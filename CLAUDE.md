# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Local Environment

- **OS**: Windows 11, shell: bash — use Unix syntax (forward slashes, not backslashes)
- **Python**: 3.14.3 — always use `.venv/Scripts/python`, never bare `python` or `python3`
- **pip**: always use `.venv/Scripts/python -m pip`, never bare `pip`
- **Docker**: NOT installed — integration tests and RAGAS retrieval eval require Docker Desktop

## Commands

All commands run from the project root.

```bash
# Unit tests (no external services)
.venv/Scripts/python -m pytest tests/unit -v

# Run a single test file
.venv/Scripts/python -m pytest tests/unit/test_search_tools.py -v

# Run a single test by name
.venv/Scripts/python -m pytest tests/unit/test_logger.py::TestAudit::test_mask_phi -v

# Integration tests (requires OpenSearch at localhost:9200 via Docker)
docker compose up opensearch -d
.venv/Scripts/python -m pytest tests/integration -m integration -v

# Linting
.venv/Scripts/python -m ruff check .

# ETL — index documents from S3 into OpenSearch
.venv/Scripts/python -m etl.run_etl                          # all domains
.venv/Scripts/python -m etl.run_etl --domain disease_study   # single domain
.venv/Scripts/python -m etl.run_etl --recreate               # drop + rebuild indices

# RAGAS evals
.venv/Scripts/python -m evals.run_evals --mode retrieval     # no Bedrock needed
.venv/Scripts/python -m evals.run_evals --mode generation    # requires Bedrock credentials
.venv/Scripts/python -m evals.run_evals --mode all           # writes eval-report.json

# Run locally (CLI — not the deployed entry point)
.venv/Scripts/python main.py
.venv/Scripts/python main.py --query "What are the side effects of ibuprofen?"

# Test the AgentCore entry point locally (starts HTTP server on port 8080)
.venv/Scripts/python agentcore_app.py
curl -X POST http://localhost:8080/invocations -H "Content-Type: application/json" \
  -d '{"prompt": "Summarize the disease study", "user_id": "test"}'

# Install dependencies
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m pip install -r requirements-test.txt
```

## Architecture

### Request flow

```
User → agentcore_app.py (@app.entrypoint)
         └─→ Orchestrator (agents/orchestrator.py)
                 ├─→ summarizer tool  → build_summarizer_agent()
                 ├─→ qa tool          → build_qa_agent()
                 └─→ question_generator tool → build_question_gen_agent()
                         │  (all sub-agents have)
                         └─→ ALL_SEARCH_TOOLS (tools/search_tools.py)
                                 └─→ _hybrid_search() → OpenSearch (BM25 + KNN via RRF)
                                         └─→ _embed_query() → Bedrock Titan Embed v2
```

**Critical pattern**: Sub-agents (`build_qa_agent()`, etc.) are instantiated **fresh on every orchestrator tool call** — this is intentional for HIPAA multi-tenant isolation (no cross-request state leakage).

### Two entry points

| File | Used when |
|---|---|
| `agentcore_app.py` | Deployed to AWS — `BedrockAgentCoreApp` serves `/invocations` on port 8080 |
| `main.py` | Local development only — interactive CLI, never deployed |

### Search pipeline

`tools/search_tools.py` exports four `@tool`-decorated functions (one per domain), each calling `_hybrid_search()`:
1. Embeds the query via Bedrock Titan (1024-dim)
2. Runs BM25 lexical search against the `text` field
3. Runs KNN semantic search against the `vector` field (HNSW/Faiss)
4. Merges results with Reciprocal Rank Fusion (`k=60`)

The four domain tools are bundled as `ALL_SEARCH_TOOLS` and given to each sub-agent.

### OpenSearch client

`get_opensearch_client()` in `etl/opensearch_indexer.py` uses `AWSV4SignerAuth` with `boto3.Session().get_credentials()`. Set `OPENSEARCH_SERVICE=aoss` for serverless. Both the ETL and search tools use this same factory.

### Configuration

