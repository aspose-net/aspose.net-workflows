"""
Load and apply static checklist rules against Markdown file content.

Each check in pr_merge_checklist.yaml is evaluated here without calling the AI.
The AI evaluation lives in evaluator.py and contributes a separate score.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

import yaml
from pathlib import Path
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def load_checklist(checklist_path: str) -> Dict[str, Any]:
    """
    Load the YAML checklist definition.

    Args:
        checklist_path: Path to pr_merge_checklist.yaml

    Returns:
        Parsed checklist dict
    """
    path = Path(checklist_path)
    if not path.exists():
        raise FileNotFoundError(f"Checklist not found: {checklist_path}")

    with open(path, 'r', encoding='utf-8') as f:
        checklist = yaml.safe_load(f)

    logger.info(f"Loaded checklist from {checklist_path}: {len(checklist.get('checks', []))} checks")
    return checklist


def run_checks(
    content: str,
    checklist: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Apply every static check to a single Markdown file's content.

    Args:
        content:   Full Markdown file text
        checklist: Parsed checklist dict from load_checklist()
        context:   Optional extra data for diff-aware checks (e.g. {'patch': '...'})

    Returns:
        Tuple of (score, results) where:
          score   - Integer 0..80 (static checks contribute up to 80 pts;
                    the remaining 20 come from AI evaluation)
          results - List of result dicts per check:
                    {'id', 'description', 'passed', 'weight', 'type'}
    """
    checks = checklist.get('checks', [])
    results: List[Dict[str, Any]] = []
    has_required_failure = False
    raw_score = 0

    for check in checks:
        passed = _evaluate_check(check['id'], content, context)
        results.append({
            'id': check['id'],
            'description': check['description'],
            'passed': passed,
            'weight': check['weight'],
            'type': check['type'],
        })

        if passed:
            raw_score += check['weight']
        elif check['type'] == 'required':
            has_required_failure = True
            logger.debug(f"Required check failed: {check['id']}")

    # Cap score at 49 if any required check failed (prevents approval)
    score = min(raw_score, 49) if has_required_failure else raw_score
    logger.debug(f"Static checklist score: {score} (raw: {raw_score})")
    return score, results


# ── Individual check implementations ─────────────────────────────────────────

def _evaluate_check(check_id: str, content: str, context: Optional[Dict[str, Any]] = None) -> bool:
    """Dispatch to the appropriate checker function."""
    # Checks that need context (diff data) in addition to content
    _context_checks = {
        'body_unchanged': _check_body_unchanged,
    }

    dispatcher = {
        'frontmatter_present':        _check_frontmatter_present,
        'frontmatter_has_title':      _check_frontmatter_has_title,
        'frontmatter_has_description':_check_frontmatter_has_description,
        'no_placeholder_text':        _check_no_placeholder_text,
        'content_not_empty':          _check_content_not_empty,
        'hugo_shortcodes_closed':     _check_hugo_shortcodes_closed,
        'no_translation_artifacts':   _check_no_translation_artifacts,
        'headings_translated':        _check_headings_translated,
        'frontmatter_values_safe':    _check_frontmatter_values_safe,
        'frontmatter_has_url':        _check_frontmatter_has_url,
        'adequate_word_count':        _check_adequate_word_count,
        'proper_heading_structure':   _check_proper_heading_structure,
        'seo_keywords_in_title':      _check_seo_keywords_in_title,
        'seo_keywords_in_description':_check_seo_keywords_in_description,
        'code_examples_present':      _check_code_examples_present,
        'internal_links_valid_format':_check_internal_links_valid_format,
        # API docs checks
        'frontmatter_has_layout':     _check_frontmatter_has_layout,
        'frontmatter_has_categories': _check_frontmatter_has_categories,
        'no_broken_html_tags':        _check_no_broken_html_tags,
        'tables_well_formed':         _check_tables_well_formed,
        'no_raw_docfx_artifacts':     _check_no_raw_docfx_artifacts,
        'frontmatter_has_summary':    _check_frontmatter_has_summary,
        'assembly_version_present':   _check_assembly_version_present,
        'internal_links_format':      _check_internal_links_format,
        # SEO checks
        'frontmatter_yaml_valid':     _check_frontmatter_yaml_valid,
        'seo_title_length':           _check_seo_title_length,
        'description_length':         _check_description_length,
        'no_keyword_stuffing':        _check_no_keyword_stuffing,
        'tags_format_valid':          _check_tags_format_valid,
        'tags_relevance':             _check_tags_relevance,
        'seo_title_has_brand':        _check_seo_title_has_brand,
        'description_has_call_to_action': _check_description_has_call_to_action,
    }

    # Context-aware checks
    if check_id in _context_checks:
        try:
            return _context_checks[check_id](content, context or {})
        except Exception as e:
            logger.error(f"Check '{check_id}' raised an error: {e}")
            return False

    checker = dispatcher.get(check_id)
    if checker is None:
        logger.warning(f"No checker implemented for: {check_id}")
        return True  # Unknown checks default to pass

    try:
        return checker(content)
    except Exception as e:
        logger.error(f"Check '{check_id}' raised an error: {e}")
        return False


