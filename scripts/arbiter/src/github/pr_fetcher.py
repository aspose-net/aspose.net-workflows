"""Fetch open pull requests from a repository, with optional filtering."""

from typing import Dict, List, Optional

from github.GithubException import GithubException
from github.PullRequest import PullRequest
from github.Repository import Repository
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def fetch_open_prs(
    repo: Repository,
    branch_prefix: Optional[str] = None,
    required_labels: Optional[List[str]] = None,
) -> List[PullRequest]:
    """
    Return open PRs for a repository.

    A PR is included if it matches EITHER condition:
      - Its head branch starts with ``branch_prefix`` (when provided), OR
      - It carries ALL labels in ``required_labels`` (when provided).

    Args:
        repo:            PyGithub Repository object
        branch_prefix:   Include PRs whose head branch starts with this string.
        required_labels: Include PRs that have ALL of these label names.

    Returns:
        List of matching PullRequest objects (may be empty), deduplicated.
    """
    try:
        all_prs = list(repo.get_pulls(state='open', sort='created', direction='asc'))
        matched: List[PullRequest] = []
        seen_numbers: set = set()

        for pr in all_prs:
            if pr.number in seen_numbers:
                continue

            pr_labels = {label.name for label in pr.labels}
            by_prefix = branch_prefix and pr.head.ref.startswith(branch_prefix)
            by_labels = required_labels and all(lbl in pr_labels for lbl in required_labels)

            if by_prefix or by_labels:
                matched.append(pr)
                seen_numbers.add(pr.number)

        logger.info(
            f"{repo.full_name}: {len(matched)} matching open PR(s) "
            f"(prefix='{branch_prefix}', labels={required_labels})"
        )
        return matched

    except GithubException as e:
        logger.error(f"Failed to fetch PRs for {repo.full_name}: {e}")
        return []


def get_pr_files(pr: PullRequest) -> List[Dict[str, str]]:
    """
    Return the list of files changed in a PR.

    Args:
        pr: PullRequest object

    Returns:
        List of dicts:  [{'path': str, 'status': str, 'patch': str}, ...]
        'patch' is the unified diff for the file (may be empty for binary files).
    """
    try:
        files = []
        for f in pr.get_files():
            files.append({
                'path': f.filename,
                'status': f.status,           # added | modified | removed | renamed
                'patch': f.patch or '',        # unified diff (empty for binary)
                'additions': f.additions,
                'deletions': f.deletions,
            })
        logger.debug(f"PR #{pr.number}: {len(files)} file(s) changed")
        return files

    except GithubException as e:
        logger.error(f"Failed to get files for PR #{pr.number}: {e}")
        return []


def get_file_content(
    repo: Repository,
    path: str,
    ref: str,
) -> Optional[str]:
    """
    Fetch the decoded content of a file at a specific git ref.

    Args:
        repo: PyGithub Repository object
        path: File path within the repository
        ref:  Commit SHA or branch name

    Returns:
        File content as UTF-8 string, or None if unavailable
    """
    try:
        contents = repo.get_contents(path, ref=ref)
        if isinstance(contents, list):
            logger.warning(f"Path is a directory, not a file: {path}")
            return None
        return contents.decoded_content.decode('utf-8')
    except GithubException as e:
        logger.warning(f"Could not fetch {path} @ {ref}: {e}")
        return None


def get_english_markdown_files(
    pr_files: List[Dict[str, str]],
    path_filter: Optional[str] = '/english/',
) -> List[Dict[str, str]]:
    """
    Filter PR file list to Markdown files, optionally matching a path segment.

    By default only English source files are included (tutorials convention).
    Set ``path_filter=None`` to include all ``.md`` files regardless of path.

    Args:
        pr_files:    Output of get_pr_files()
        path_filter: Path segment that must appear in the file path.
                     ``None`` disables the path filter.

    Returns:
        Subset of pr_files matching the filter and ending with .md
    """
    return [
        f for f in pr_files
        if f['path'].endswith('.md')
        and (path_filter is None or path_filter in f['path'])
        and f['status'] in ('added', 'modified')
    ]
