# CLAUDE.md — Medical Document Intelligence Multi-Agent App

## Project Overview

A HIPAA/GDPR-compliant medical RAG (Retrieval-Augmented Generation) system built with:
- **Strands Agents** framework + AWS Bedrock (Claude 3.7 Sonnet, Titan Embed v2)
- **Amazon Bedrock AgentCore Runtime** — managed serverless runtime for the agent (replaced ECS Fargate for the app)
- **OpenSearch** with hybrid search (BM25 lexical + KNN semantic, merged via Reciprocal Rank Fusion)
- **4 document domains**: disease study, medicine study, medicine expiry, equipment study
- **RAGAS** evaluation framework for retrieval and generation quality
- **Terraform** infrastructure (dev / qa / prod) deployed via GitHub Actions CI/CD

---

## Local Environment

- **OS**: Windows 11, shell: bash (use Unix syntax — forward slashes, not backslashes)
- **Python**: 3.14.3 — always use `.venv/Scripts/python`, never bare `python` or `python3`
- **pip**: always use `.venv/Scripts/python -m pip`, never bare `pip`
- **Docker**: NOT installed — integration tests and RAGAS retrieval eval require Docker Desktop
- **AWS**: credentials active (account 686019146554, user `akhil`), Bedrock + S3 access available

---

## Commands — always run from project root

```bash
# Unit tests (no Docker needed)
.venv/Scripts/python -m pytest tests/unit -v

# Integration tests (requires OpenSearch via Docker)
docker compose up opensearch -d
.venv/Scripts/python -m pytest tests/integration -m integration -v

# Linting
.venv/Scripts/python -m ruff check .

# RAGAS retrieval eval (requires OpenSearch via Docker)
.venv/Scripts/python -m evals.run_evals --mode retrieval

# RAGAS generation eval (requires AWS Bedrock)
.venv/Scripts/python -m evals.run_evals --mode generation

# Full RAGAS eval (retrieval + generation)
.venv/Scripts/python -m evals.run_evals --mode all

# Run the app (interactive mode — requires OpenSearch)
.venv/Scripts/python main.py

# Install/refresh dependencies
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m pip install -r requirements-test.txt
```

---

## Project Structure

```
multi-agent/
├── agentcore_app.py             # AgentCore Runtime entry point — BedrockAgentCoreApp on port 8080
├── main.py                      # Local CLI entry point (interactive + single-shot modes, not deployed)
├── config/settings.py           # All config via os.getenv(), loads .env via python-dotenv
├── agents/
│   ├── orchestrator.py          # build_orchestrator() — main Strands agent
│   ├── summarizer_agent.py
│   ├── qa_agent.py
│   └── question_gen_agent.py
├── tools/search_tools.py        # _rrf_merge(), _hybrid_search(), 4 @tool functions
├── etl/
│   ├── document_processor.py    # Word-level sliding window chunker
│   ├── opensearch_indexer.py    # create_index(), index_chunks(), _embed()
│   ├── s3_reader.py             # read_domain_documents(), PDF via pdfplumber
│   └── run_etl.py               # ETL entry point
├── utils/
│   ├── logger.py                # audit(), _mask_phi() — PHI masking (SSN/email/phone)
│   └── compliance.py            # check_domain_access(), strip_sensitive_metadata()
├── evals/
│   ├── golden_dataset.py        # 12-entry corpus + 12 Q&A SAMPLES with reference_contexts
│   ├── seed_index.py            # Deterministic vectors (SHA-256), no Bedrock needed
│   ├── retrieval_eval.py        # NonLLMContextPrecision + NonLLMContextRecall
│   ├── generation_eval.py       # Faithfulness + ResponseRelevancy + RougeScore
│   └── run_evals.py             # CLI entry point, writes eval-report.json
├── tests/
│   ├── conftest.py              # Injects safe env defaults BEFORE any app import
│   ├── unit/                    # No external services needed
│   └── integration/             # Requires OpenSearch at localhost:9200
├── terraform/
│   ├── shared/                  # S3 state, DynamoDB lock, ECR repos, GitHub OIDC
│   ├── modules/                 # networking, iam, s3, opensearch, agentcore, ecs (ETL only)
│   └── environments/            # dev / qa / prod — each has backend.tf + tfvars
├── .github/workflows/
│   ├── ci.yml                   # lint → unit → integration → docker-build → tf-validate → tf-plan
│   ├── cd.yml                   # meta → build-push → deploy-dev → deploy-qa → deploy-prod
│   └── ragas-eval.yml           # retrieval-eval → generation-eval → eval-gate
├── Dockerfile                   # App image (multi-stage, non-root appuser)
├── Dockerfile.etl               # ETL image
├── docker-compose.yml           # OpenSearch + optional dashboards, etl, app profiles
├── requirements.txt
├── requirements-test.txt
├── pytest.ini
└── .env                         # Local overrides (not committed)
```