def _extract_frontmatter(content: str):
    """
    Split content into (frontmatter_text, body_text).
    Returns (None, content) if no frontmatter block is found.
    """
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n?(.*)', content, re.DOTALL)
    if match:
        return match.group(1), match.group(2)
    return None, content


def _check_frontmatter_present(content: str) -> bool:
    fm, _ = _extract_frontmatter(content)
    return fm is not None


def _check_frontmatter_has_title(content: str) -> bool:
    fm, _ = _extract_frontmatter(content)
    if not fm:
        return False
    return bool(re.search(r'^\s*title\s*:\s*.+', fm, re.MULTILINE))


def _check_frontmatter_has_description(content: str) -> bool:
    fm, _ = _extract_frontmatter(content)
    if not fm:
        return False
    match = re.search(r'^\s*description\s*:\s*(.+)', fm, re.MULTILINE)
    if not match:
        return False
    return len(match.group(1).strip().strip('"\'')) >= 50


def _check_no_placeholder_text(content: str) -> bool:
    patterns = [
        r'\bTODO\b', r'\bFIXME\b', r'\[PLACEHOLDER\]',
        r'Lorem ipsum', r'\[INSERT\b',
    ]
    return not any(re.search(p, content, re.IGNORECASE) for p in patterns)


def _check_content_not_empty(content: str) -> bool:
    _, body = _extract_frontmatter(content)
    return len(body.strip()) >= 100


def _check_frontmatter_has_url(content: str) -> bool:
    fm, _ = _extract_frontmatter(content)
    if not fm:
        return False
    return bool(re.search(r'^\s*(url|linktitle)\s*:\s*.+', fm, re.MULTILINE))


def _check_adequate_word_count(content: str) -> bool:
    _, body = _extract_frontmatter(content)
    # Strip Markdown syntax before counting
    plain = re.sub(r'[#*`\[\]()>_~]', ' ', body)
    words = plain.split()
    return len(words) >= 200


def _check_proper_heading_structure(content: str) -> bool:
    _, body = _extract_frontmatter(content)
    return bool(re.search(r'^##\s+', body, re.MULTILINE))


def _check_seo_keywords_in_title(content: str) -> bool:
    fm, _ = _extract_frontmatter(content)
    if not fm:
        return False
    match = re.search(r'^\s*title\s*:\s*(.+)', fm, re.MULTILINE)
    if not match:
        return False
    title = match.group(1).lower()
    # Title should contain at least one action verb or format keyword
    action_patterns = [
        r'\b(convert|create|merge|split|extract|edit|add|remove|insert|format|'
        r'compress|encrypt|sign|watermark|annotate|render|parse|generate|export|'
        r'import|read|write|load|save|open|close|resize|rotate|scan|recognize)\b'
    ]
    return any(re.search(p, title) for p in action_patterns)


def _check_seo_keywords_in_description(content: str) -> bool:
    fm, _ = _extract_frontmatter(content)
    if not fm:
        return False
    match = re.search(r'^\s*description\s*:\s*(.+)', fm, re.MULTILINE)
    if not match:
        return False
    desc = match.group(1).lower()
    # Description should mention at least one product or format
    product_patterns = [
        r'\baspose\b', r'\bgroupdocs\b',
        r'\b(pdf|word|excel|powerpoint|cells|slides|email|html|cad|ocr|barcode)\b',
        r'\b(\.net|java|python|c#)\b',
    ]
    return any(re.search(p, desc, re.IGNORECASE) for p in product_patterns)


