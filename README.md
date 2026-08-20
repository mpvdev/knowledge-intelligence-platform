# Knowledge Intelligence

Knowledge Intelligence Phase 1 is a source-grounded Platform Knowledge Agent for TME
application teams, users, operations teams, and new joiners. It answers service discovery,
onboarding, prerequisite, validation, and runbook questions from approved content.

It is not a developer assistant and does not inspect source code, Terraform, pipelines, IAM,
or repository internals.

## Knowledge sources

- Confluence PDF exports under the configured Amazon S3 prefix
- `README.md` from repositories explicitly mapped in the component registry
- `registry/components/*.yaml`, the authoritative component and ownership mapping

When visual analysis is enabled, candidate PDF pages are rendered and passed to a
vision-capable Strands agent. Its page-grounded descriptions of diagrams, workflows,
architecture, charts, and mappings are indexed alongside extracted text.

GitHub access uses a fine-grained read-only PAT with **Contents: read** permission. Phase 1
does not use GitHub Apps, webhooks, repository sync, or repository scanning.

## Structure

```text
app/
    main.py              FastAPI routes and service composition
    config.py            environment configuration
    models.py            shared Pydantic models
    ingestion.py         three-source ingestion flow
    search.py            hybrid retrieval
    embeddings.py        OpenAI embeddings
    vector_store.py      Amazon S3 Vectors and chunk persistence
    chunker.py            deterministic chunking
    registry.py           authoritative component mappings
    agent.py              single Strands Platform Knowledge Agent
    pdf_parser.py         Confluence PDF parser
    markdown_parser.py    GitHub README parser
    s3_reader.py          read-only Confluence source access
    github_reader.py      README-only GitHub access
    slack.py              Slack delivery
    diagram.py            Slack flow-diagram rendering
    metrics.py            per-answer timing via agent lifecycle hooks
    diagram_analysis.py   decides when content supports a diagram
registry/components/     one YAML file per component
scripts/ingest.py        explicit index rebuild
scripts/validate_search.py
scripts/evaluate.py      grounding and refusal scorecard
```

## Local setup

Python 3.14 is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Populate `.env` without committing it. Enable GitHub only when a suitable PAT is available:

```dotenv
KNOWLEDGE_INTELLIGENCE_GITHUB_ENABLED=true
KNOWLEDGE_INTELLIGENCE_GITHUB_TOKEN=your-read-only-fine-grained-pat
KNOWLEDGE_INTELLIGENCE_GITHUB_API_URL=https://api.github.com
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```

The suite runs entirely offline and makes no AWS, OpenAI, or Slack calls.

## Ingest and validate

```bash
python scripts/ingest.py
python scripts/validate_search.py "How do I onboard to EKS as a Service?"
```

Run the API:

```bash
fastapi dev app/main.py
```

Available endpoints:

- `GET /health`
- `GET /ready`
- `POST /knowledge/query`
- `POST /admin/reindex`
- `POST /slack/events`

`POST /admin/reindex` requires `X-Admin-Token` matching
`KNOWLEDGE_INTELLIGENCE_ADMIN_TOKEN`. Prefer `scripts/ingest.py` for controlled ingestion.
For ECS, set `admin_reindex_enabled = true` only after adding `ADMIN_TOKEN` to the
Terraform-managed Secrets Manager JSON. The same secret uses `OPENAI_API_KEY`,
`GITHUB_TOKEN` when GitHub is enabled, and the Slack token keys when Slack is enabled.

Example query:

```bash
curl -sS http://localhost:8000/knowledge/query \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"What is EKS as a Service?"}'
```

The public query response contains only the end-user answer. Source details and internal
identifiers such as `[S1]` are retained for grounding and are not returned to API or Slack
users.

When retrieved information supports a workflow, process, architecture, lifecycle, or
component mapping, Slack automatically adds a compact high-level flow diagram. The API
continues to return only the answer.

## Intelligent Slack experience

Slack adds Phase 1 knowledge-sharing capabilities without changing the public API:

- guided onboarding journeys when supported steps are available
- service comparisons grounded across approved component knowledge
- connected component, repository, Confluence, and architecture mappings
- proactive high-level workflow visuals
- two or three grounded suggested follow-up questions
- clickable follow-up buttons that continue in the same Slack thread
- Helpful, Partly, and Not helpful feedback buttons
- answers that stream into the message as they are written

