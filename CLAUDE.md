# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project purpose and boundaries

Knowledge Intelligence Phase 1 is a source-grounded Platform Knowledge Agent for TME
application teams, operations teams, and new joiners. It answers service discovery,
onboarding, prerequisite, validation, and runbook questions from three **approved sources
only**:

1. Confluence PDF exports under a configured S3 prefix
2. `README.md` from repositories explicitly mapped in `registry/components/*.yaml`
3. `registry/components/*.yaml` itself (authoritative component/ownership mapping)

It is **not** a developer assistant: it must never answer questions about Terraform
implementation, pipeline internals, source code, IAM implementation, or repository code
analysis — those are out of scope for Phase 1 by design (see `AGENTS.md`). Do not add
DOCX/PPTX/XLSX/source-code/pipeline ingestion. Never infer component/repository/document
ownership that isn't in the registry.

Full product and grounding rules live in `AGENTS.md` — read it before making
agent-behavior, ingestion, or Slack-presentation changes.

## Two parallel codebases — know which one you're touching

This repo currently contains **two implementations** of the same system:

- **`app/`** — the flat, direct-composition implementation described by `AGENTS.md` and
  `README.md`. This is what `Dockerfile`, `deploy.sh`, `scripts/ingest.py`, and
  `scripts/validate_search.py` run against (`fastapi dev app/main.py`). Treat this as the
  authoritative/deployed structure unless told otherwise.
- **`src/knowledge_intelligence/`** — a more layered package (separate `connectors/`,
  `parsers/`, `retrieval/`, `embeddings/`, `agents/`, `registry/`, `api/`,
  `visual/`, `chunking/` subpackages) that is what `tests/` actually imports from
  (`from knowledge_intelligence.connectors.github.client import ...`) and what
  `pyproject.toml`'s `[tool.hatch.build.targets.wheel]` and `[tool.mypy] files` target.
  It is currently untracked in git (`src/`, `tests/`, `evals/` all show as `??`).

Before editing, check which tree a request actually concerns — `app/*.py` mirrors
`src/knowledge_intelligence/**` roughly 1:1 by concept (e.g. `app/github_reader.py` vs
`src/knowledge_intelligence/connectors/github/`), but they are not kept in sync
automatically. Don't assume a fix in one is reflected in the other.

## Commands

Install (Python 3.14 required):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt        # or: pip install -e ".[dev]"
cp .env.example .env
```

Run the app (the `app/` implementation):

```bash
fastapi dev app/main.py
```

Ingest and validate:

```bash
python scripts/ingest.py
python scripts/validate_search.py "How do I onboard to EKS as a Service?"
```

Lint / type-check / test (mypy and hatch build both target `src` + `scripts`, not `app`):

```bash
ruff check .
mypy
pytest
pytest tests/retrieval/test_github_search.py::test_github_adapter_requires_owner_and_repository_names  # single test
```

Docker:

```bash
docker build -t knowledge-intelligence .
docker run --rm --env-file .env -p 8000:8000 knowledge-intelligence
```

Deploy (Terraform via ECR/ECS, non-interactive):

```bash
./deploy.sh
```

Uses `infra/backend.hcl` and `infra/terraform.tfvars` by default; override with
`BACKEND_CONFIG` / `TFVARS_FILE` (paths resolved from `infra/`).

## Architecture (Phase 1 flow)

```text
Confluence PDF + GitHub README + Component Registry
                         |
                       Parser            (PDF Parser and Markdown Parser only — both
                         |                 return the same ParsedDocument model)
                  ParsedDocument
                         |
                      Chunking
                         |
                     Embeddings           (OpenAI)
                         |
                 Amazon S3 Vectors
                         |
                   Hybrid Search          (semantic + keyword)
                         |
              Platform Knowledge Agent    (single Strands agent)
```

Runtime endpoints (do not add others in Phase 1 — no change-impact, repository-analysis,
evaluation, visual-processing, GitHub-agent, or multi-agent-orchestrator endpoints):

- `GET /health`, `GET /ready`
- `POST /knowledge/query` — public API; response contains only the end-user answer.
  Source identifiers like `[S1]` are used internally for grounding and never returned.
- `POST /admin/reindex` — requires `X-Admin-Token` matching
  `KNOWLEDGE_INTELLIGENCE_ADMIN_TOKEN`; prefer `scripts/ingest.py` for controlled ingestion
- `POST /slack/events` — Slack is a delivery channel only; it must not contain retrieval or
  agent logic itself

### Component Registry

`registry/components/*.yaml` (one file per component) is the single source of truth for
component IDs, aliases, GitHub repos, and Confluence prefixes. Ingestion must skip any
source not mapped here and log only its identifier, never its content.

### GitHub access boundary

Read-only, fine-grained PAT with **Contents: read** only. Fetches `README.md` via the
GitHub Contents API exclusively — no GitHub App, no webhooks, no repo cloning/tree
traversal, no code search, no continuous sync. Controlled by
`KNOWLEDGE_INTELLIGENCE_GITHUB_ENABLED` / `_GITHUB_TOKEN` / `_GITHUB_API_URL`.

### Slack integration

Each Slack thread gets an independent Strands conversation with a bounded sliding window
(recent Q&A/tool results retained ~2 hours in memory; a fresh retrieval happens on every
turn regardless). When retrieved content supports a workflow/process/architecture/lifecycle
mapping, Slack auto-generates a high-level flow diagram (`app/diagram.py` /
`app/diagram_analysis.py`) — the API itself never returns diagrams. Feedback storage
(`feedback/slack/`) is limited to a random answer ID, category, rating, and timestamp —
never the Slack user, channel, question, answer, or conversation content.

### Visual (diagram) analysis

When `KNOWLEDGE_INTELLIGENCE_VISUAL_ANALYSIS_ENABLED=true`, candidate PDF pages are
rendered and passed to a vision-capable Strands agent whose page-grounded descriptions are
indexed alongside extracted text. Treat these descriptions as model-derived and
page-grounded only — never present a relationship not actually visible on the source page.
Re-run `scripts/ingest.py` after enabling this flag.

## Engineering conventions (from `AGENTS.md`)

- Prefer readability and deterministic behavior over abstraction; keep modules small and
  direct-composition (no DI containers, no protocols/repository/factory/builder patterns
  unless genuinely necessary).
- Strong typing throughout; Pydantic v2 for config, API contracts, and external data.
- Use `pathlib` for filesystem paths; avoid `Any`, mutable global state, wildcard imports,
  monkey patching.
- Raise specific errors internally; return safe messages to users.
- Never log secrets, tokens, document text, embeddings, or personal data. Structured logs
  should include correlation ID, operation, component, and duration when available (see
  `JsonFormatter` in `app/main.py`).
- Grounding: retrieve first, answer only from returned content, cite via source
  identifiers, never invent components/repositories/ownership/prerequisites/procedures. If
  insufficient information, respond exactly:
  `I don't have enough information to answer that reliably.`
- User-facing responses must never mention indexing, retrieval, prompts, tools, or other
  backend implementation details.

## Secrets and environment

Copy `.env.example` to `.env` and populate locally — never commit `.env`. In AWS, the same
Secrets Manager JSON entry carries `OPENAI_API_KEY`, `GITHUB_TOKEN` (when GitHub is
enabled), `ADMIN_TOKEN` (only add once `admin_reindex_enabled = true` in Terraform), and
Slack token keys.