def _check_code_examples_present(content: str) -> bool:
    _, body = _extract_frontmatter(content)
    return bool(re.search(r'```', body))


def _check_hugo_shortcodes_closed(content: str) -> bool:
    """
    Ensure no meaningful content appears after the last closing
    {{< /blocks/products/pf/main-wrap-class >}} tag.
    Content leaking outside the tag breaks the Hugo page layout.
    The back-to-top button shortcode is allowed after the closing tag.
    """
    _, body = _extract_frontmatter(content)

    close_re = re.compile(
        r'\{\{<\s*/blocks/products/pf/main-wrap-class\s*>\}\}', re.IGNORECASE
    )
    matches = list(close_re.finditer(body))
    if not matches:
        return True  # No shortcodes used — not applicable

    after = body[matches[-1].end():]
    # Strip the back-to-top button shortcode and any whitespace
    after = re.sub(
        r'\{\{<\s*blocks/products/products-backtop-button\s*>\}\}', '', after
    )
    return len(after.strip()) == 0


def _check_no_translation_artifacts(content: str) -> bool:
    """
    Ensure no LLM reasoning text or draft notes appear before the first
    Hugo shortcode tag ({{< blocks/products/pf/main-wrap-class >}}).
    Translators sometimes leave internal monologue in the output.
    """
    _, body = _extract_frontmatter(content)

    open_re = re.compile(
        r'\{\{<\s*blocks/products/pf/main-wrap-class\s*>\}\}', re.IGNORECASE
    )
    first = open_re.search(body)
    if not first:
        return True  # No shortcodes — not applicable

    before = body[:first.start()].strip()
    return len(before) == 0


def _check_headings_translated(content: str) -> bool:
    """
    For translated files (detected by significant non-ASCII body text),
    verify that headings are also translated and not left in English.
    A file is considered a translation when > 5 % of non-whitespace
    characters are non-ASCII.  All-ASCII headings in such a file signal
    that the translator forgot to translate the section titles.
    """
    _, body = _extract_frontmatter(content)

    # Strip code blocks and shortcodes before measuring language
    clean = re.sub(r'```.*?```', '', body, flags=re.DOTALL)
    clean = re.sub(r'\{\{<.*?>\}\}', '', clean)

    non_ws = [c for c in clean if not c.isspace()]
    if not non_ws:
        return True

    non_ascii = sum(1 for c in non_ws if ord(c) > 127)
    if non_ascii / len(non_ws) < 0.05:
        return True  # Likely an English file — check not applicable

    # File is a translation: at least some headings must contain non-ASCII
    headings = re.findall(r'^#{1,6}\s+(.+)', body, re.MULTILINE)
    if not headings:
        return True

    heading_text = ' '.join(headings)
    return any(ord(c) > 127 for c in heading_text)


def _check_frontmatter_values_safe(content: str) -> bool:
    """
    Detect unquoted frontmatter values that contain a colon.
    An unquoted colon in a YAML value (e.g.  title: Guide: Part 2)
    breaks the Hugo build process.  Values must be wrapped in quotes.
    """
    fm, _ = _extract_frontmatter(content)
    if not fm:
        return True

    for line in fm.splitlines():
        # Match  key: value  lines (skip blank / comment / continuation lines)
        m = re.match(r'^\s*[\w][\w-]*\s*:\s*(.+)$', line)
        if not m:
            continue
        value = m.group(1).strip()
        # Already quoted → safe
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            continue
        # Unquoted value with a colon → unsafe
        if ':' in value:
            return False
    return True


def _check_internal_links_valid_format(content: str) -> bool:
    _, body = _extract_frontmatter(content)
    # If no internal links exist, pass by default
    raw_links = re.findall(r'\[.*?\]\(((?!http)[^)]+)\)', body)
    if not raw_links:
        return True
    # Links should be relative paths or Hugo relref shortcodes
    hugo_relref = re.search(r'\{\{<\s*relref\s+', body)
    return hugo_relref is not None or all(
        link.startswith('/') or link.startswith('../') or link.endswith('.md')
        for link in raw_links
    )


# ── API docs checks ──────────────────────────────────────────────────────────

def _check_frontmatter_has_layout(content: str) -> bool:
    """Frontmatter must contain a ``layout`` field."""
    fm, _ = _extract_frontmatter(content)
    if not fm:
        return False
    return bool(re.search(r'^\s*layout\s*:\s*.+', fm, re.MULTILINE))


