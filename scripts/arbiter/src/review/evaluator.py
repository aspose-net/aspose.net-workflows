"""AI-powered content evaluation for PR review."""

import json
from typing import Any, Dict, Optional

from src.ai.client import AIClient
from src.config.loader import load_prompt
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Fallback result when AI evaluation is unavailable
_FALLBACK_RESULT: Dict[str, Any] = {
    'score': 0,
    'technical_accuracy': 0,
    'clarity': 0,
    'seo_quality': 0,
    'actionability': 0,
    'uniqueness': 0,
    'summary': 'AI evaluation unavailable.',
    'strengths': [],
    'issues': ['AI evaluation could not be completed.'],
    'recommendation': 'REQUEST_CHANGES',
}


def evaluate_content(
    content: str,
    ai_client: AIClient,
    prompt_path: str,
    checklist_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Ask the AI to evaluate a single Markdown article and return a structured result.

    The AI score (0-100) is scaled by the ai_evaluation.weight from the checklist
    to produce a contribution of 0..weight points added to the static score.

    Args:
        content:          Full Markdown content of an English tutorial file
        ai_client:        Initialised AIClient instance
        prompt_path:      Path to the review_pr.txt prompt template
        checklist_config: Parsed checklist dict (for ai_evaluation settings)

    Returns:
        Dict with keys: score, technical_accuracy, clarity, seo_quality,
        actionability, uniqueness, summary, strengths, issues, recommendation
        Plus 'weighted_contribution' (int) ready to add to the static score.
    """
    ai_cfg = checklist_config.get('ai_evaluation', {})
    if not ai_cfg.get('enabled', True):
        logger.info("AI evaluation is disabled in checklist config")
        result = dict(_FALLBACK_RESULT)
        result['weighted_contribution'] = 0
        return result

    weight = ai_cfg.get('weight', 20)
    temperature = ai_cfg.get('temperature', 0.2)

    # Truncate very long articles to avoid token limits (~4000 chars ≈ 1000 tokens)
    truncated = content[:4000] + '\n...[truncated]' if len(content) > 4000 else content

    try:
        prompt_template = load_prompt(prompt_path)
    except FileNotFoundError as e:
        logger.error(f"Review prompt not found: {e}")
        result = dict(_FALLBACK_RESULT)
        result['weighted_contribution'] = 0
        return result

    prompt = prompt_template.format(content=truncated)

    try:
        raw = ai_client.complete_json(prompt, temperature=temperature)
    except Exception as e:
        logger.error(f"AI evaluation failed: {e}")
        result = dict(_FALLBACK_RESULT)
        result['weighted_contribution'] = 0
        return result

    # Validate and normalise the response
    result = _normalise_ai_result(raw)

    # Scale the 0-100 AI score to the configured weight contribution
    ai_score_0_to_1 = max(0, min(100, result['score'])) / 100.0
    result['weighted_contribution'] = round(ai_score_0_to_1 * weight)

    logger.info(
        f"AI evaluation: score={result['score']}, "
        f"contribution={result['weighted_contribution']}/{weight}, "
        f"recommendation={result['recommendation']}"
    )
    return result


def _normalise_ai_result(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure the AI response has all expected fields with correct types.
    Missing or invalid fields fall back to safe defaults.
    """
    def _int(val: Any, default: int = 0) -> int:
        try:
            return int(val)
        except (TypeError, ValueError):
            return default

    def _list(val: Any) -> list:
        return val if isinstance(val, list) else []

    valid_recommendations = {'APPROVE', 'REQUEST_CHANGES', 'REJECT'}
    recommendation = raw.get('recommendation', 'REQUEST_CHANGES')
    if recommendation not in valid_recommendations:
        recommendation = 'REQUEST_CHANGES'

    return {
        'score':               _int(raw.get('score'), 0),
        'technical_accuracy':  _int(raw.get('technical_accuracy'), 0),
        'clarity':             _int(raw.get('clarity'), 0),
        'seo_quality':         _int(raw.get('seo_quality'), 0),
        'actionability':       _int(raw.get('actionability'), 0),
        'uniqueness':          _int(raw.get('uniqueness'), 0),
        'summary':             str(raw.get('summary', '')),
        'strengths':           _list(raw.get('strengths')),
        'issues':              _list(raw.get('issues')),
        'recommendation':      recommendation,
    }
