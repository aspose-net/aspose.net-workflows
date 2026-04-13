"""
Tutorials PR Arbiter — Main Orchestrator

Workflow per run:
  1. Load config + checklist
  2. For each configured product repository:
     a. Fetch open PRs (filtered by branch prefix)
     b. Skip PRs already reviewed (unless updated since last review)
     c. For each unreviewed PR:
        i.   Fetch changed English Markdown files
        ii.  Run static checklist on each file
        iii. Run AI evaluation on each file
        iv.  Combine scores → decision
        v.   Post GitHub review (approve / request-changes)
        vi.  Optionally merge approved PRs
        vii. Persist decision in state DB
  3. Post run metrics to monitoring endpoint
"""

import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.ai.client import AIClient
from src.config.loader import load_config
from src.config.validator import validate_config
from src.github.client import GitHubClient
from src.github.pr_fetcher import (
    fetch_open_prs,
    get_english_markdown_files,
    get_file_content,
    get_pr_files,
)
from src.github.pr_reviewer import add_labels, merge_pr, post_review
from src.review.checklist import load_checklist, run_checks
from src.review.decision import build_review_comment, make_decision
from src.review.evaluator import evaluate_content
from src.state.repository import StateRepository
try:
    from src.utils.email_reporter import WeeklyReporter
except ImportError:
    WeeklyReporter = None
from src.utils.logger import setup_logger
from src.utils.metrics_logger import MetricsLogger

logger = setup_logger(__name__)

_PLATFORM_MAP = {
    'net':        '.NET',
    'java':       'Java',
    'python':     'Python',
    'cpp':        'C++',
    'nodejs':     'Node.js',
    'android':    'Android',
    'ios':        'iOS',
    'php':        'PHP',
    'ruby':       'Ruby',
    'go':         'Go',
    'javascript': 'JavaScript',
    'rust':       'Rust',
}


def _detect_platforms(file_paths: List[str]) -> str:
    """
    Infer platform(s) from PR file paths (e.g. 'words/english/net/foo.md' -> '.NET').
    Returns a display string such as '.NET' or '.NET, Java'.
    Falls back to 'All' when no known segment is found.
    """
    found: list = []
    for path in file_paths:
        parts = path.lower().replace('\\', '/').split('/')
        for part in parts:
            display = _PLATFORM_MAP.get(part)
            if display and display not in found:
                found.append(display)
    return ', '.join(found) if found else 'All'