def _check_frontmatter_has_categories(content: str) -> bool:
    """Frontmatter must contain a ``categories`` field."""
    fm, _ = _extract_frontmatter(content)
    if not fm:
        return False
    return bool(re.search(r'^\s*categories\s*:', fm, re.MULTILINE))


def _check_no_broken_html_tags(content: str) -> bool:
    """No unclosed HTML tags (``<xref>``, ``<pre>``, ``<code>``) in the body."""
    _, body = _extract_frontmatter(content)
    for tag in ('xref', 'pre', 'code'):
        opens = len(re.findall(rf'<{tag}[\s>]', body, re.IGNORECASE))
        closes = len(re.findall(rf'</{tag}\s*>', body, re.IGNORECASE))
        if opens > closes:
            return False
    return True


def _check_tables_well_formed(content: str) -> bool:
    """Markdown tables must have consistent column counts across rows."""
    _, body = _extract_frontmatter(content)
    table_rows = re.findall(r'^\|.+\|$', body, re.MULTILINE)
    if not table_rows:
        return True  # No tables — pass
    # Group consecutive table rows
    i = 0
    while i < len(table_rows):
        first_cols = table_rows[i].count('|') - 1
        i += 1
        while i < len(table_rows):
            cols = table_rows[i].count('|') - 1
            if cols != first_cols:
                return False
            i += 1
    return True


def _check_no_raw_docfx_artifacts(content: str) -> bool:
    """No raw DocFX artifacts (``<xref:...>``, ``uid:`` references) in the body."""
    _, body = _extract_frontmatter(content)
    if re.search(r'<xref:', body):
        return False
    # Raw uid: lines outside frontmatter
    if re.search(r'^\s*uid\s*:', body, re.MULTILINE):
        return False
    return True


def _check_frontmatter_has_summary(content: str) -> bool:
    """Frontmatter must contain a non-empty ``summary`` field."""
    fm, _ = _extract_frontmatter(content)
    if not fm:
        return False
    match = re.search(r'^\s*summary\s*:\s*(.+)', fm, re.MULTILINE)
    return bool(match and match.group(1).strip())


def _check_assembly_version_present(content: str) -> bool:
    """Body should reference an assembly version (e.g. ``Assembly: Aspose.Words.dll``)."""
    _, body = _extract_frontmatter(content)
    return bool(re.search(r'Assembly\s*:.*\.dll', body, re.IGNORECASE))


def _check_internal_links_format(content: str) -> bool:
    """Internal links should use path format (``/family/...``), not ``.md`` extensions."""
    _, body = _extract_frontmatter(content)
    internal_links = re.findall(r'\[.*?\]\(((?!http)[^)]+)\)', body)
    if not internal_links:
        return True
    # Fail if any internal link ends with .md (should use clean URLs)
    return not any(link.endswith('.md') for link in internal_links)


# ── SEO checks ────────────────────────────────────────────────────────────────

def _check_frontmatter_yaml_valid(content: str) -> bool:
    """Frontmatter YAML must parse without errors."""
    fm, _ = _extract_frontmatter(content)
    if fm is None:
        return False
    try:
        yaml.safe_load(fm)
        return True
    except yaml.YAMLError:
        return False


def _check_seo_title_length(content: str) -> bool:
    """``seoTitle`` field must be 30-60 characters."""
    fm, _ = _extract_frontmatter(content)
    if not fm:
        return False
    match = re.search(r'^\s*seoTitle\s*:\s*(.+)', fm, re.MULTILINE)
    if not match:
        return False
    title = match.group(1).strip().strip('"\'')
    return 30 <= len(title) <= 60


def _check_description_length(content: str) -> bool:
    """``description`` field must be 50-160 characters (optimal for meta descriptions)."""
    fm, _ = _extract_frontmatter(content)
    if not fm:
        return False
    match = re.search(r'^\s*description\s*:\s*(.+)', fm, re.MULTILINE)
    if not match:
        return False
    desc = match.group(1).strip().strip('"\'')
    return 50 <= len(desc) <= 160


