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
implementation, pipeline internals, source code, variable tracing, IAM implementation, or
repository code analysis — those are out of scope for Phase 1 by design. Do not add
DOCX/PPTX/XLSX/source-code/pipeline ingestion, and never infer component, repository, or
document ownership that isn't in the registry.

`AGENTS.md` is the product specification and holds the full grounding, presentation, and
boundary rules — read it before making agent-behavior, ingestion, or Slack changes.

## Layout

The application is a single flat, direct-composition package under `app/`:

```text
app/main.py            FastAPI routes, JsonFormatter logging, build_application() composition
app/config.py          Pydantic settings (KNOWLEDGE_INTELLIGENCE_* env vars)
app/models.py          shared Pydantic models
app/ingestion.py       three-source ingestion flow
app/pdf_parser.py      Confluence PDF parser      -> ParsedDocument
app/markdown_parser.py GitHub README parser       -> ParsedDocument
app/chunker.py         deterministic chunking
app/embeddings.py      OpenAI embeddings
app/vector_store.py    Amazon S3 Vectors + chunk persistence
app/search.py          hybrid retrieval (semantic + keyword)
app/agent.py           single Strands Platform Knowledge Agent, public_answer()
app/cache.py           bounded thread-safe LruCache shared by embeddings + vector_store
app/metrics.py         per-answer timing via Strands lifecycle hooks (observe only)
app/registry.py        authoritative component mappings
app/s3_reader.py       read-only Confluence source access
app/github_reader.py   README-only GitHub access
app/slack.py           Slack delivery + FeedbackStore
app/diagram.py         Slack flow-diagram rendering
app/diagram_analysis.py  decides when retrieved content supports a diagram
```

`app/main.py` wires everything explicitly in `build_application()` — there is no DI
container. `scripts/ingest.py` and `scripts/validate_search.py` reuse that same function,
so composition changes there propagate to both the API and the scripts.

Two details worth knowing before changing retrieval or ranking:

- `HybridSearch` keeps an **inverted index** (`_postings`: term -> ((chunk_id, term
  frequency), ...)) built in `replace_keyword_cache()`. A query only visits chunks that
  contain one of its terms. Keep TF-IDF weighting in `_keyword()` consistent with what
  `replace_keyword_cache()` stores, and note that document frequency is simply the length
  of a term's postings list.
- `HybridSearch.search()` already assigns the `S1..Sn` identifiers that the agent cites,
  so downstream code must not renumber them.
- `INSTRUCTIONS` in `app/agent.py` is an **f-string** so the refusal sentence comes from
  the `INSUFFICIENT_ANSWER` constant that `answer()` and `scripts/evaluate.py` match on
  exactly. Any literal `{` or `}` added to that prompt must be doubled, and the sentence
  itself must only ever be changed at the constant.
- `_knowledge_answer()` **enforces** the answer contract rather than trusting the prompt:
  an answer that is the refusal (compared via `is_refusal()`, which tolerates casing,
  spacing, quoting, and curly apostrophes) is canonicalised to `INSUFFICIENT_ANSWER` and
  stripped of its diagram and follow-ups; follow-ups already stated in the answer are
  dropped so nothing renders twice; and a "flow" of fewer than two nodes is discarded.
  Put new presentation rules here, not only in the prompt.
- `PlatformKnowledgeAgent.answer_stream()` streams the answer while it is generated.
  Because the model returns **structured output**, the raw deltas are JSON, not prose —
  `PartialAnswer` decodes just the `answer` field from the partial JSON. It deliberately
  withholds a trailing lone surrogate, since an emoji can arrive split across two deltas
  and a half pair is not UTF-8 encodable. Do not "simplify" that guard away.

Note: `pyproject.toml` is **tooling configuration only**. Runtime dependencies live in
`requirements.txt` (what the Dockerfile and README setup install); do not duplicate them
into `pyproject.toml`, since the two silently drifted apart before.

