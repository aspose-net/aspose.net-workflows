"""Metrics logging for the PR Arbiter agent.

Sends run metrics to the shared Google Apps Script endpoint so that all
Conholdate agents (optimizer, arbiter, …) report into the same dashboard.
"""

from datetime import datetime
from typing import Optional

import requests
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Product key → proper display name (shared with optimizer)
_PRODUCT_MAP = {
    '3d':        'Aspose.3D',
    'barcode':   'Aspose.BarCode',
    'cad':       'Aspose.CAD',
    'cells':     'Aspose.Cells',
    'drawing':   'Aspose.Drawing',
    'email':     'Aspose.Email',
    'gis':       'Aspose.GIS',
    'html':      'Aspose.HTML',
    'imaging':   'Aspose.Imaging',
    'note':      'Aspose.Note',
    'ocr':       'Aspose.OCR',
    'page':      'Aspose.Page',
    'pdf':       'Aspose.PDF',
    'psd':       'Aspose.PSD',
    'slides':    'Aspose.Slides',
    'tasks':     'Aspose.Tasks',
    'tex':       'Aspose.TeX',
    'words':     'Aspose.Words',
    'zip':       'Aspose.ZIP',
    # GroupDocs
    'annotation':  'GroupDocs.Annotation',
    'comparison':  'GroupDocs.Comparison',
    'conversion':  'GroupDocs.Conversion',
    'editor':      'GroupDocs.Editor',
    'merger':      'GroupDocs.Merger',
    'metadata':    'GroupDocs.Metadata',
    'parser':      'GroupDocs.Parser',
    'redaction':   'GroupDocs.Redaction',
    'search':      'GroupDocs.Search',
    'signature':   'GroupDocs.Signature',
    'viewer':      'GroupDocs.Viewer',
    'watermark':   'GroupDocs.Watermark',
    # API Reference (aspose.net-workflows)
    'aspose-net-api': 'Aspose API Reference',
    # SEO (aspose.org-workflows)
    'aspose-org':     'Aspose.org SEO',
}

_GROUPDOCS_KEYS = {
    'annotation', 'comparison', 'conversion', 'editor', 'merger',
    'metadata', 'parser', 'redaction', 'search', 'signature',
    'viewer', 'watermark',
}


def _format_product(key: Optional[str]) -> str:
    if not key:
        return 'All Products'
    return _PRODUCT_MAP.get(key.lower(), f"Aspose.{key.title()}")


def _determine_website(key: Optional[str]) -> str:
    if key and key.lower() in _GROUPDOCS_KEYS:
        return 'groupdocs.com'
    return 'aspose.com'


def _determine_status(succeeded: int, failed: int) -> str:
    if succeeded == 0:
        return 'failure'
    if failed == 0:
        return 'success'
    return 'partial_success'