Answers are delivered progressively: the placeholder message fills in while the answer is
generated, throttled to respect Slack rate limits. Disable with
`KNOWLEDGE_INTELLIGENCE_SLACK_STREAMING_ENABLED=false`. Slash-command replies remain
non-streaming because `response_url` posts new messages instead of editing one.

Set `KNOWLEDGE_INTELLIGENCE_SESSION_PERSISTENCE_ENABLED=true` to back each thread with
Amazon S3 so conversations survive a task restart, and
`KNOWLEDGE_INTELLIGENCE_CONVERSATION_SUMMARIZATION_ENABLED=true` to summarize older turns
instead of dropping them.

Each Slack thread receives an independent Strands conversation with a bounded sliding
window. Recent user questions, answers, and tool results are retained for two hours in
application memory, allowing follow-ups such as “What happens after approval?” without
repeating the service name. The agent still performs a fresh search for every answer.
Conversation content is not written to feedback storage.

Configure the Slack app's **Interactivity & Shortcuts** Request URL to the same signed
endpoint used by Events API:

```text
https://<api-gateway-host>/slack/events
```

Configure the `/ask-tme` slash command with the same Request URL:

```text
https://<api-gateway-host>/slack/events
```

Examples:

```text
/ask-tme What is TME?
/ask-tme How does Golden AMI work?
```

Slash-command responses are visible in the channel so the user's question and the agent's
answer remain together as a normal conversation. To use `@TME Knowledge Hub` mentions in a
channel, add the app to that channel first.

Feedback stored under `feedback/slack/` contains only:

- random answer ID
- response category
- rating
- timestamp

It does not contain the Slack user, channel, question, answer, source text, or conversation.

Enable PDF diagram understanding with:

```dotenv
KNOWLEDGE_INTELLIGENCE_VISUAL_ANALYSIS_ENABLED=true
KNOWLEDGE_INTELLIGENCE_VISUAL_ANALYSIS_MODEL=
KNOWLEDGE_INTELLIGENCE_VISUAL_RENDER_DPI=144
KNOWLEDGE_INTELLIGENCE_VISUAL_MAX_PAGES_PER_DOCUMENT=10
KNOWLEDGE_INTELLIGENCE_SLACK_CONVERSATION_WINDOW=20
KNOWLEDGE_INTELLIGENCE_FEEDBACK_PREFIX=feedback/slack
```

The selected OpenAI model must support image input. Leaving the visual model empty uses
`KNOWLEDGE_INTELLIGENCE_OPENAI_MODEL`. Re-run `scripts/ingest.py` after enabling it.
Visual calls occur only for candidate pages and incur model usage.

## Evaluation

Score the agent against the approved dataset in `evals/datasets/`:

```bash
python scripts/evaluate.py
python scripts/evaluate.py --judge
```

The default run uses deterministic evaluators — refusal discipline, forbidden-claim
detection, expected-term coverage, and internal-wording leakage — and costs only the agent
calls. `--judge` adds the Strands LLM-as-judge faithfulness and refusal evaluators, which
make additional model calls. Both write a Markdown scorecard to
`evals/reports/platform_knowledge.md`.

## Container and AWS

```bash
docker build -t knowledge-intelligence .
docker run --rm --env-file .env -p 8000:8000 knowledge-intelligence
```

Deploy the complete AWS environment non-interactively:

```bash
./deploy.sh
```

The deployment script:

1. initializes the configured Terraform backend
2. creates the ECR repository first
3. builds and pushes only the `latest` image
4. applies the remaining Terraform resources
5. forces ECS to pull the newly published image
6. waits for the ECS service to become stable

It uses `infra/backend.hcl` and `infra/terraform.tfvars` by default. Alternative
Terraform files can be selected using `BACKEND_CONFIG` and `TFVARS_FILE`; paths
are resolved from the `infra/` directory.

The container remains compatible with the Terraform-managed ECS, S3, S3 Vectors,
Secrets Manager, CloudWatch, ALB, and API Gateway resources.
