# API Docs PR Arbiter — Setup & Execution Guide

This document provides everything needed to operate, configure, and troubleshoot the PR Arbiter deployed in this repository. It reviews pull requests created by the API reference documentation pipeline against `Aspose/aspose.net`.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Pipeline Flow](#pipeline-flow)
- [Scoring System](#scoring-system)
- [Static Checklist](#static-checklist)
- [AI Evaluation](#ai-evaluation)
- [Configuration Reference](#configuration-reference)
- [Secrets & Environment Variables](#secrets--environment-variables)
- [GitHub Workflow](#github-workflow)
- [State Management](#state-management)
- [Metrics & Monitoring](#metrics--monitoring)
- [CLI Reference](#cli-reference)
- [Module Reference](#module-reference)
- [Troubleshooting](#troubleshooting)
- [Customization Guide](#customization-guide)

---

## Overview

The **API Docs PR Arbiter** is an automated GitHub PR review system. When the reference documentation pipeline (`scripts/reference/`) generates API docs and pushes them to `Aspose/aspose.net` via `push_to_repo.py`, the resulting PRs have no quality gate. This arbiter fills that gap.

**What it does:**
1. Finds open PRs on `Aspose/aspose.net` matching branch prefix `api-update-`
2. Evaluates every changed `.md` file against 13 static quality checks
3. Optionally runs AI evaluation for nuanced content quality assessment
4. Posts a scored GitHub review (APPROVE / REQUEST_CHANGES / REJECT) directly on the PR
5. Reports metrics to the shared Google Apps Script dashboard
6. Persists review state to avoid duplicate reviews

**Where results appear:**
- GitHub PR review comment on `Aspose/aspose.net`
- Google Apps Script dashboard (shared with tutorials arbiter)
- Runner logs (ephemeral)

---

## Architecture

```
aspose.net-workflows/
├── .github/workflows/
│   └── pr-review.yml          ← GitHub Actions workflow
├── scripts/arbiter/
│   ├── src/                   ← Arbiter engine (self-contained)
│   │   ├── main.py            ← Entry point & orchestrator
│   │   ├── ai/client.py       ← OpenAI-compatible LLM client
│   │   ├── config/            ← Config loader + validator
│   │   ├── github/            ← PR fetching, reviewing, merging
│   │   ├── review/            ← Checklist, decision, AI evaluator
│   │   ├── state/             ← TinyDB persistence
│   │   └── utils/             ← Logging + metrics
│   ├── config/
│   │   ├── config.yaml        ← Runtime configuration
│   │   ├── checklist.yaml     ← Quality check definitions
│   │   └── prompts/
│   │       └── review.txt     ← AI evaluation prompt template
│   ├── data/                  ← Runtime state (gitignored)
│   │   └── state.json         ← TinyDB review history
│   └── requirements.txt       ← Python dependencies
```

The engine is a complete copy of the tutorials-pr-arbiter reference implementation with API-docs-specific configuration. It runs entirely within this repo — no cross-repo dependencies at runtime.

---

## Pipeline Flow

```
Reference Doc Pipeline                        PR Arbiter
┌─────────────────────┐                  ┌──────────────────────┐
│ check_versions.py   │                  │                      │
│ detect_updates.py   │                  │  1. Fetch open PRs   │
│ extract_files.py    │                  │     (api-update-*)   │
│ generate_docfx.py   │──→ PR on ──→    │                      │
│ postprocessor.py    │   aspose.net     │  2. Run 13 static    │
│ push_to_repo.py     │                  │     quality checks   │
└─────────────────────┘                  │                      │
                                         │  3. Run AI eval      │
                                         │     (if enabled)     │
                                         │                      │
                                         │  4. Post review      │
                                         │     on GitHub PR     │
                                         │                      │
                                         │  5. Report metrics   │
                                         └──────────────────────┘
```

### Step-by-Step Execution

1. **Load config** — Read `config/config.yaml`, substitute `${VAR}` with environment variables
2. **Validate** — Ensure GitHub token, GPT-OSS credentials, product config all present
3. **Fetch PRs** — Query `Aspose/aspose.net` for open PRs with branches starting with `api-update-`
4. **Deduplicate** — Check TinyDB state; skip PRs already reviewed
5. **For each PR:**
   a. Get list of changed files
   b. Filter to `.md` files (no path restriction — reviews all markdown)
   c. Detect platform from path segments (`.NET`, `Java`, `Python`, etc.)
   d. For each file:
      - Run static checklist → score (0–80) + check results
      - Run AI evaluation → score (0–100), scaled to 0–20 contribution
   e. Aggregate: average scores across files
   f. If ANY required check failed in ANY file → cap static score at 49
   g. Combine: `total = min(100, avg_static + avg_ai_contribution)`
   h. Decision: ≥70 = APPROVE, 40–69 = REQUEST_CHANGES, <40 = REJECT
   i. Post GitHub review with detailed Markdown comment
   j. Add labels (`arbiter:approved`, `arbiter:needs-changes`, `arbiter:rejected`)
   k. Save review to TinyDB
6. **Report metrics** — POST to Google Apps Script endpoint

---

## Scoring System

### Score Composition

| Component | Max Points | Source |
|-----------|-----------|--------|
| Static checklist | 80 | 13 checks with configured weights |
| AI evaluation | 20 | LLM score (0–100) scaled by weight |
| **Total** | **100** | `min(100, static + ai)` |

### Decision Thresholds

| Score Range | Decision | GitHub Review Event |
|-------------|----------|-------------------|
| ≥ 70 | APPROVE | `APPROVE` |
| 40–69 | REQUEST_CHANGES | `REQUEST_CHANGES` |
| < 40 | REJECT | `REQUEST_CHANGES` (GitHub doesn't allow REJECT) |

### Required Check Cap

If **any** required check fails in **any** file in the PR, the static score is capped at **49 out of 80**. This ensures that a PR with structural problems (missing frontmatter, broken HTML, DocFX artifacts) can never be approved regardless of how well other files score.

---

## Static Checklist

Defined in `config/checklist.yaml`. Each check has an `id`, `description`, `weight`, and `type`.

### Required Checks (failure → score capped at 49)

| ID | Description | Weight |
|----|-------------|--------|
| `frontmatter_present` | YAML frontmatter block (`---...---`) exists | 10 |
| `frontmatter_has_title` | Non-empty `title` field in frontmatter | 10 |
| `frontmatter_has_layout` | `layout` field present (e.g., `reference-single`) | 10 |
| `frontmatter_has_categories` | `categories` field present | 5 |
| `no_broken_html_tags` | No unclosed `<xref>`, `<pre>`, `<code>` tags | 15 |
| `tables_well_formed` | Markdown tables have consistent column counts | 10 |
| `no_raw_docfx_artifacts` | No raw DocFX artifacts (`<xref:...>`, `uid:` refs) | 10 |

**Required total weight: 70 points**

### Recommended Checks (improve score, don't block)

| ID | Description | Weight |
|----|-------------|--------|
| `frontmatter_has_description` | `description` field ≥ 30 characters | 5 |
| `frontmatter_has_summary` | Non-empty `summary` field | 5 |
| `code_examples_present` | At least one fenced code block | 5 |
| `assembly_version_present` | References assembly version (`Assembly: *.dll`) | 5 |
| `internal_links_format` | Internal links use path format, not `.md` extensions | 5 |
| `content_not_empty` | Body content ≥ 50 characters | 5 |

**Recommended total weight: 30 points**

### How Checks Map to Functions

Each `id` in `checklist.yaml` maps to a `_check_{id}` function in `src/review/checklist.py`. The dispatcher in `_evaluate_check()` calls the matching function. To add a new check:

1. Add entry to `checklist.yaml`
2. Add `_check_{id}(content, context)` function to `checklist.py`
3. Register in the dispatcher dict inside `_evaluate_check()`

---

## AI Evaluation

**Currently disabled** (`ai_evaluation.enabled: false` in `checklist.yaml`). When enabled:

### How It Works

1. File content truncated to 4000 characters
2. Prompt template (`config/prompts/review.txt`) populated with content
3. Sent to GPT-OSS (`gpt-4o-mini`) at temperature 0.2
4. Response parsed as JSON with structured scores

### AI Scoring Criteria

| Criterion | Max | Description |
|-----------|-----|-------------|
| `technical_accuracy` | 25 | Type names, signatures, descriptions accurate? |
| `clarity` | 20 | Tables, code examples, sections properly formatted? |
| `seo_quality` | 20 | Title and description reflect API element? |
| `actionability` | 20 | Can developers understand the API from this? |
| `uniqueness` | 15 | Description meaningful beyond type/member name? |

### AI Score Scaling

Raw AI score (0–100) is scaled by configured weight:

```
weighted_contribution = round((ai_score / 100) × 20) = 0–20 points
```

### Enabling AI Evaluation

In `config/checklist.yaml`, change:

```yaml
ai_evaluation:
  enabled: true    # ← change from false
  weight: 20
  temperature: 0.2
```

Ensure `GPT_OSS_ENDPOINT` and `GPT_OSS_API_KEY` secrets are configured.

---

## Configuration Reference

### config/config.yaml

```yaml
github:
  token: "${GITHUB_TOKEN}"           # Resolved from env var at runtime

metrics:
  enabled: true
  endpoint: "https://script.google.com/macros/s/AKfycby.../exec"
  token: "lM6iU2mW0gV1eZ"           # Dashboard auth token (not a secret)
  agent_name: "API Docs PR Arbiter"  # Distinguishes from other arbiters
  agent_owner: "Muhammad Muqarrab"
  job_type: "pr_review"
  item_name: "Pull Requests"
  website_section: "API Reference"

gpt_oss:
  endpoint: "${GPT_OSS_ENDPOINT}"    # Resolved from env var
  api_key: "${GPT_OSS_API_KEY}"      # Resolved from env var
  model: "gpt-4o-mini"
  timeout: 120                       # Seconds

review:
  checklist_path: "config/checklist.yaml"
  pr_branch_prefix: "api-update-"    # Only review PRs from these branches
  auto_merge: false                  # Do not auto-merge approved PRs
  pr_labels: []                      # No label filter
  post_review_comment: true          # Post detailed review comment
  score_thresholds:
    approve: 70                      # Score >= 70 → APPROVE
    request_changes: 40              # Score 40–69 → REQUEST_CHANGES
  file_filter:
    path_contains: null              # Review ALL .md files (no path filter)

products:
  aspose-net-api:
    content_repo: "https://github.com/Aspose/aspose.net"
    branch: "main"

prompts:
  review_pr: "config/prompts/review.txt"

monitoring:
  check_interval_hours: 4
  stale_review_hours: 48

logging:
  level: "INFO"
  dir: "logs"
  rotation: "daily"
```

### Environment Variable Substitution

The config loader (`src/config/loader.py`) recursively replaces `${VAR_NAME}` patterns with `os.getenv('VAR_NAME')`. This happens at load time before any validation.

---

## Secrets & Environment Variables

### Required Secrets (GitHub Actions)

| Secret | Env Var in Workflow | Purpose |
|--------|-------------------|---------|
| `REPO_TOKEN` | `GITHUB_TOKEN` | GitHub PAT with `repo` scope on `Aspose/aspose.net`. Used for: fetching PRs, reading file content, posting reviews, adding labels |
| `GPT_OSS_ENDPOINT` | `GPT_OSS_ENDPOINT` | LLM API endpoint URL (e.g., `https://your-endpoint.openai.azure.com/`) |
| `GPT_OSS_API_KEY` | `GPT_OSS_API_KEY` | LLM API authentication key |

### Token Permissions

The `REPO_TOKEN` must have:
- `repo` scope (read + write access to `Aspose/aspose.net`)
- Ability to: list PRs, read file content, create reviews, add labels
- If auto-merge enabled: merge permissions

### Adding Secrets

1. Go to **aspose.net-workflows** repo → Settings → Secrets and variables → Actions
2. Add each secret with the exact name listed above
3. The workflow maps them to env vars:
   ```yaml
   env:
     GITHUB_TOKEN: ${{ secrets.REPO_TOKEN }}
     GPT_OSS_ENDPOINT: ${{ secrets.GPT_OSS_ENDPOINT }}
     GPT_OSS_API_KEY: ${{ secrets.GPT_OSS_API_KEY }}
   ```

---

## GitHub Workflow

### File: `.github/workflows/pr-review.yml`

```yaml
name: API Docs PR Review
on:
  workflow_dispatch:
    inputs:
      max_prs:
        description: "Max PRs to review"
        default: "1"
```

### Trigger Options

| Method | How |
|--------|-----|
| **Manual** | Actions tab → "API Docs PR Review" → Run workflow → set max_prs |
| **After pipeline** | Add `gh workflow run pr-review.yml` to `push_to_repo.py` after PR creation |
| **On schedule** | Add a `schedule:` trigger (e.g., `cron: '0 */4 * * *'` for every 4 hours) |
| **On PR creation** | Add `workflow_run:` trigger watching the reference doc pipeline workflow |

### Execution Details

- **Runner:** `ubuntu-latest`
- **Timeout:** 30 minutes
- **Working directory:** `scripts/arbiter` (all paths resolve relative to here)
- **Python:** 3.11
- **State caching:** `data/state.json` cached with key `arbiter-state-{branch}`

### Adding Automatic Trigger

To run automatically after the reference doc pipeline, add to the workflow:

```yaml
on:
  workflow_dispatch:
    inputs:
      max_prs:
        description: "Max PRs to review"
        default: "1"
  workflow_run:
    workflows: ["Translator"]   # or whatever the pipeline workflow is named
    types: [completed]
```

Or add to `push_to_repo.py` after PR creation:

```python
import subprocess, os
subprocess.run([
    "gh", "workflow", "run", "pr-review.yml",
    "--repo", "Aspose/aspose.net-workflows",
], check=False, env={**os.environ, "GH_TOKEN": GITHUB_TOKEN})
```

---

## State Management

### TinyDB (data/state.json)

Review history is persisted in a lightweight JSON database via TinyDB.

**Schema:**

| Field | Type | Description |
|-------|------|-------------|
| `repo_url` | string | Full GitHub repo URL |
| `pr_number` | int | PR number |
| `product` | string | Product key (e.g., `aspose-net-api`) |
| `decision` | string | `APPROVE` / `REQUEST_CHANGES` / `REJECT` |
| `score` | int | Final composite score (0–100) |
| `reviewed_at` | string | ISO timestamp of review |
| `pr_updated_at` | string | PR's `updated_at` at time of review |

**Behavior:**
- PRs are skipped permanently once reviewed (no re-review on update)
- Upsert logic: if PR already in DB, record is updated
- State file cached via GitHub Actions cache across workflow runs

### Cache Key

```yaml
key: arbiter-state-${{ github.ref_name }}
restore-keys: arbiter-state-
```

This means state persists across runs on the same branch. If cache is lost, the arbiter will re-review all open PRs (harmless — just posts duplicate reviews).

### Resetting State

To force re-review of all PRs:
1. Delete the cache entry from Actions → Caches
2. Or manually delete `data/state.json` before running

---

## Metrics & Monitoring

### Google Apps Script Dashboard

Metrics are POSTed to a shared Google Apps Script endpoint after each run.

**Endpoint:** `https://script.google.com/macros/s/AKfycbyCHwElrM6RcYLi0JNQAkJmzGrBjAhf28mKXVyub_6SdaZ2ITvzCwfM5xCLE7rmuxio/exec`

**Payload fields:**

| Field | Value |
|-------|-------|
| `agent_name` | "API Docs PR Arbiter" |
| `agent_owner` | "Muhammad Muqarrab" |
| `job_type` | "pr_review" |
| `product` | "Aspose API Reference" |
| `platform` | Detected from file paths |
| `status` | "success" / "partial_success" / "failure" |
| `items_discovered` | Files found |
| `items_succeeded` | Files reviewed successfully |
| `items_failed` | Errors |
| `run_duration_ms` | Execution time |
| `token_usage` | LLM tokens consumed |
| `api_calls_count` | LLM API calls made |

### Distinguishing From Other Arbiters

Three arbiter instances report to the same dashboard:

| Agent Name | Website Section | Repo |
|------------|----------------|------|
| Tutorials PR Arbiter | Tutorials | tutorials-pr-arbiter |
| **API Docs PR Arbiter** | **API Reference** | **aspose.net-workflows** |
| SEO PR Arbiter | SEO | aspose.org-workflows |

---

## CLI Reference

```bash
# Run from scripts/arbiter/ directory
python -m src.main [OPTIONS]
```

### Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--config`, `-c` | `config/config.yaml` | Path to config file |
| `--product`, `-p` | All products | Single product key to review |
| `--max-prs`, `-n` | Unlimited | Max PRs to review per run |

### Examples

```bash
# Review 1 PR (default workflow behavior)
python -m src.main -p aspose-net-api -n 1

# Review all open PRs
python -m src.main -p aspose-net-api

# Use custom config
python -m src.main -c config/custom.yaml -p aspose-net-api -n 3

# Dry run locally (set env vars first)
export GITHUB_TOKEN="ghp_..."
export GPT_OSS_ENDPOINT="https://..."
export GPT_OSS_API_KEY="sk-..."
python -m src.main -p aspose-net-api -n 1
```

---

## Module Reference

| Module | File | Responsibility |
|--------|------|---------------|
| **PRArbitrAgent** | `src/main.py` | Orchestrates entire review pipeline |
| **AIClient** | `src/ai/client.py` | OpenAI-compatible LLM client (GPT-OSS) |
| **load_config** | `src/config/loader.py` | YAML loading + `${VAR}` substitution |
| **validate_config** | `src/config/validator.py` | Config structure validation |
| **fetch_open_prs** | `src/github/pr_fetcher.py` | Query open PRs by branch prefix |
| **get_pr_files** | `src/github/pr_fetcher.py` | List changed files with patches |
| **get_english_markdown_files** | `src/github/pr_fetcher.py` | Filter to .md files |
| **get_file_content** | `src/github/pr_fetcher.py` | Fetch file at specific SHA |
| **post_review** | `src/github/pr_reviewer.py` | Submit GitHub review event |
| **add_labels** | `src/github/pr_reviewer.py` | Apply labels to PR |
| **merge_pr** | `src/github/pr_reviewer.py` | Squash merge (if enabled) |
| **GitHubClient** | `src/github/client.py` | PyGithub wrapper |
| **load_checklist** | `src/review/checklist.py` | Parse checklist YAML |
| **run_checks** | `src/review/checklist.py` | Execute all static checks |
| **make_decision** | `src/review/decision.py` | Score → decision mapping |
| **build_review_comment** | `src/review/decision.py` | Generate Markdown review body |
| **evaluate_content** | `src/review/evaluator.py` | AI evaluation orchestrator |
| **StateRepository** | `src/state/repository.py` | TinyDB review history |
| **MetricsLogger** | `src/utils/metrics_logger.py` | Google Apps Script reporter |
| **setup_logger** | `src/utils/logger.py` | File + console logging |

---

## Troubleshooting

### Common Issues

**"Config validation failed: GitHub token appears to be a placeholder"**
- `GITHUB_TOKEN` env var not set or `REPO_TOKEN` secret missing
- Check: Actions → Settings → Secrets

**"No open PRs found matching prefix 'api-update-'"**
- No PRs exist on `Aspose/aspose.net` with `api-update-*` branches
- Or all matching PRs already reviewed (check state cache)

**"AI evaluation failed, using fallback"**
- GPT-OSS endpoint unreachable or API key invalid
- Check `GPT_OSS_ENDPOINT` and `GPT_OSS_API_KEY` secrets
- AI eval currently disabled — this is informational only

**Review posted as comment instead of review**
- Happens when the bot user is the PR author (GitHub 422 error)
- Falls back to issue comment automatically

**Duplicate reviews appearing**
- State cache was cleared or expired
- Harmless but noisy — consider extending cache retention

### Logs

Logs are written to `scripts/arbiter/logs/arbiter-{DATE}.log` on the runner. These are ephemeral — they don't persist after the workflow run. To debug, check the workflow run output in GitHub Actions.

---

## Customization Guide

### Adjusting Thresholds

In `config/config.yaml`:
```yaml
review:
  score_thresholds:
    approve: 70        # Lower = more lenient
    request_changes: 40  # Lower = fewer rejections
```

### Adding a New Check

1. Add to `config/checklist.yaml`:
   ```yaml
   - id: my_new_check
     description: "Description of what it checks"
     weight: 5
     type: recommended  # or required
   ```

2. Add function to `src/review/checklist.py`:
   ```python
   def _check_my_new_check(content: str, context: Optional[Dict] = None) -> bool:
       # Return True if check passes
       return 'expected_pattern' in content
   ```

3. Register in the dispatcher dict inside `_evaluate_check()`.

### Changing Branch Prefix

In `config/config.yaml`:
```yaml
review:
  pr_branch_prefix: "new-prefix-"
```

### Enabling Auto-Merge

In `config/config.yaml`:
```yaml
review:
  auto_merge: true
```

**Warning:** Ensure the token has merge permissions and the repo allows squash merges.

### Adding File Path Filter

In `config/config.yaml`:
```yaml
review:
  file_filter:
    path_contains: "/net/"  # Only review .NET docs
```

Set to `null` to review all `.md` files (current default).

---

## Dependencies

```
PyGithub>=2.1.1          # GitHub API client
openai>=1.0.0            # OpenAI-compatible client (GPT-OSS)
pyyaml>=6.0.1            # YAML config parsing
tinydb>=4.8.0            # Lightweight JSON state DB
python-frontmatter>=1.0.0 # Markdown frontmatter parsing
requests>=2.31.0         # HTTP requests (metrics posting)
```

---

## Pre-Flight Checklist

Before first run:

- [ ] `REPO_TOKEN` secret added with `repo` scope on `Aspose/aspose.net`
- [ ] `GPT_OSS_ENDPOINT` secret added (required even if AI eval disabled — config validation checks it)
- [ ] `GPT_OSS_API_KEY` secret added
- [ ] `data/` directory has `.gitignore` with `*.json` (already done)
- [ ] At least one open PR exists on `Aspose/aspose.net` with `api-update-*` branch prefix
- [ ] Test with manual dispatch: Actions → "API Docs PR Review" → Run workflow

---

## Reference

This arbiter is adapted from the [tutorials-pr-arbiter](https://github.com/user/tutorials-pr-arbiter) reference implementation. The engine code in `src/` is a portable copy with API-docs-specific configuration layered on top via `config/`.
