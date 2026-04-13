"""Configuration loader with environment variable substitution."""

import os
import re
import yaml
from pathlib import Path
from typing import Any, Dict
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def load_config(config_path: str = "config/config.yaml") -> Dict[str, Any]:
    """
    Load YAML configuration and substitute ${VAR_NAME} with env vars.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Configuration dictionary with env vars substituted

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML syntax is invalid
    """
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    config = _replace_env_vars(config)
    logger.info(f"Configuration loaded from {config_path}")
    return config


def load_prompt(prompt_path: str) -> str:
    """
    Load a prompt template from a file.

    Args:
        prompt_path: Path to prompt text file

    Returns:
        Prompt content as string
    """
    path = Path(prompt_path)

    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    logger.debug(f"Prompt loaded from {prompt_path}")
    return content


def _replace_env_vars(config: Any) -> Any:
    """Recursively replace ${VAR_NAME} patterns with environment variable values."""
    if isinstance(config, dict):
        return {k: _replace_env_vars(v) for k, v in config.items()}
    elif isinstance(config, list):
        return [_replace_env_vars(item) for item in config]
    elif isinstance(config, str):
        pattern = r'\$\{([^}]+)\}'

        def replacer(match: re.Match) -> str:
            var_name = match.group(1)
            return os.getenv(var_name, match.group(0))

        return re.sub(pattern, replacer, config)
    return config
