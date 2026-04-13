"""GitHub API client wrapper."""

from github import Github
from github.GithubException import GithubException
from github.Repository import Repository
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class GitHubClient:
    """Thin wrapper around PyGithub."""

    def __init__(self, token: str):
        """
        Initialise the GitHub client.

        Args:
            token: Personal access token with repo + pull_request scopes
        """
        self.client = Github(token)
        self.user = self.client.get_user()
        logger.info(f"GitHub client initialised for user: {self.user.login}")

    def get_repository(self, repo_url: str) -> Repository:
        """
        Resolve a full GitHub URL to a Repository object.

        Args:
            repo_url: e.g. https://github.com/owner/repo

        Returns:
            PyGithub Repository object

        Raises:
            ValueError: Malformed URL
            GithubException: Repo not found / no access
        """
        parts = repo_url.rstrip('/').split('/')
        if len(parts) < 2:
            raise ValueError(f"Invalid repository URL: {repo_url}")

        full_name = f"{parts[-2]}/{parts[-1]}"

        try:
            repo = self.client.get_repo(full_name)
            logger.debug(f"Retrieved repository: {full_name}")
            return repo
        except GithubException as e:
            logger.error(f"Failed to get repository {full_name}: {e}")
            raise

    def check_rate_limit(self) -> dict:
        """Return current GitHub API rate-limit information."""
        rate_limit = self.client.get_rate_limit()
        core = rate_limit.core
        return {
            'remaining': core.remaining,
            'limit': core.limit,
            'reset_time': core.reset,
        }