class MetricsLogger:
    """Sends PR Arbiter run metrics to the shared monitoring endpoint."""

    def __init__(self, config: dict):
        """
        Initialise from the 'metrics' section of config.yaml.

        Args:
            config: Full configuration dictionary (not just the metrics sub-dict)
        """
        metrics_cfg = config.get('metrics', {})
        self.enabled = metrics_cfg.get('enabled', False)
        self.endpoint = metrics_cfg.get('endpoint', '')
        self.token = metrics_cfg.get('token', '')
        self.agent_name = metrics_cfg.get('agent_name', 'Tutorials PR Arbiter')
        self.agent_owner = metrics_cfg.get('agent_owner', 'Unknown')
        self.job_type = metrics_cfg.get('job_type', 'pr_review')
        self.item_name = metrics_cfg.get('item_name', 'Pull Requests')
        self.website_section = metrics_cfg.get('website_section', 'Tutorials')

        if self.enabled:
            logger.info("Metrics logging enabled")
        else:
            logger.debug("Metrics logging disabled")

    # ── Core send method ──────────────────────────────────────────────────────

    def log_run_metrics(
        self,
        run_id: str,
        status: str,
        product: Optional[str] = None,
        platform: str = 'All',
        items_discovered: int = 0,
        items_succeeded: int = 0,
        items_failed: int = 0,
        run_duration_ms: int = 0,
        timestamp: Optional[str] = None,
        token_usage: int = 0,
        api_calls_count: int = 0,
    ) -> bool:
        """
        Send one metrics record to the Google Apps Script endpoint.

        Args:
            run_id:           Unique identifier for this run (e.g. 'arbiter_20260410_143000')
            status:           'success' | 'partial_success' | 'failure'
            product:          Product key (e.g. 'words') or None for an all-products run
            items_discovered: Total PRs found (open PRs matching the branch prefix)
            items_succeeded:  PRs approved
            items_failed:     PRs rejected or errored
            run_duration_ms:  Actual wall-clock duration in milliseconds
            timestamp:        ISO timestamp override (defaults to UTC now)
            token_usage:      Cumulative AI tokens consumed
            api_calls_count:  Cumulative AI API calls made

        Returns:
            True if the HTTP request succeeded (status 200), False otherwise
        """
        if not self.enabled:
            logger.debug("Metrics disabled — skipping")
            return False

        if not self.endpoint or not self.token:
            logger.warning("Metrics endpoint or token not configured — skipping")
            return False

        if timestamp is None:
            timestamp = datetime.utcnow().isoformat()

        payload = {
            'timestamp':        timestamp,
            'agent_name':       self.agent_name,
            'agent_owner':      self.agent_owner,
            'job_type':         self.job_type,
            'run_id':           run_id,
            'status':           status,
            'item_name':        self.item_name,
            'product':          _format_product(product),
            'platform':         platform,
            'website':          _determine_website(product),
            'website_section':  self.website_section,
            'items_discovered': items_discovered,
            'items_succeeded':  items_succeeded,
            'items_failed':     items_failed,
            'run_duration_ms':  run_duration_ms,
            'token_usage':      token_usage,
            'api_calls_count':  api_calls_count,
        }

        try:
            url = f"{self.endpoint}?token={self.token}"
            response = requests.post(
                url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10,
            )

            if response.status_code == 200:
                logger.info(f"Metrics logged for run {run_id} ({status})")
                return True
            else:
                logger.error(
                    f"Metrics HTTP {response.status_code} for run {run_id}: {response.text}"
                )
                return False

        except requests.exceptions.Timeout:
            logger.error("Metrics request timed out")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Metrics request failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected metrics error: {e}")
            return False

    # ── Convenience wrapper ───────────────────────────────────────────────────

    def log_review_run(
        self,
        run_id: str,
        product: Optional[str],
        platform: str,
        files_found: int,
        files_reviewed: int,
        prs_errors: int,
        duration_ms: int,
        token_usage: int = 0,
        api_calls_count: int = 0,
    ) -> bool:
        """
        Convenience wrapper with PR-arbiter-specific argument names.

        items_succeeded = all files where a review was successfully posted,
        regardless of the review decision (approve / request-changes / reject).
        The agent's job is to review — a REQUEST_CHANGES decision is a success,
        not a failure.  Only agent-level exceptions count as items_failed.

        Args:
            run_id:         Unique run identifier
            product:        Product key or None (all products)
            platform:       Platform display string e.g. '.NET' or '.NET, Java'
            files_found:    Total markdown files found across all PRs (items_discovered)
            files_reviewed: Files where a review was successfully posted (items_succeeded)
            prs_errors:     PRs that raised exceptions (items_failed)
            duration_ms:    Actual wall-clock duration in milliseconds
            token_usage:    AI tokens consumed
            api_calls_count: AI API calls made

        Returns:
            True if metrics were posted successfully
        """
        status = _determine_status(files_reviewed, prs_errors)

        return self.log_run_metrics(
            run_id=run_id,
            status=status,
            product=product,
            platform=platform,
            items_discovered=files_found,
            items_succeeded=files_reviewed,
            items_failed=prs_errors,
            run_duration_ms=duration_ms,
            token_usage=token_usage,
            api_calls_count=api_calls_count,
        )
