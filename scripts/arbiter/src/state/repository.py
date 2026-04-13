"""State persistence for reviewed PRs using TinyDB."""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from tinydb import Query, TinyDB
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class StateRepository:
    """
    Tracks which PRs have been reviewed to avoid duplicate reviews.

    Schema (table: 'reviews'):
        repo_url    : str   - Full GitHub repository URL
        pr_number   : int   - PR number within the repository
        product     : str   - Product key (e.g. 'words', 'pdf')
        decision    : str   - 'APPROVE' | 'REQUEST_CHANGES' | 'REJECT'
        score       : int   - Final composite score (0-100)
        reviewed_at : str   - ISO timestamp of when the review was posted
        pr_updated_at: str  - PR updated_at timestamp at time of review
                              (used to detect if PR changed since last review)
    """

    def __init__(self, db_path: str = "data/state.json"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db = TinyDB(db_path)
        self.reviews = self.db.table('reviews')
        logger.info(f"StateRepository initialised at {db_path}")

    def close(self) -> None:
        self.db.close()

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_review(self, repo_url: str, pr_number: int) -> Optional[Dict]:
        """
        Return the stored review record for a PR, or None if not reviewed yet.

        Args:
            repo_url:  Repository URL
            pr_number: PR number

        Returns:
            Review record dict or None
        """
        Q = Query()
        return self.reviews.get(
            (Q.repo_url == repo_url) & (Q.pr_number == pr_number)
        )

    def was_reviewed(self, repo_url: str, pr_number: int) -> bool:
        """Return True if this PR has already been reviewed."""
        return self.get_review(repo_url, pr_number) is not None

    def needs_re_review(
        self,
        repo_url: str,
        pr_number: int,
        pr_updated_at: str,
    ) -> bool:
        """
        Return True when the PR was reviewed before but has since been updated.

        Args:
            repo_url:       Repository URL
            pr_number:      PR number
            pr_updated_at:  Current PR updated_at ISO timestamp from GitHub

        Returns:
            True if the PR's updated_at changed since the last review
        """
        record = self.get_review(repo_url, pr_number)
        if not record:
            return False  # Never reviewed → not a *re*-review
        return record.get('pr_updated_at') != pr_updated_at

    def get_all_reviews(self) -> List[Dict]:
        """Return all stored review records."""
        return self.reviews.all()

    def get_reviews_since(self, since_iso: str) -> List[Dict]:
        """
        Return review records where reviewed_at >= since_iso.

        Args:
            since_iso: ISO timestamp string (e.g. '2026-04-03T00:00:00')

        Returns:
            List of matching review records
        """
        return [
            r for r in self.reviews.all()
            if r.get('reviewed_at', '') >= since_iso
        ]

    # ── Write ─────────────────────────────────────────────────────────────────

    def save_review(
        self,
        repo_url: str,
        pr_number: int,
        product: str,
        decision: str,
        score: int,
        pr_updated_at: str,
    ) -> None:
        """
        Persist a review decision.  Upserts (inserts or replaces).

        Args:
            repo_url:       Repository URL
            pr_number:      PR number
            product:        Product key
            decision:       'APPROVE' | 'REQUEST_CHANGES' | 'REJECT'
            score:          Final composite score 0-100
            pr_updated_at:  PR updated_at timestamp from GitHub
        """
        Q = Query()
        record = {
            'repo_url': repo_url,
            'pr_number': pr_number,
            'product': product,
            'decision': decision,
            'score': score,
            'reviewed_at': datetime.now().isoformat(),
            'pr_updated_at': pr_updated_at,
        }

        existing = self.reviews.get(
            (Q.repo_url == repo_url) & (Q.pr_number == pr_number)
        )

        if existing:
            self.reviews.update(
                record,
                (Q.repo_url == repo_url) & (Q.pr_number == pr_number),
            )
            logger.info(
                f"Updated review record: {repo_url}#{pr_number} -> {decision} ({score})"
            )
        else:
            self.reviews.insert(record)
            logger.info(
                f"Saved review: {repo_url}#{pr_number} -> {decision} ({score})"
            )

    def clear_review(self, repo_url: str, pr_number: int) -> None:
        """Remove a review record (useful for re-triggering a review)."""
        Q = Query()
        self.reviews.remove(
            (Q.repo_url == repo_url) & (Q.pr_number == pr_number)
        )
        logger.info(f"Cleared review record: {repo_url}#{pr_number}")

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, int]:
        """Return review counts grouped by decision."""
        all_records = self.reviews.all()
        stats: Dict[str, int] = {'APPROVE': 0, 'REQUEST_CHANGES': 0, 'REJECT': 0, 'total': 0}
        for record in all_records:
            decision = record.get('decision', '')
            if decision in stats:
                stats[decision] += 1
            stats['total'] += 1
        return stats
