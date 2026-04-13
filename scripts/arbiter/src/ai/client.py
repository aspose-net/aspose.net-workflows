"""GPT-OSS API client (OpenAI-compatible)."""

import json
from typing import Any, Dict, Optional

from openai import OpenAI
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class AIClient:
    """Synchronous client for GPT-OSS / OpenAI-compatible APIs."""

    def __init__(self, base_url: str, api_key: str, model: str = "gpt-oss", timeout: int = 120):
        """
        Initialize AI client.

        Args:
            base_url: API base URL
            api_key:  API authentication key
            model:    Model name
            timeout:  Request timeout in seconds
        """
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.timeout = timeout
        self.token_usage = 0
        self.api_calls = 0
        logger.info(f"AI client initialized — model: {model}")

    def complete(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Synchronous chat completion.

        Args:
            prompt:      User prompt text
            temperature: Sampling temperature
            max_tokens:  Optional response length cap

        Returns:
            AI response string
        """
        try:
            kwargs: Dict[str, Any] = dict(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
            if max_tokens:
                kwargs["max_tokens"] = max_tokens

            response = self.client.chat.completions.create(**kwargs)

            message = response.choices[0].message
            content = getattr(message, 'content', None) or getattr(message, 'reasoning_content', None)

            if not content:
                raise ValueError("No content in AI response")

            if response.usage:
                self.token_usage += response.usage.total_tokens or 0
            self.api_calls += 1

            logger.debug(f"AI completion: {len(content)} chars")
            return content

        except Exception as e:
            logger.error(f"AI completion failed: {e}")
            raise

    def complete_json(self, prompt: str, temperature: float = 0.2) -> Dict[str, Any]:
        """
        Chat completion that forces JSON output.

        Args:
            prompt:      User prompt (should explicitly request JSON)
            temperature: Sampling temperature (low for consistency)

        Returns:
            Parsed JSON as dictionary
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                response_format={"type": "json_object"},
            )

            message = response.choices[0].message
            content = getattr(message, 'content', None) or getattr(message, 'reasoning_content', None)

            if not content:
                raise ValueError("No content in AI response")

            if response.usage:
                self.token_usage += response.usage.total_tokens or 0
            self.api_calls += 1

            return json.loads(content)

        except Exception as e:
            logger.error(f"AI JSON completion failed: {e}")
            raise

    def complete_with_system(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Chat completion with a separate system instruction.

        Args:
            system_prompt: System role instruction
            user_prompt:   User message
            temperature:   Sampling temperature
            max_tokens:    Optional response length cap

        Returns:
            AI response string
        """
        try:
            kwargs: Dict[str, Any] = dict(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )
            if max_tokens:
                kwargs["max_tokens"] = max_tokens

            response = self.client.chat.completions.create(**kwargs)

            message = response.choices[0].message
            content = getattr(message, 'content', None) or getattr(message, 'reasoning_content', None)

            if not content:
                raise ValueError("No content in AI response")

            if response.usage:
                self.token_usage += response.usage.total_tokens or 0
            self.api_calls += 1

            logger.debug(f"AI completion (with system): {len(content)} chars")
            return content

        except Exception as e:
            logger.error(f"AI completion with system failed: {e}")
            raise