def _check_body_unchanged(content: str, context: Dict[str, Any]) -> bool:
    """Only frontmatter should be modified — body content must remain untouched.

    Uses the unified diff (patch) from context to verify that all changed
    lines fall within the frontmatter block.
    """
    patch = context.get('patch', '')
    if not patch:
        return True  # No diff available — assume pass

    # Find the closing --- line number in the content
    lines = content.splitlines()
    fm_end_line = None
    in_frontmatter = False
    for i, line in enumerate(lines, start=1):
        if i == 1 and line.strip() == '---':
            in_frontmatter = True
            continue
        if in_frontmatter and line.strip() == '---':
            fm_end_line = i
            break

    if fm_end_line is None:
        return False  # No frontmatter found — any change is body change

    # Parse the unified diff for changed line numbers
    for hunk_match in re.finditer(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', patch, re.MULTILINE):
        start = int(hunk_match.group(1))
        count = int(hunk_match.group(2)) if hunk_match.group(2) else 1
        # If any hunk touches lines after frontmatter, body was modified
        if start + count - 1 > fm_end_line:
            return False

    return True


def _check_no_keyword_stuffing(content: str) -> bool:
    """``seoTitle`` and ``description`` should not repeat any word more than twice."""
    fm, _ = _extract_frontmatter(content)
    if not fm:
        return True
    # Combine seoTitle and description text
    texts = []
    for field in ('seoTitle', 'description'):
        match = re.search(rf'^\s*{field}\s*:\s*(.+)', fm, re.MULTILINE)
        if match:
            texts.append(match.group(1).strip().strip('"\'').lower())
    combined = ' '.join(texts)
    # Tokenize and count (skip short stop words)
    words = re.findall(r'\b[a-z]{4,}\b', combined)
    counts: Dict[str, int] = {}
    for w in words:
        counts[w] = counts.get(w, 0) + 1
    return all(c <= 2 for c in counts.values())


def _check_tags_format_valid(content: str) -> bool:
    """``tags`` field must be a YAML list of 3-10 lowercase hyphenated entries."""
    fm, _ = _extract_frontmatter(content)
    if not fm:
        return True  # No frontmatter — not applicable
    try:
        data = yaml.safe_load(fm)
    except yaml.YAMLError:
        return False
    if not isinstance(data, dict):
        return True
    tags = data.get('tags')
    if tags is None:
        return True  # No tags field — not applicable
    if not isinstance(tags, list):
        return False
    if not (3 <= len(tags) <= 10):
        return False
    return all(
        isinstance(t, str) and re.match(r'^[a-z0-9][a-z0-9-]*$', t)
        for t in tags
    )


def _check_tags_relevance(content: str) -> bool:
    """Tags should include at least one product name and one action/format keyword."""
    fm, _ = _extract_frontmatter(content)
    if not fm:
        return True
    try:
        data = yaml.safe_load(fm)
    except yaml.YAMLError:
        return True
    if not isinstance(data, dict):
        return True
    tags = data.get('tags')
    if not tags or not isinstance(tags, list):
        return True
    tag_str = ' '.join(str(t).lower() for t in tags)
    has_product = bool(re.search(r'aspose|groupdocs', tag_str))
    has_action = bool(re.search(
        r'convert|merge|split|edit|create|parse|render|export|import|compress|'
        r'pdf|word|excel|html|image|barcode|ocr|email|slide|cell', tag_str
    ))
    return has_product and has_action


def _check_seo_title_has_brand(content: str) -> bool:
    """``seoTitle`` should mention the product name (Aspose.*, GroupDocs.*)."""
    fm, _ = _extract_frontmatter(content)
    if not fm:
        return False
    match = re.search(r'^\s*seoTitle\s*:\s*(.+)', fm, re.MULTILINE)
    if not match:
        return False
    title = match.group(1).strip().lower()
    return bool(re.search(r'aspose|groupdocs', title))


def _check_description_has_call_to_action(content: str) -> bool:
    """``description`` should contain an action verb (learn, discover, convert, etc.)."""
    fm, _ = _extract_frontmatter(content)
    if not fm:
        return False
    match = re.search(r'^\s*description\s*:\s*(.+)', fm, re.MULTILINE)
    if not match:
        return False
    desc = match.group(1).strip().lower()
    return bool(re.search(
        r'\b(learn|discover|convert|create|merge|split|edit|manage|generate|'
        r'extract|process|automate|optimize|explore|master|implement|build|'
        r'add|remove|read|write|parse|render|export|import)\b', desc
    ))
