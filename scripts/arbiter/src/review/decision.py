"""
Combine static checklist scores + AI evaluation into a final decision
and generate the GitHub PR review comment body.
"""

from typing import Any, Dict, List

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


# ── Decision logic ────────────────────────────────────────────────────────────

def make_decision(
    static_score: int,
    ai_result: Dict[str, Any],
    thresholds: Dict[str, int],
) -> tuple[str, int]:
    """
    Produce a final review decision.

    Score composition:
      - static_score          : 0-80  (from checklist.run_checks)
      - ai_result['weighted_contribution'] : 0-20  (from evaluator)

    Args:
        static_score: Points from static checklist (already capped at 49 on required failure)
        ai_result:    Dict returned by evaluator.evaluate_content()
        thresholds:   Dict with keys 'approve' and 'request_changes' (from config)

    Returns:
        Tuple of (decision_str, total_score) where decision_str is one of:
        'APPROVE' | 'REQUEST_CHANGES' | 'REJECT'
    """
    ai_contribution = ai_result.get('weighted_contribution', 0)
    total = min(100, static_score + ai_contribution)

    approve_threshold = thresholds.get('approve', 80)
    request_threshold = thresholds.get('request_changes', 50)

    if total >= approve_threshold:
        decision = 'APPROVE'
    elif total >= request_threshold:
        decision = 'REQUEST_CHANGES'
    else:
        decision = 'REJECT'

    logger.info(
        f"Decision: {decision} | score={total} "
        f"(static={static_score} + ai={ai_contribution})"
    )
    return decision, total


# ── Review comment builder ────────────────────────────────────────────────────

def build_review_comment(
    decision: str,
    total_score: int,
    static_score: int,
    ai_result: Dict[str, Any],
    check_results: List[Dict[str, Any]],
    file_summaries: List[Dict[str, Any]],
    thresholds: Dict[str, int],
    required_cap_applied: bool = False,
) -> str:
    """
    Build the Markdown body for the GitHub PR review comment.

    Args:
        decision:       'APPROVE' | 'REQUEST_CHANGES' | 'REJECT'
        total_score:    Final composite score 0-100
        static_score:   Points from static checklist only
        ai_result:      Dict from evaluator.evaluate_content()
        check_results:  List of per-check result dicts from checklist.run_checks()
        file_summaries: List of {'path': str, 'score': int, 'issues': [str]}
                        for each reviewed file
        thresholds:     Score threshold dict from config

    Returns:
        Markdown string ready to post as a GitHub review comment
    """
    header = _decision_header(decision, total_score, thresholds)
    cap_notice = _cap_notice() if required_cap_applied else ''
    score_breakdown = _score_breakdown(static_score, ai_result)
    checklist_table = _checklist_table(check_results)
    ai_section = _ai_section(ai_result)
    files_section = _files_section(file_summaries)
    footer = _footer(decision)

    parts = [header, cap_notice, score_breakdown, checklist_table, ai_section, files_section, footer]
    return '\n\n'.join(p for p in parts if p)


# ── Private helpers ───────────────────────────────────────────────────────────

def _decision_header(decision: str, score: int, thresholds: Dict[str, int]) -> str:
    icons = {'APPROVE': '✅', 'REQUEST_CHANGES': '⚠️', 'REJECT': '❌'}
    icon = icons.get(decision, '🔍')

    if decision == 'APPROVE':
        verdict = f"This PR meets quality standards and is approved for merge."
    elif decision == 'REQUEST_CHANGES':
        verdict = (
            f"This PR needs some improvements before it can be merged. "
            f"Please address the issues listed below and push an update."
        )
    else:
        verdict = (
            f"This PR has significant quality issues that must be resolved. "
            f"Please review the checklist failures and AI feedback carefully."
        )

    return (
        f"## {icon} PR Arbiter Review — Score: **{score}/100**\n\n"
        f"{verdict}\n\n"
        f"| Threshold | Score |\n"
        f"|-----------|-------|\n"
        f"| Auto-approve (≥ {thresholds.get('approve', 80)}) | {'✅ Met' if score >= thresholds.get('approve', 80) else '❌ Not met'} |\n"
        f"| Request changes (≥ {thresholds.get('request_changes', 50)}) | {'✅ Met' if score >= thresholds.get('request_changes', 50) else '❌ Not met'} |"
    )


def _cap_notice() -> str:
    return (
        "> ⚠️ **Required check failed in one or more files** — static score capped at 49 "
        "regardless of other passing files. Resolve all ❌ required checks below to lift the cap."
    )


def _score_breakdown(static_score: int, ai_result: Dict[str, Any]) -> str:
    ai_contrib = ai_result.get('weighted_contribution', 0)
    total = static_score + ai_contrib
    return (
        f"### Score Breakdown\n\n"
        f"| Component | Points |\n"
        f"|-----------|--------|\n"
        f"| Static checklist (max 80) | {static_score} |\n"
        f"| AI evaluation (max 20) | {ai_contrib} |\n"
        f"| **Total** | **{total}** |"
    )


def _checklist_table(check_results: List[Dict[str, Any]]) -> str:
    if not check_results:
        return ''

    rows = ['### Checklist Results\n', '| # | Check | Type | Result |', '|---|-------|------|--------|']
    for i, r in enumerate(check_results, 1):
        icon = '✅' if r['passed'] else ('❌' if r['type'] == 'required' else '⚠️')
        rows.append(
            f"| {i} | {r['description']} | {r['type'].title()} | {icon} |"
        )
    return '\n'.join(rows)


def _ai_section(ai_result: Dict[str, Any]) -> str:
    if not ai_result.get('summary'):
        return ''

    lines = [
        '### AI Content Evaluation',
        '',
        f"**Summary:** {ai_result['summary']}",
        '',
        f"| Criterion | Score |",
        f"|-----------|-------|",
        f"| Technical accuracy (max 25) | {ai_result.get('technical_accuracy', 0)} |",
        f"| Clarity & readability (max 20) | {ai_result.get('clarity', 0)} |",
        f"| SEO quality (max 20) | {ai_result.get('seo_quality', 0)} |",
        f"| Actionability (max 20) | {ai_result.get('actionability', 0)} |",
        f"| Content uniqueness (max 15) | {ai_result.get('uniqueness', 0)} |",
    ]

    strengths = ai_result.get('strengths', [])
    if strengths:
        lines += ['', '**Strengths:**']
        lines += [f"- {s}" for s in strengths]

    issues = ai_result.get('issues', [])
    if issues:
        lines += ['', '**Issues:**']
        lines += [f"- {iss}" for iss in issues]

    return '\n'.join(lines)


def _files_section(file_summaries: List[Dict[str, Any]]) -> str:
    if not file_summaries:
        return ''

    lines = ['### Files Reviewed']
    for fs in file_summaries:
        lines.append(f"\n**`{fs['path']}`**")
        if fs.get('issues'):
            for issue in fs['issues']:
                lines.append(f"  - {issue}")
        else:
            lines.append("  - No issues found")

    return '\n'.join(lines)


def _footer(decision: str) -> str:
    return (
        "---\n"
        "*This review was generated automatically by the **Tutorials PR Arbiter**. "
        "Static checks evaluate frontmatter, structure, and content completeness. "
        "The AI evaluation assesses overall quality and SEO effectiveness.*"
    )
