# aspose.net-workflows

CI/CD workflows and automation scripts for the [Aspose/aspose.net](https://github.com/Aspose/aspose.net) API reference documentation site.

## Workflows

| Workflow | File | Trigger | Description |
|---|---|---|---|
| **Translator** | `translator.yml` | Manual dispatch | Translates API reference documentation pages into multiple languages using LLM. Processes specified product families and target languages. |
| **API Docs PR Review** | `pr-review.yml` | Manual dispatch | Automated quality gate for API reference PRs. Runs static checklist + AI evaluation, posts scored GitHub reviews. |

## Scripts

### `scripts/reference/` — API Reference Doc Pipeline

| Script | Description |
|---|---|
| `check_versions.py` | Checks for new NuGet package versions across Aspose product families |
| `detect_updates.py` | Detects which product families have updated packages requiring doc regeneration |
| `extract_files.py` | Extracts and prepares source files from NuGet packages for DocFX processing |
| `generate_docfx.py` | Runs DocFX to generate API reference markdown from extracted assemblies |
| `postprocessor.py` | Post-processes generated markdown — fixes formatting, adds frontmatter, cleans artifacts |
| `push_to_repo.py` | Pushes processed docs to `Aspose/aspose.net` and creates PRs for review |
| `update_status.py` | Updates processing status tracking after pipeline completion |

### `scripts/gsc/` — Google Search Console

| Script | Description |
|---|---|
| `query-collector.py` | Collects search performance data (queries, clicks, impressions) from Google Search Console API |
| `sitemap_parser.py` | Parses XML sitemaps to extract URL lists for submission and analysis |
| `sitemap_submission_google.py` | Submits sitemaps to Google Search Console for indexing |
| `batch_submitter.py` | Batch submits URLs to Google for indexing via the Indexing API |

### `scripts/search/` — Search Data

| Script | Description |
|---|---|
| `merge_search_data.py` | Merges search index data across product families into unified search datasets |

### `scripts/arbiter/` — PR Review Bot

Automated PR quality gate for API reference documentation. Reviews PRs created by the reference doc pipeline against a configurable checklist.

| Component | Description |
|---|---|
| `src/` | Arbiter engine — PR fetching, static checklist evaluation, AI scoring, GitHub review posting, metrics reporting |
| `config/config.yaml` | Runtime config — target repo, thresholds, metrics endpoint, LLM settings |
| `config/checklist.yaml` | 13 quality checks (7 required, 6 recommended) for API reference content |
| `config/prompts/review.txt` | AI evaluation prompt for API doc quality assessment |
| `requirements.txt` | Python dependencies |
| `data/` | Runtime state (`.gitignore`d) — tracks reviewed PRs to avoid duplicates |

**Checklist highlights:**
- Required: frontmatter present, has title/layout/categories, no broken HTML tags, well-formed tables, no raw DocFX artifacts
- Recommended: has description/summary, code examples present, assembly version, valid internal links, adequate content length
- Score thresholds: >= 70 = APPROVE, 40-69 = REQUEST_CHANGES, < 40 = REJECT

## Secrets

| Secret | Used By | Purpose |
|---|---|---|
| `REPO_TOKEN` | All workflows | GitHub PAT with repo scope on `Aspose/aspose.net` |
| `GPT_OSS_ENDPOINT` | `pr-review.yml` | LLM API endpoint for AI evaluation |
| `GPT_OSS_API_KEY` | `pr-review.yml` | LLM API key |
