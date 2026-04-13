"""Post GitHub PR reviews and optionally merge approved PRs."""

from typing import Optional

from github.GithubException import GithubException
from github.PullRequest import PullRequest
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# GitHub review event constants
_EVENT_APPROVE = "APPROVE"
_EVENT_REQUEST_CHANGES = "REQUEST_CHANGES"
_EVENT_COMMENT = "COMMENT"


def post_review(
    pr: PullRequest,
    decision: str,
    body: str,
) -> bool:
    """
    Submit a GitHub pull-request review.

    Args:
        pr:       PullRequest object
        decision: 'APPROVE' | 'REQUEST_CHANGES' | 'REJECT'
                  (REJECT maps to REQUEST_CHANGES with a rejection header)
        body:     Review comment body (Markdown)

    Returns:
        True on success, False on failure
    """
    if decision == 'APPROVE':
        event = _EVENT_APPROVE
    else:
        # Both REQUEST_CHANGES and REJECT use GitHub's REQUEST_CHANGES event
        event = _EVENT_REQUEST_CHANGES

    try:
        pr.create_review(body=body, event=event)
        logger.info(f"Posted '{decision}' review on PR #{pr.number}")
        return True
    except GithubException as e:
        # GitHub rejects APPROVE/REQUEST_CHANGES when the reviewer is the PR author.
        # Fall back to posting the full report as a plain issue comment instead.
        if e.status == 422 and 'own pull request' in str(e).lower():
            logger.warning(
                f"PR #{pr.number}: cannot post formal review (same author) — "
                f"falling back to comment"
            )
            return post_comment(pr, body)
        logger.error(f"Failed to post review on PR #{pr.number}: {e}")
        return False


def post_comment(pr: PullRequest, body: str) -> bool:
    """
    Post a plain issue comment (not a formal review) on a PR.

    Args:
        pr:   PullRequest object
        body: Comment body (Markdown)

    Returns:
        True on success, False on failure
    """
    try:
        pr.create_issue_comment(body)
        logger.info(f"Posted comment on PR #{pr.number}")
        return True
    except GithubException as e:
        logger.error(f"Failed to post comment on PR #{pr.number}: {e}")
        return False


def merge_pr(
    pr: PullRequest,
    commit_message: Optional[str] = None,
    merge_method: str = "squash",
) -> bool:
    """
    Merge a pull request.

    Args:
        pr:             PullRequest object
        commit_message: Optional custom squash commit message
        merge_method:   'merge' | 'squash' | 'rebase'  (default: squash)

    Returns:
        True on success, False on failure
    """
    try:
        if not pr.mergeable:
            logger.warning(
                f"PR #{pr.number} is not mergeable (conflicts or checks pending)"
            )
            return False

        kwargs = {"merge_method": merge_method}
        if commit_message:
            kwargs["commit_message"] = commit_message

        pr.merge(**kwargs)
        logger.info(f"Merged PR #{pr.number} via {merge_method}")
        return True

    except GithubException as e:
        logger.error(f"Failed to merge PR #{pr.number}: {e}")
        return False


def add_labels(pr: PullRequest, labels: list) -> None:
    """
    Add labels to a pull request (silently ignores failures).

    Args:
        pr:     PullRequest object
        labels: List of label name strings
    """
    try:
        pr.add_to_labels(*labels)
        logger.debug(f"Added labels {labels} to PR #{pr.number}")
    except GithubException as e:
        logger.warning(f"Failed to add labels to PR #{pr.number}: {e}")