class PRArbitrAgent:
    """Orchestrates PR review across all configured tutorial repositories."""

    def __init__(self, config_path: str = "config/config.yaml"):
        logger.info("=" * 70)
        logger.info("Tutorials PR Arbiter Starting")
        logger.info("=" * 70)

        self.config = load_config(config_path)
        if not validate_config(self.config):
            raise ValueError("Invalid configuration — aborting.")

        gpt_cfg = self.config['gpt_oss']
        self.ai_client = AIClient(
            base_url=gpt_cfg['endpoint'],
            api_key=gpt_cfg['api_key'],
            model=gpt_cfg['model'],
            timeout=gpt_cfg.get('timeout', 120),
        )

        self.github_client = GitHubClient(self.config['github']['token'])
        self.state_repo = StateRepository("data/state.json")
        self.metrics_logger = MetricsLogger(self.config)
        if WeeklyReporter is not None:
            self.weekly_reporter = WeeklyReporter(self.config.get('email_report', {}))
        else:
            self.weekly_reporter = None

        checklist_path = self.config['review']['checklist_path']
        self.checklist = load_checklist(checklist_path)

        self.review_cfg = self.config['review']
        self.thresholds = self.review_cfg['score_thresholds']
        self.prompt_path = self.config['prompts']['review_pr']
        self.branch_prefix = self.review_cfg.get('pr_branch_prefix', 'optimize/')
        self.pr_labels = self.review_cfg.get('pr_labels', [])
        self.auto_merge = self.review_cfg.get('auto_merge', False)
        self.post_comment = self.review_cfg.get('post_review_comment', True)
        file_filter_cfg = self.review_cfg.get('file_filter', {})
        self.path_filter = file_filter_cfg.get('path_contains', '/english/')

        # Run-level counters (reset per run() call)
        self._reset_metrics()
        self.run_start: datetime = datetime.now()

        logger.info("All components initialised successfully")

    # ── Public entry point ────────────────────────────────────────────────────

    def run(
        self,
        product_filter: Optional[str] = None,
        max_prs: Optional[int] = None,
    ) -> None:
        """
        Review open PRs across all (or one) product repository.

        Args:
            product_filter: If set, only process this product key (e.g. 'words').
                            None means process all configured products.
            max_prs:        Cap on how many PRs to review this run (None = unlimited).
                            Set to 1 for rotation mode (one PR per scheduled run).
        """
        self._reset_metrics()
        self.run_start = datetime.now()

        products = self.config['products']

        if product_filter:
            if product_filter not in products:
                logger.error(f"Unknown product: '{product_filter}'")
                return
            products = {product_filter: products[product_filter]}

        for product_key, product_cfg in products.items():
            product_start = datetime.now()
            product_metrics = self._blank_product_metrics()

            remaining = (
                max_prs - self.metrics['prs_reviewed']
                if max_prs is not None else None
            )
            if remaining is not None and remaining <= 0:
                logger.info(f"max_prs={max_prs} reached — stopping early")
                break

            try:
                self._process_product(
                    product_key, product_cfg, product_metrics,
                    max_prs=remaining,
                )
            except Exception as e:
                logger.error(
                    f"Unhandled error processing '{product_key}': {e}",
                    exc_info=True,
                )
                product_metrics['errors'] += 1
                self.metrics['errors'] += 1

            # Post per-product metrics
            product_duration_ms = int(
                (datetime.now() - product_start).total_seconds() * 1000
            )
            run_id = self._make_run_id(product_key)
            platform = ', '.join(product_metrics['platforms']) or 'All'
            self.metrics_logger.log_review_run(
                run_id=run_id,
                product=product_key,
                platform=platform,
                files_found=product_metrics['files_found'],
                files_reviewed=product_metrics['files_reviewed'],
                prs_errors=product_metrics['errors'],
                duration_ms=product_duration_ms,
                token_usage=self.ai_client.token_usage,
                api_calls_count=self.ai_client.api_calls,
            )

        self._log_summary()
        self._maybe_send_weekly_report()
        self.state_repo.close()

    # ── Per-product processing ────────────────────────────────────────────────

    def _process_product(
        self,
        product: str,
        cfg: Dict[str, Any],
        product_metrics: Dict[str, int],
        max_prs: Optional[int] = None,
    ) -> None:
        repo_url = cfg['content_repo']
        logger.info(f"[{product}] Processing {repo_url}")

        try:
            repo = self.github_client.get_repository(repo_url)
        except Exception as e:
            logger.error(f"[{product}] Cannot access repo: {e}")
            product_metrics['errors'] += 1
            self.metrics['errors'] += 1
            return

        prs = fetch_open_prs(
            repo,
            branch_prefix=self.branch_prefix,
            required_labels=self.pr_labels or None,
        )
        product_metrics['prs_found'] += len(prs)
        self.metrics['prs_found'] += len(prs)

        reviewed_this_product = 0
        for pr in prs:
            if max_prs is not None and reviewed_this_product >= max_prs:
                logger.info(f"[{product}] max_prs={max_prs} reached for this product — stopping")
                break
            try:
                before = self.metrics['prs_reviewed']
                self._process_pr(repo, pr, product, repo_url, product_metrics)
                if self.metrics['prs_reviewed'] > before:
                    reviewed_this_product += 1
            except Exception as e:
                logger.error(
                    f"[{product}] Error on PR #{pr.number}: {e}",
                    exc_info=True,
                )
                product_metrics['errors'] += 1
                self.metrics['errors'] += 1

    # ── Per-PR processing ─────────────────────────────────────────────────────

    def _process_pr(
        self,
        repo,
        pr,
        product: str,
        repo_url: str,
        product_metrics: Dict,
    ) -> None:
        pr_updated_at = pr.updated_at.isoformat()

        if self.state_repo.was_reviewed(repo_url, pr.number):
            logger.debug(
                f"[{product}] Skipping PR #{pr.number} '{pr.title}' — already reviewed"
            )
            self.metrics['prs_skipped'] += 1
            return

        logger.info(f"[{product}] Reviewing PR #{pr.number}: {pr.title}")

        # ── Gather changed English Markdown files ─────────────────────────────
        pr_files = get_pr_files(pr)
        english_files = get_english_markdown_files(pr_files, path_filter=self.path_filter)

        if not english_files:
            logger.info(
                f"[{product}] PR #{pr.number} has no English Markdown files — skipping"
            )
            self.metrics['prs_skipped'] += 1
            return

        # Detect platform(s) from file paths and accumulate file count
        file_paths = [f['path'] for f in english_files]
        pr_platform = _detect_platforms(file_paths)
        product_metrics['files_found'] += len(english_files)
        for p in pr_platform.split(', '):
            if p and p not in product_metrics['platforms']:
                product_metrics['platforms'].append(p)

        # ── Evaluate each file ────────────────────────────────────────────────
        file_summaries: List[Dict[str, Any]] = []
        aggregate_static = 0
        aggregate_ai_contribution = 0
        aggregate_check_results: List[Dict[str, Any]] = []
        any_required_failure = False  # True if ANY file fails a required check

        for file_info in english_files:
            file_path = file_info['path']
            content = get_file_content(repo, file_path, ref=pr.head.sha)

            if content is None:
                logger.warning(f"[{product}] Could not fetch {file_path} — skipping file")
                continue

            static_score, check_results = run_checks(
                content, self.checklist,
                context={'patch': file_info.get('patch', '')},
            )

            # Propagate required-failure flag across all files in the PR
            if any(r['type'] == 'required' and not r['passed'] for r in check_results):
                any_required_failure = True

            ai_result = evaluate_content(
                content=content,
                ai_client=self.ai_client,
                prompt_path=self.prompt_path,
                checklist_config=self.checklist,
            )

            failed_checks = [c['description'] for c in check_results if not c['passed']]
            per_file_issues = failed_checks + ai_result.get('issues', [])

            file_summaries.append({
                'path': file_path,
                'static_score': static_score,
                'ai_score': ai_result.get('score', 0),
                'issues': per_file_issues,
            })

            aggregate_static += static_score
            aggregate_ai_contribution += ai_result.get('weighted_contribution', 0)

            # Merge check results: a check is failed if it failed in ANY file
            if not aggregate_check_results:
                aggregate_check_results = [dict(r) for r in check_results]
            else:
                for merged, current in zip(aggregate_check_results, check_results):
                    if not current['passed']:
                        merged['passed'] = False

        if not file_summaries:
            logger.warning(f"[{product}] PR #{pr.number} — no files could be evaluated")
            self.metrics['prs_skipped'] += 1
            return

        # ── Average scores across files ───────────────────────────────────────
        n = len(file_summaries)
        avg_static = round(aggregate_static / n)
        avg_ai_contribution = round(aggregate_ai_contribution / n)

        # Re-apply the required-failure cap after averaging.
        # Without this, a failing file can be "rescued" by passing files:
        # e.g. (49 + 100 + 100) / 3 = 83 → would incorrectly APPROVE.
        if any_required_failure:
            avg_static = min(avg_static, 49)
            logger.warning(
                f"[{product}] PR #{pr.number} — required check failed in at least one file; "
                f"static score capped at 49 (was {round(aggregate_static / n)})"
            )

        synthetic_ai = {
            'weighted_contribution': avg_ai_contribution,
            'score': round(sum(f['ai_score'] for f in file_summaries) / n),
            'summary': f"Averaged over {n} English Markdown file(s).",
            'strengths': [],
            'issues': list({iss for f in file_summaries for iss in f['issues']}),
            'technical_accuracy': 0,
            'clarity': 0,
            'seo_quality': 0,
            'actionability': 0,
            'uniqueness': 0,
        }

        decision, total_score = make_decision(avg_static, synthetic_ai, self.thresholds)

        # ── Build and post review ─────────────────────────────────────────────
        if self.post_comment:
            comment_body = build_review_comment(
                decision=decision,
                total_score=total_score,
                static_score=avg_static,
                ai_result=synthetic_ai,
                check_results=aggregate_check_results,
                file_summaries=file_summaries,
                thresholds=self.thresholds,
                required_cap_applied=any_required_failure,
            )
        else:
            comment_body = f"PR Arbiter decision: **{decision}** (score: {total_score}/100)"

        post_review(pr, decision, comment_body)

        # ── Label PR ──────────────────────────────────────────────────────────
        label_map = {
            'APPROVE': ['arbiter:approved'],
            'REQUEST_CHANGES': ['arbiter:needs-changes'],
            'REJECT': ['arbiter:rejected'],
        }
        add_labels(pr, label_map.get(decision, []))

        # ── Auto-merge if configured and approved ─────────────────────────────
        merged = False
        if self.auto_merge and decision == 'APPROVE':
            commit_msg = f"Auto-merge: {pr.title} (arbiter score {total_score}/100)"
            merged = merge_pr(pr, commit_message=commit_msg, merge_method='squash')
            if merged:
                self.metrics['merged'] += 1

        # ── Persist state ─────────────────────────────────────────────────────
        self.state_repo.save_review(
            repo_url=repo_url,
            pr_number=pr.number,
            product=product,
            decision=decision,
            score=total_score,
            pr_updated_at=pr_updated_at,
        )

        # ── Update both run-level and product-level counters ──────────────────
        self.metrics['prs_reviewed'] += 1

        # All decisions count as successfully reviewed — agent completed its job
        product_metrics['files_reviewed'] += n

        if decision == 'APPROVE':
            self.metrics['approved'] += 1
            product_metrics['approved'] += 1
        elif decision == 'REQUEST_CHANGES':
            self.metrics['request_changes'] += 1
            product_metrics['request_changes'] += 1
        else:
            self.metrics['rejected'] += 1
            product_metrics['rejected'] += 1

        logger.info(
            f"[{product}] PR #{pr.number} -> {decision} "
            f"(score={total_score}, files={n}, merged={merged})"
        )

    # ── Summary ───────────────────────────────────────────────────────────────

    def _log_summary(self) -> None:
        elapsed = int((datetime.now() - self.run_start).total_seconds())
        logger.info("=" * 70)
        logger.info("PR Arbiter Run Complete")
        logger.info(f"  Elapsed:         {elapsed}s")
        logger.info(f"  PRs found:       {self.metrics['prs_found']}")
        logger.info(f"  PRs skipped:     {self.metrics['prs_skipped']}")
        logger.info(f"  PRs reviewed:    {self.metrics['prs_reviewed']}")
        logger.info(f"    Approved:      {self.metrics['approved']}")
        logger.info(f"    Req. changes:  {self.metrics['request_changes']}")
        logger.info(f"    Rejected:      {self.metrics['rejected']}")
        logger.info(f"    Merged:        {self.metrics['merged']}")
        logger.info(f"  Errors:          {self.metrics['errors']}")
        logger.info(f"  AI tokens used:  {self.ai_client.token_usage}")
        logger.info(f"  AI API calls:    {self.ai_client.api_calls}")
        logger.info("=" * 70)

    # ── Weekly report ─────────────────────────────────────────────────────────

    def _maybe_send_weekly_report(self) -> None:
        """Send the weekly summary email on Fridays."""
        if self.weekly_reporter is None:
            return
        if not self.weekly_reporter.is_friday():
            logger.debug("Not Friday — skipping weekly email report")
            return

        since = (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                 - timedelta(days=6)).isoformat()
        reviews = self.state_repo.get_reviews_since(since)
        logger.info(f"Friday report: sending summary for {len(reviews)} review(s) from the past week")
        self.weekly_reporter.send_weekly_report(reviews)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _reset_metrics(self) -> None:
        self.metrics: Dict[str, int] = {
            'prs_found': 0,
            'prs_skipped': 0,
            'prs_reviewed': 0,
            'approved': 0,
            'request_changes': 0,
            'rejected': 0,
            'merged': 0,
            'errors': 0,
        }

    @staticmethod
    def _blank_product_metrics() -> Dict:
        return {
            'prs_found': 0,
            'approved': 0,
            'request_changes': 0,
            'rejected': 0,
            'errors': 0,
            # File-level counts (used as metrics items)
            'files_found': 0,
            'files_reviewed': 0,  # all files where a review was posted (success)
            # Detected platforms across all reviewed PRs
            'platforms': [],
        }

    @staticmethod
    def _make_run_id(product: Optional[str] = None) -> str:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        suffix = f"_{product}" if product else "_all"
        return f"pr_arbiter{suffix}_{ts}"