---

## Key Rules

### Testing
- Always run unit tests before any code change: `.venv/Scripts/python -m pytest tests/unit -v`
- `tests/conftest.py` sets safe defaults via `os.environ.setdefault()` — these win over `.env` during pytest
- Unit tests are marked with no marker; integration tests use `@pytest.mark.integration`
- Do NOT mock OpenSearch in integration tests — they must hit a real instance

### Configuration
- All config is in `config/settings.py` via `os.getenv()` — never hardcode values
- `.env` file is the local override; CI/CD uses GitHub Actions `env:` blocks; prod uses ECS task env vars injected by Terraform
- `AUDIT_LOG_BUCKET=""` disables real S3 audit writes (safe for local dev and unit tests)

### Compliance (HIPAA/GDPR)
- PHI masking is in `utils/logger.py::_mask_phi()` — covers SSN, email, phone, patient IDs
- Audit logs use KMS encryption and S3 Object Lock (COMPLIANCE mode) in prod
- Do NOT add logging that could expose PHI — always route through `audit()` or `_mask_phi()`
- `data_retention_days=2555` (7 years) in prod — HIPAA minimum

### Terraform
- Do NOT touch `terraform/shared/` without explicit user confirmation — it holds S3 state bucket and ECR repos with `prevent_destroy=true`
- Each environment (dev/qa/prod) has its own IAM role (`AWS_DEPLOY_ROLE_ARN_DEV/QA/PROD`) — never share roles across envs
- Backend config is passed via `-backend-config` flags in CI/CD, not stored in `.tf` files
- Terraform version pinned to `1.7.5`
- AWS provider pinned to `~> 6.18` (required for `aws_bedrockagentcore_agent_runtime`)
- The `agentcore` module provisions the agent runtime; the `ecs` module now handles only the ETL batch job

### RAGAS Evaluations
- Retrieval eval uses deterministic fake vectors (SHA-256 seeded) — no Bedrock needed
- Generation eval requires real Bedrock credentials
- Eval indices are named `eval-medical-*` — separate from production indices
- Thresholds: context_precision ≥ 0.50, context_recall ≥ 0.40, faithfulness ≥ 0.70, response_relevancy ≥ 0.60, rouge_score ≥ 0.15
- Report is written to `eval-report.json` after each run

### CI/CD
- CI runs on every push and PR to `main`/`master`
- CD deploys sequentially: dev → qa → prod (prod requires manual approval in GitHub Environments)
- GitHub OIDC is used for AWS auth — no static AWS keys stored in secrets (except deploy role ARNs)
- `ENABLE_GENERATION_EVAL` repo variable must be set to `"true"` to enable generation eval in CI

---

## OpenSearch Index Names

| Domain | Index |
|---|---|
| Disease Study | `medical-disease-study` |
| Medicine Study | `medical-medicine-study` |
| Medicine Expiry | `medical-medicine-expiry` |
| Equipment Study | `medical-equipment-study` |
| RAGAS Eval (all) | `eval-medical-*` |

---

## GitHub Actions Secrets & Variables Required

| Name | Type | Description |
|---|---|---|
| `AWS_DEPLOY_ROLE_ARN_DEV` | Secret | IAM role ARN for dev deploys |
| `AWS_DEPLOY_ROLE_ARN_QA` | Secret | IAM role ARN for qa deploys |
| `AWS_DEPLOY_ROLE_ARN_PROD` | Secret | IAM role ARN for prod deploys |
| `TF_STATE_BUCKET` | Variable | S3 bucket for Terraform state |
| `TF_LOCK_TABLE` | Variable | DynamoDB table for Terraform locks |
| `AWS_REGION` | Variable | e.g. `us-east-1` |
| `ECR_APP_IMAGE_URL` | Variable | ECR URL for app image |
| `ECR_ETL_IMAGE_URL` | Variable | ECR URL for ETL image |
| `ENABLE_GENERATION_EVAL` | Variable | Set to `"true"` to run generation eval in CI |
