# Knowledge Intelligence Phase 1

## Project goal

Knowledge Intelligence Phase 1 is a Platform Knowledge Agent that helps TME users discover
and understand TME services using approved information.

The intended users are:

- Application Teams
- TME Users
- Operations Teams
- New Onboarded Users

Phase 1 is not a developer assistant and is not intended for platform implementation or
source-code investigation.

## Supported questions

The agent may answer questions such as:

- What is a TME service?
- What are its prerequisites?
- Which registered repository should a user access?
- How does onboarding work?
- What happens after PR approval?
- How can a deployment be validated?
- Where is the relevant runbook?

The agent must not answer questions about:

- Terraform implementation
- Pipeline internals
- Source code
- Variable tracing
- IAM implementation
- Repository code analysis

Those capabilities belong to a future phase.

## Approved sources

Phase 1 supports exactly three sources:

1. Confluence PDF exports stored under the configured Amazon S3 prefix.
2. GitHub `README.md` files from repositories mapped by the Component Registry.
3. Component definitions stored in `registry/components/*.yaml`.

Do not add DOCX, PPTX, XLSX, source-code, pipeline, Terraform, or shell-script ingestion.
PDF ingestion may render candidate pages for diagram understanding through a
vision-capable Strands agent.

## Component Registry

The Component Registry is the authoritative mapping for:

- component IDs and names
- aliases
- GitHub repositories
- Confluence prefixes

Never infer component membership, repository ownership, or document ownership. Skip an
unmapped source and log its identifier without logging its content.

## GitHub boundary

Use a fine-grained Personal Access Token with read-only Contents permission.

Only request `README.md` through the GitHub Contents API. Do not:

- create a GitHub App
- use webhooks
- clone repositories
- traverse repository trees
- perform code search
- read source code, Terraform, YAML, pipelines, or shell scripts
- implement continuous repository synchronisation

GitHub access is controlled by:

- `KNOWLEDGE_INTELLIGENCE_GITHUB_ENABLED`
- `KNOWLEDGE_INTELLIGENCE_GITHUB_TOKEN`
- `KNOWLEDGE_INTELLIGENCE_GITHUB_API_URL`

## Phase 1 flow

```text
Confluence PDF + GitHub README + Component Registry
                         |
                       Parser
                         |
                  ParsedDocument
                         |
                      Chunking
                         |
                     Embeddings
                         |
                 Amazon S3 Vectors
                         |
                   Hybrid Search
                         |
              Platform Knowledge Agent
```

Only `PDF Parser` and `Markdown Parser` are supported. Both return the same
`ParsedDocument` model.

## Application structure

Keep the codebase small and direct:

```text
app/
    main.py
    config.py
    models.py
    ingestion.py
    search.py
    embeddings.py
    vector_store.py
    chunker.py
    registry.py
    agent.py
    pdf_parser.py
    diagram_analysis.py
    markdown_parser.py
    s3_reader.py
    github_reader.py
    slack.py

registry/components/
scripts/ingest.py
scripts/validate_search.py
requirements.txt
Dockerfile
```

## Engineering

- Target Python 3.14.
- Prefer readability and deterministic behavior over abstraction.
- Use strong typing and Pydantic v2 for configuration, API contracts, and external data.
- Keep modules small and focused.
- Use direct composition instead of dependency-injection containers.
- Avoid protocols, repository patterns, factories, builders, and layered domain/application
  separation unless they become genuinely necessary.
- Keep the application under `app/`.
- Use `pathlib` for filesystem paths.
- Avoid `Any`, mutable global state, wildcard imports, and monkey patching.
- Raise specific errors internally while returning safe messages to users.
- Never log secrets, tokens, document text, embeddings, or personal data.
- Keep logs structured and include correlation ID, operation, component, and duration when
  available.
- Preserve Slack, OpenAI, Strands, Amazon S3 Vectors, Secrets Manager, source citations,
  and ECS deployment compatibility.
- Treat visual descriptions as model-derived, page-grounded content. Never present a
  relationship that is not visible in the supplied PDF page.
- Terraform remains the source of truth for AWS infrastructure.

## Grounding and presentation

- Retrieve first and answer only from returned content.
- Cite all factual answers using returned source identifiers.
- Never invent components, repositories, ownership, prerequisites, runbooks, procedures,
  account IDs, IAM roles, or deployment behavior.
- Do not claim that indexed information represents live infrastructure state.
- If information is insufficient, say: `I don't have enough information to answer that reliably.`
- User-facing responses must not mention indexing, retrieval, prompts, tools, evidence,
  or other backend implementation.
- State supported information directly instead of saying “the documentation says”.
- Slack is a delivery channel only; it must not contain retrieval or agent logic.
- When supported information establishes a workflow, process, architecture, lifecycle, or
  mapping, generate a high-level visual automatically for Slack. Do not require the user to
  request it and never invent missing nodes or relationships.
- Present supported onboarding information as a guided journey.
- Present supported service differences as a clear comparison.
- Offer only grounded, component-relevant next questions.
- Continue follow-up questions within the originating Slack thread using a bounded Strands
  conversation manager. Perform retrieval again on every turn.
- Store feedback without user IDs, channel IDs, questions, answers, source content, or
  conversation history.

## Runtime surface

Keep only these application endpoints:

- `GET /health`
- `GET /ready`
- `POST /knowledge/query`
- `POST /admin/reindex`
- `POST /slack/events`

Do not reintroduce change-impact, repository-analysis, evaluation, visual-processing,
GitHub-agent, or multi-agent-orchestrator endpoints in Phase 1.

## Validation

Phase 1 uses:

- `scripts/ingest.py` to rebuild the approved index
- `scripts/validate_search.py` to execute a live grounded query

Before handing off a change:

- format and lint the Python files
- run strict type checking
- compile the Python modules
- validate Terraform when infrastructure changed
- ensure the Docker image remains buildable
- confirm no secrets or generated caches were added