# ── CLI entry point ───────────────────────────────────────────────────────────

def main() -> None:
    """
    Usage:
        python -m src.main                         # Review all products (unlimited)
        python -m src.main --product words         # Review only 'words'
        python -m src.main --product words --max-prs 1   # One PR, rotation mode
        python -m src.main words                   # Legacy positional form
    """
    import argparse

    parser = argparse.ArgumentParser(description="Tutorials PR Arbiter")
    parser.add_argument(
        '--config', '-c',
        default='config/config.yaml',
        help="Path to config YAML (default: config/config.yaml).",
    )
    parser.add_argument(
        '--product', '-p',
        default=None,
        help="Product key to process (e.g. words, 3d). Omit to process all.",
    )
    parser.add_argument(
        '--max-prs', '-n',
        type=int,
        default=None,
        dest='max_prs',
        help="Maximum number of PRs to review this run (default: unlimited).",
    )
    # Legacy: positional product names without flags
    parser.add_argument('products_positional', nargs='*', help=argparse.SUPPRESS)

    args = parser.parse_args()

    agent = PRArbitrAgent(config_path=args.config)

    if args.product:
        agent.run(product_filter=args.product, max_prs=args.max_prs)
    elif args.products_positional:
        for product in args.products_positional:
            agent.run(product_filter=product, max_prs=args.max_prs)
    else:
        agent.run(product_filter=None, max_prs=args.max_prs)


if __name__ == '__main__':
    main()
