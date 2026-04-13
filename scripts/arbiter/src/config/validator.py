"""Configuration validator for the PR Arbiter."""

from typing import Any, Dict
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def validate_config(config: Dict[str, Any]) -> bool:
    """
    Validate the arbiter configuration structure.

    Args:
        config: Configuration dictionary

    Returns:
        True if valid, False otherwise
    """
    required_sections = ['github', 'gpt_oss', 'products', 'review', 'prompts']

    try:
        for section in required_sections:
            if section not in config:
                logger.error(f"Missing required config section: '{section}'")
                return False

        if not _validate_github(config['github']):
            return False

        if not _validate_gpt_oss(config['gpt_oss']):
            return False

        if not _validate_products(config['products']):
            return False

        if not _validate_review(config['review']):
            return False

        if not _validate_prompts(config['prompts']):
            return False

        logger.info("Configuration validation passed")
        return True

    except Exception as e:
        logger.error(f"Configuration validation error: {e}")
        return False


def _validate_github(github_config: Dict[str, Any]) -> bool:
    if 'token' not in github_config or not github_config['token']:
        logger.error("Missing or empty 'token' in github config")
        return False
    # Warn if token still looks like a placeholder
    if github_config['token'].startswith('${'):
        logger.error("GITHUB_TOKEN environment variable is not set")
        return False
    return True


def _validate_gpt_oss(gpt_config: Dict[str, Any]) -> bool:
    for field in ['endpoint', 'api_key', 'model']:
        if field not in gpt_config or not gpt_config[field]:
            logger.error(f"Missing or empty '{field}' in gpt_oss config")
            return False
        if str(gpt_config[field]).startswith('${'):
            logger.error(f"Environment variable for gpt_oss.{field} is not set")
            return False
    return True


def _validate_products(products: Dict[str, Any]) -> bool:
    if not products:
        logger.error("No products configured")
        return False

    for product, cfg in products.items():
        if 'content_repo' not in cfg:
            logger.error(f"Missing 'content_repo' for product: {product}")
            return False

    return True


def _validate_review(review_config: Dict[str, Any]) -> bool:
    required = ['checklist_path', 'score_thresholds']
    for field in required:
        if field not in review_config:
            logger.error(f"Missing '{field}' in review config")
            return False

    thresholds = review_config['score_thresholds']
    for key in ['approve', 'request_changes']:
        if key not in thresholds:
            logger.error(f"Missing score threshold: '{key}'")
            return False

    return True


def _validate_prompts(prompts_config: Dict[str, Any]) -> bool:
    if 'review_pr' not in prompts_config or not prompts_config['review_pr']:
        logger.error("Missing 'review_pr' prompt path in prompts config")
        return False
    return True