## Commands

Install (Python 3.14 required):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"
cp .env.example .env
```

Run the API:

```bash
fastapi dev app/main.py
```

Ingest and validate — these two scripts are the sanctioned Phase 1 validation path:

```bash
python scripts/ingest.py
python scripts/validate_search.py "How do I onboard to EKS as a Service?"
```

Lint and type-check (both target `app` and `scripts`):

```bash
ruff check .
mypy
```

Score the agent against the approved evaluation dataset (`evals/datasets/*.yaml`). The
deterministic evaluators cost only the agent calls; `--judge` adds the Strands
LLM-as-judge faithfulness and refusal evaluators, which make extra model calls:

```bash
python scripts/evaluate.py
python scripts/evaluate.py --judge
```

Run the test suite (offline — no AWS, OpenAI, or Slack calls):

```bash
pytest
pytest tests/test_answer_contract.py::test_refusal_cannot_carry_a_diagram_or_buttons
```

`tests/` covers `app/` directly: the registry boundary, deterministic chunking, the
inverted keyword index, the enforced answer contract, streaming (including the split
surrogate-pair guard), every HTTP endpoint, and the evaluation harness. Shared fakes live
in `tests/conftest.py`. `mypy` deliberately targets only `app` and `scripts`, so tests are
linted by `ruff` but not type-checked. `tests/test_evaluate.py` skips itself unless the
`dev` extra (which brings `strands-agents-evals`) is installed.

Docker and deploy:

```bash
docker build -t knowledge-intelligence .
docker run --rm --env-file .env -p 8000:8000 knowledge-intelligence
./deploy.sh
```

`deploy.sh` is non-interactive: it inits the Terraform backend, creates ECR first, builds
and pushes only the `latest` image, applies the rest, forces a new ECS deployment, and
waits for service stability. It uses `infra/backend.hcl` and `infra/terraform.tfvars` by
default; override with `BACKEND_CONFIG` / `TFVARS_FILE` (paths resolved from `infra/`).
Terraform remains the source of truth for AWS infrastructure.

## Architecture (Phase 1 flow)

```text
Confluence PDF + GitHub README + Component Registry
                         |
                       Parser            (PDF and Markdown parsers only — both
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

Keep exactly these endpoints — do not reintroduce change-impact, repository-analysis,
evaluation, visual-processing, GitHub-agent, or multi-agent-orchestrator endpoints:

- `GET /health`, `GET /ready`
- `POST /knowledge/query` — public API; the response contains **only** the end-user answer.
  Source identifiers like `[S1]` are used internally for grounding and are never returned.
- `POST /admin/reindex` — requires `X-Admin-Token` matching
  `KNOWLEDGE_INTELLIGENCE_ADMIN_TOKEN`; prefer `scripts/ingest.py` for controlled ingestion.
  For ECS, set `admin_reindex_enabled = true` only after adding `ADMIN_TOKEN` to the
  Terraform-managed secret.
- `POST /slack/events` — also serves Slack Interactivity and the `/ask-tme` slash command

### Component Registry

`registry/components/*.yaml` (one file per component) is the single source of truth for
component IDs, names, aliases, GitHub repositories, and Confluence prefixes. Ingestion must
skip any source not mapped here and log only its identifier, never its content.

### GitHub access boundary

Read-only, fine-grained PAT with **Contents: read** only, fetching `README.md` through the
GitHub Contents API exclusively. No GitHub App, webhooks, repository cloning, tree
traversal, code search, or continuous sync. Controlled by
`KNOWLEDGE_INTELLIGENCE_GITHUB_ENABLED` / `_GITHUB_TOKEN` / `_GITHUB_API_URL`.

### Optional runtime features

All default-safe and controlled by `KNOWLEDGE_INTELLIGENCE_*` settings:

- `SLACK_STREAMING_ENABLED` (default true) — the Slack placeholder message is updated
  progressively as the answer is generated, throttled by `SLACK_STREAM_INTERVAL_SECONDS`
  to stay within Slack's `chat.update` rate limit. Slash-command replies stay
  non-streaming, because `response_url` posts new messages rather than editing one.
- `SESSION_PERSISTENCE_ENABLED` (default false) — backs each Slack thread with a Strands
  `S3SessionManager` so conversations survive an ECS task restart. Uses the existing
  knowledge bucket under `SESSION_PREFIX`. Ephemeral API calls are never persisted.
- `CONVERSATION_SUMMARIZATION_ENABLED` (default false) — swaps the sliding window for
  `SummarizingConversationManager` so long threads keep earlier context.
- `METRICS_ENABLED` (default true) — `app/metrics.py` registers observe-only Strands
  hooks that log invocation duration and model-call count. It logs a hash of the
  conversation id, never the Slack channel, user, question, or answer.

### Slack integration

Slack is a **delivery channel only** and must never contain retrieval or agent logic. Each
thread gets an independent Strands conversation with a bounded sliding window (recent Q&A
and tool results kept ~2 hours in process memory), but a fresh retrieval happens on every
turn regardless. When retrieved content supports a workflow, process, architecture,
lifecycle, or mapping, Slack automatically adds a high-level flow diagram — the API itself
never returns diagrams, and diagram nodes must never be invented.

Feedback under `feedback/slack/` stores only a random answer ID, response category, rating,
and timestamp — never the Slack user, channel, question, answer, source text, or
conversation.

### Visual (diagram) analysis

With `KNOWLEDGE_INTELLIGENCE_VISUAL_ANALYSIS_ENABLED=true`, candidate PDF pages are rendered
(PyMuPDF/Pillow) and passed to a vision-capable Strands agent; the page-grounded
descriptions are indexed alongside extracted text. The chosen OpenAI model must support
image input, and an empty `_VISUAL_ANALYSIS_MODEL` falls back to
`KNOWLEDGE_INTELLIGENCE_OPENAI_MODEL`. Treat these descriptions as model-derived and
page-grounded only — never present a relationship not visible on the source page. Re-run
`scripts/ingest.py` after enabling the flag; visual calls incur model usage.

## Engineering conventions

- Prefer readability and deterministic behavior over abstraction; keep modules small and
  direct-composition. Avoid DI containers, protocols, repository patterns, factories,
  builders, and layered domain/application separation unless genuinely necessary.
- Strong typing throughout; Pydantic v2 for configuration, API contracts, and external data.
  `mypy` runs in `strict` mode.
- Use `pathlib` for filesystem paths; avoid `Any`, mutable global state, wildcard imports,
  and monkey patching.
- Raise specific errors internally; return safe messages to users.
- Never log secrets, tokens, document text, embeddings, or personal data. Structured logs
  include correlation ID, operation, component, and duration when available (see
  `JsonFormatter` in `app/main.py`).
- Grounding: retrieve first, answer only from returned content, cite via returned source
  identifiers, and never invent components, repositories, ownership, prerequisites,
  runbooks, procedures, account IDs, IAM roles, or deployment behavior. Do not claim
  indexed information reflects live infrastructure state. When information is insufficient,
  respond exactly: `I don't have enough information to answer that reliably.`
- User-facing responses must never mention indexing, retrieval, prompts, tools, evidence, or
  other backend implementation. State supported information directly rather than saying
  "the documentation says".

## Secrets and environment

Copy `.env.example` to `.env` and populate locally — never commit `.env`. All settings use
the `KNOWLEDGE_INTELLIGENCE_` prefix. In AWS, one Secrets Manager JSON entry carries
`OPENAI_API_KEY`, `GITHUB_TOKEN` (when GitHub is enabled), `ADMIN_TOKEN` (only once
`admin_reindex_enabled = true`), and the Slack token keys.
