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
app/instructions.md    the agent prompt, loaded at import and shipped inside the package
app/cache.py           bounded thread-safe LruCache shared by embeddings + vector_store
app/metrics.py         per-answer timing via Strands lifecycle hooks (observe only)
app/registry.py        authoritative component mappings
app/s3_reader.py       read-only Confluence source access
app/github_reader.py   README-only GitHub access
app/slack.py           Slack delivery + FeedbackStore + DiagramStore
app/waiting.py         prompt-aware holding messages posted before the agent runs
app/diagram.py         Graphviz flow and knowledge-map rendering, Pillow fallback
app/diagram_analysis.py  decides when retrieved content supports a diagram
```

`app/main.py` wires everything explicitly in `build_application()` — there is no DI
container. `scripts/ingest.py` and `scripts/validate_search.py` reuse that same function,
so composition changes there propagate to both the API and the scripts.

Details worth knowing before changing retrieval or ranking:

- `HybridSearch` keeps an **inverted index** (`_postings`: term -> ((chunk_id, term
  frequency), ...)) built in `replace_keyword_cache()`. A query only visits chunks that
  contain one of its terms. Keep TF-IDF weighting in `_keyword()` consistent with what
  `replace_keyword_cache()` stores, and note that document frequency is simply the length
  of a term's postings list.
- `search()` **retrieves wide and returns narrow**: each side fetches `max(limit, top_k)`
  candidates (25 by default) and RRF fusion trims to the `limit` the agent asked for (5).
  Raising `VECTOR_TOP_K` alone used to be inert, because the old code took
  `min(limit, top_k)` and the agent always passes the smaller number. Keep the two numbers
  distinct: `candidates` governs recall, `returned` governs how much reaches the prompt.
- Fusion caps how many chunks any one document contributes (`per_document`, default 3).
  A long PDF otherwise supplies the best chunk *and* the next four, crowding out the
  document that answers the rest of the question. Chunks over the cap are held back and
  only used to top up if the limit is not otherwise met.
- `_tokens()` folds a simple plural (`_singular`), so `osbuild` and `osbuilds` share a
  postings list. Without it a query term had to match the indexed form exactly, and
  questions using the singular missed every chunk of the component.
- `_searchable()` and `_embedding_text()` both prepend the chunk's title and component id.
  That adds context, but it also means every chunk of a component literally contains that
  component's name — so a question naming a component pulls its chunks strongly and can
  crowd out a cross-cutting document. Measure before changing either, and see the
  evaluation dataset for the cases that pin this behaviour.
- `HybridSearch.search()` already assigns the `S1..Sn` identifiers that the agent cites,
  so downstream code must not renumber them.
- The agent prompt lives in `app/instructions.md` and is loaded by `_instructions()` in
  `app/agent.py`. The `{INSUFFICIENT_ANSWER}` placeholder is **substituted, not formatted**,
  so the refusal sentence stays single-sourced from the constant that `answer()` and
  `scripts/evaluate.py` match on exactly, while a literal `{` or `}` in the prompt is
  harmless. Change the sentence only at the constant. The file sits inside `app/` so
  `COPY app ./app` ships it in the image — a prompt outside the package would not be there
  at runtime. A test asserts every `IntelligentResponse` field is named in the prompt, so a
  new structured field cannot be added without documenting it.
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

Logging: `JsonFormatter` in `app/main.py` emits **every** scalar `extra` a caller passes,
not a fixed whitelist. It previously listed six field names and silently dropped the rest,
which is why `slack_error` and `model_calls` never appeared in CloudWatch while the code
that set them looked correct. Falsy values are emitted too, so `skipped: 0` is visible.

Note: `pyproject.toml` is **tooling configuration only** — except for `packages = ["app"]`,
which is required: without it setuptools' flat-layout discovery sees `app/`, `evals/`,
`infra/` and `registry/` as four competing top-level packages and refuses to build, so the
documented `pip install -e ".[dev]"` fails. Runtime dependencies live in `requirements.txt`
(what the Dockerfile and README setup install); do not duplicate them into `pyproject.toml`,
since the two silently drifted apart before. `strands-agents-evals` belongs to the `dev`
extra alone so the container never ships the evaluation harness.

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

`scripts/ingest.py --source {confluence,github,registry}` (repeatable) rebuilds only the
named sources. Confluence PDF parsing plus visual analysis is by far the most expensive
part of a run, so `--source github --source registry` refreshes the cheap sources without
repeating it. This is safe because `Ingestion.run()` carries the chunks of every
*unselected* source into the set it hands `VectorStore.finalize()` — that method prunes
whatever is missing from the set it is given, so a subset run would otherwise delete the
sources it did not touch. Keep that invariant if you change either method.

A repository whose `README.md` cannot be read is **skipped and counted**, never fatal.
`_github_documents()` returns the documents and a skip count; an expired token or a renamed
branch must not discard a run whose PDF parsing and visual analysis have already been paid
for.

If the vector index is lost but `processed/chunks/` survives, do not re-run ingestion:

```bash
python scripts/rebuild_vectors.py
```

It re-embeds the persisted chunks, which costs embedding calls only. This separation is why
the chunk store lives in the ordinary S3 bucket rather than as vector metadata — the index
is disposable, the parsed text and visual descriptions are not.

Lint and type-check (both target `app` and `scripts`):

```bash
ruff check .
mypy
```

Score the agent against the approved evaluation dataset (`evals/datasets/*.yaml`). The
deterministic evaluators cost only the agent calls; `--judge` adds the Strands
LLM-as-judge faithfulness and refusal evaluators, which make extra model calls.

The dataset carries only fields the evaluators actually read — `question`, `category`,
`expected_keywords`, `forbidden_keywords`, `expect_refusal`. Cases are grouped by category
so a run reports separately on `supported`, `unsupported` and `out-of-scope`; keep enough
refusal cases that loosening the prompt shows up as a failure rather than a nicer number.
`collect_rows()` exists because `report.to_dict()` returns case detail and outcomes as
**parallel arrays** — `cases` has name, evaluator and metadata, while `scores`,
`test_passes` and `reasons` sit alongside it. Reading a score off a case row yields 0.0 and
a blank reason for everything, which once produced a confident 0% scorecard:

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
`backend.tf` holds only a partial backend, so bucket, key and region come from
`backend.hcl` at init time; that file is gitignored and `backend.hcl.example` is the
template. `build.sh` passes `--platform linux/amd64` because Fargate runs `X86_64` — an
image built natively on Apple Silicon will not start.

The image installs the **graphviz binary and DejaVu fonts**; `app/diagram.py` falls back to
the plainer Pillow renderer when `dot` is missing, so a forgotten system package degrades
the picture silently rather than failing.

Terraform remains the source of truth for AWS infrastructure, with two deliberate
exceptions. The application secret is a **data source**, not a managed resource: Terraform
reads `knowledge-intelligence/application` and never creates or destroys it, so a clean
deploy into a new account needs that secret created by hand first. And
`destroy_resources.sh` preserves anything matching `aws_s3_*`, `aws_s3vectors_*`,
`aws_secretsmanager_*` or `aws_ecr_*` — the `aws_s3vectors_*` entry matters because a vector
bucket is not `aws_s3_bucket`, and without it every teardown deletes the embeddings. S3
Vectors bills for storage and requests with no idle charge, so there is nothing to save by
destroying it.

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
- `GET /diagrams/{id}.png` — unauthenticated by necessity, because Slack's image fetcher is
  anonymous. The id must match a UUID, so it cannot be used to read other bucket objects.

### Component Registry

`registry/components/*.yaml` (one file per component) is the single source of truth for
component IDs, names, aliases, GitHub repositories, contacts, relationships, and Confluence
prefixes. An empty registry file is a hard error, not a silent skip, and every `related:`
target must name a component that exists.

Membership is declared by the child (`part_of: tme-platform`), never by the hub. Exactly
one component may omit it — the root — and every other must name a parent that exists, with
no cycles; all three are load-time errors. A component added next year therefore joins the
hierarchy by its own file, and TME's list of children is derived, so no one has to remember
to edit a second file. Both directions are indexed: the child document states "X is part of
TME" and the parent document states "TME includes X".

Nesting works to any depth, and `component_for_s3_key()` resolves a document to the
**most specific** matching prefix, so a nested component may claim a prefix inside its
parent's. Two components claiming a prefix of equal length is a genuine ambiguity and stays
a hard error. `children_of()` returns direct children only — a transitive list would bloat
the indexed document.

`notes:` captures knowledge agreed outside Confluence — decisions from a call, conventions
that were never written down. Each note needs `note` text and a `recorded` date, and may
name a `source`. **Only the note text is indexed**; `recorded` and `source` stay out of the
vector store, the keyword index, and the prompt, exactly as `contact:` does, because a
source often names a person.

Treat notes as the one place unreviewed knowledge legitimately enters the index. They are
approved by the act of being written into the registry, which is why they are dated: a note
is auditable and expirable, and a stale one is a bug. Keep them short and factual, and
state the exceptions — asserting that one thing follows another's process licenses the model
to restate every detail of that process, including the ones that do not transfer.

`related:` edges are for peer relationships that are not containment. They are directed and
authoritative: the one place a relationship between components is declared rather than
inferred, so they are safe to state and to draw.
They are rendered into the indexed registry document as sentences. `contact:` deliberately
is **not** indexed — a person or channel must never reach the vector store, the keyword
index, or the model prompt; it is attached structurally at answer time instead.

The registry provides **attribution, not admission**. Approval happens at upload: anything
under the configured S3 prefix is approved by definition. A PDF that no component maps is
still indexed, tagged with `UNMAPPED_COMPONENT_ID` rather than a guessed owner, and counted
in `ReindexSummary.unmapped` — a rising count means the registry is drifting behind the
bucket. That placeholder is deliberately kept out of the keyword index, the embedding text,
and the model prompt, so it can never be mistaken for a real owner. Set
`KNOWLEDGE_INTELLIGENCE_INGEST_UNMAPPED_DOCUMENTS=false` to restore registry-gated
ingestion. Log only a source identifier, never its content.

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

When the answer instead breaks a subject into unordered areas, the agent returns
`visual_center` plus `visual_branches`, and Slack renders a **radial knowledge map**
(`render_mindmap`, Graphviz `twopi`) rather than a flow. A sequence always wins: if
`visual_nodes` survives cleaning, `_knowledge_answer()` discards the map, so an ordered
process can never be redrawn as a map. A map needs a subject and at least two branches, and
every label passes through `public_answer()`.

Diagrams are delivered as an `image` block pointing at `GET /diagrams/{id}.png`, which the
application serves from S3 under `DIAGRAM_PREFIX`. It must answer **HEAD as well as GET** —
Slack sends HEAD first, and a presigned S3 URL (signed for GET alone) answers HEAD with 403,
which Slack reports as `invalid_blocks`. `_delivery_attempts()` retries without the image and
then as plain text, so a rejected block never costs the answer.

Flows are laid out by Graphviz: a single column up to four steps, two columns beyond that,
because Slack scales a tall image down until its labels stop being readable. A leading stage
token such as `M0` becomes a chip only when **every** step carries one — mixing `M0` with a
sequence number invents a numbering that contradicts the source.

Before the agent runs, `app/waiting.py` posts a holding message chosen by keyword from the
question, and the answer later replaces that same message. It never mentions retrieval or
indexing, and a test asserts none of the phrasings do.

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