All config lives in `config/settings.py` as typed module-level constants loaded via `os.getenv()`. The `.env` file is loaded by `python-dotenv` at import time. The test `conftest.py` sets `os.environ.setdefault()` values **before** any app import — this means `.env` values never override test defaults.

Key env vars: `OPENSEARCH_HOST`, `S3_BUCKET`, `BEDROCK_MODEL_ID`, `BEDROCK_EMBED_MODEL_ID`, `AUDIT_LOG_BUCKET` (set to `""` to disable S3 audit writes locally).

## Key Rules

### Testing

- `tests/conftest.py` must remain the **first** thing pytest loads — never import app modules at the top of test files before conftest runs
- Unit tests: no marker; integration tests: `@pytest.mark.integration`
- Do NOT mock OpenSearch in integration tests — they must hit a real instance at `localhost:9200`

### Compliance (HIPAA/GDPR)

- All logging must go through `audit()` or `_mask_phi()` in `utils/logger.py` — never log raw query strings directly
- `check_domain_access(role, domain)` in `utils/compliance.py` is the RBAC gate — call it before returning search results in new tools
- `AUDIT_LOG_BUCKET=""` disables real S3 writes (safe for local dev and unit tests)
- `data_retention_days=2555` (7 years) in prod — HIPAA minimum

### Terraform

- Do NOT touch `terraform/shared/` without explicit user confirmation — it holds the S3 state bucket and ECR repos with `prevent_destroy=true`
- AWS provider pinned to `~> 6.18` (required for `aws_bedrockagentcore_agent_runtime`)
- The `agentcore` module provisions the agent runtime; `ecs` module handles only the ETL batch job
- Each environment has its own IAM role (`AWS_DEPLOY_ROLE_ARN_DEV/QA/PROD`) — never share roles across envs
- Backend config passed via `-backend-config` flags in CI/CD, not stored in `.tf` files

### RAGAS Evaluations

- Retrieval eval monkey-patches `_embed_query` with a SHA-256 deterministic fake — no Bedrock calls, no Docker required if you provide your own OpenSearch
- Eval indices are prefixed `eval-medical-*` — always separate from production indices
- Thresholds (in `run_evals.py`): context_precision ≥ 0.50, context_recall ≥ 0.40, faithfulness ≥ 0.70, response_relevancy ≥ 0.60, rouge_score ≥ 0.15

### CI/CD

- CI: lint → unit tests → integration → docker-build → tf-validate → tf-plan (every push/PR to `main`/`master`)
- CD: dev → qa → prod sequentially; prod requires manual approval in GitHub Environments
- GitHub OIDC for AWS auth — no static keys; deploy role ARNs stored as secrets
- Set repo variable `ENABLE_GENERATION_EVAL=true` to enable generation eval in CI

## OpenSearch Index Names

| Domain | Index |
|---|---|
| Disease Study | `medical-disease-study` |
| Medicine Study | `medical-medicine-study` |
| Medicine Expiry | `medical-medicine-expiry` |
| Equipment Study | `medical-equipment-study` |
| RAGAS Eval | `eval-medical-*` |

## GitHub Actions Secrets & Variables

| Name | Type | Description |
|---|---|---|
| `AWS_DEPLOY_ROLE_ARN_DEV` | Secret | IAM role ARN for dev |
| `AWS_DEPLOY_ROLE_ARN_QA` | Secret | IAM role ARN for qa |
| `AWS_DEPLOY_ROLE_ARN_PROD` | Secret | IAM role ARN for prod |
| `TF_STATE_BUCKET` | Variable | S3 bucket for Terraform state |
| `TF_LOCK_TABLE` | Variable | DynamoDB table for Terraform locks |
| `AWS_REGION` | Variable | e.g. `us-east-1` |
| `ECR_APP_IMAGE_URL` | Variable | ECR URL for app image |
| `ECR_ETL_IMAGE_URL` | Variable | ECR URL for ETL image |
| `ENABLE_GENERATION_EVAL` | Variable | Set to `"true"` to run generation eval in CI |
