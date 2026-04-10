# Medical Document Intelligence — Multi-Agent Application

A HIPAA/GDPR-aware multi-agent system built with **Strands Agents** and **AWS Bedrock**.
Four specialized agents collaborate to answer questions, generate summaries, and create study questions from medical document corpora stored in S3.

---

## Architecture

```
User Query
    │
    ▼
┌──────────────────────────────────────┐
│  Orchestrator (get_intent)           │   ← Routes by intent
│  agents/orchestrator.py              │
└──────┬───────────────────────────────┘
       │  tool calls
  ┌────┴──────────────────────────────────────┐
  │                                           │
  ▼                  ▼                        ▼
┌──────────┐   ┌──────────┐   ┌───────────────────────┐
│Summarizer│   │ QA Agent │   │Question Gen Agent     │
│  Agent   │   │          │   │                       │
└────┬─────┘   └────┬─────┘   └──────────┬────────────┘
     │              │                    │
     └──────────────┴────────────────────┘
                    │  @tool calls
         ┌──────────┴──────────┐
         │   Hybrid Search     │   tools/search_tools.py
         │  BM25 + KNN (RRF)   │
         └──────────┬──────────┘
                    │
         ┌──────────┴──────────┐
         │    OpenSearch       │   one index per domain
         │  (lexical + vector) │
         └─────────────────────┘
                    ▲
                    │  ETL
         ┌──────────┴──────────┐
         │  S3 Document Store  │
         │  4 domain prefixes  │
         └─────────────────────┘
```

### Agent Responsibilities

| Agent | Name | System Prompt Focus | Temperature |
|-------|------|---------------------|-------------|
| **Orchestrator** | `get_intent` | Intent detection + routing | 0.0 |
| **Summarizer** | `MedSummarizer` | Structured document summaries | 0.2 |
| **QA** | `MedQA` | Grounded, cited Q&A | 0.0 |
| **Question Gen** | `MedQGen` | Bloom's taxonomy questions | 0.7 |

### Document Domains → S3 Prefixes → OpenSearch Indices

| Domain | S3 Prefix | OpenSearch Index |
|--------|-----------|------------------|
| Disease Study | `medical-docs/disease-study/` | `medical-disease-study` |
| Medicine Study | `medical-docs/medicine-study/` | `medical-medicine-study` |
| Medicine Expiry | `medical-docs/medicine-expiry/` | `medical-medicine-expiry` |
| Equipment Study | `medical-docs/equipment-study/` | `medical-equipment-study` |

---

## Hybrid Search

Each OpenSearch index stores both:
- **`text`** field → BM25 lexical search (exact keyword match)
- **`vector`** field → KNN semantic search (Amazon Titan embeddings, 1024-dim, HNSW/Faiss)

Results are merged using **Reciprocal Rank Fusion (RRF)** — a parameter-free fusion method that consistently outperforms weighted score combination.

---

## HIPAA / GDPR Compliance

| Requirement | Implementation |
|-------------|---------------|
| Encryption at rest | S3 SSE-KMS, OpenSearch encryption |
| Encryption in transit | HTTPS enforced (`assert_tls_endpoint`) |
| Audit trail | Every query written to S3 `audit-logs/` with KMS encryption |
| PHI masking | `_mask_phi()` strips SSN, phone, email before logs |
| Minimum necessary access | `check_domain_access(role, domain)` RBAC guard |
| Right to erasure (GDPR Art. 17) | `delete_user_data(user_id, client)` |
| Data minimisation (GDPR Art. 25) | `strip_sensitive_metadata()` removes PHI keys before indexing |
| Data retention | Configurable `DATA_RETENTION_DAYS` (default 2555 = 7 years, HIPAA minimum) |

---

## Setup

### 1. Clone and install

```bash
cd "C:\Users\DLP-I516-147\OneDrive - UsefulBI Corporation\Documents\claude-code\multi-agent"
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

### 2. Configure environment

```bash
copy .env.example .env
# Edit .env with your S3 bucket, OpenSearch endpoint, etc.
```

### 3. AWS prerequisites

| Service | What you need |
|---------|---------------|
| **S3** | Bucket with documents under the four prefixes |
| **Bedrock** | Model access: Claude 3.7 Sonnet + Titan Embed Text v2 |
| **OpenSearch** | Managed cluster or Serverless collection (set `OPENSEARCH_SERVICE=aoss` for serverless) |
| **IAM** | Role/user with S3 read, Bedrock invoke, OpenSearch write + read |

### 4. Run the ETL pipeline

```bash
# Index all domains
python -m etl.run_etl

# Index a single domain
python -m etl.run_etl --domain disease_study

# Re-build indices from scratch
python -m etl.run_etl --recreate
```

### 5. Run the application

```bash
# Interactive mode
python main.py

# Single query
python main.py --query "Summarize the key findings on Type 2 Diabetes"

# With user identifier (for audit trail)
python main.py --user-id dr.smith --query "What drugs interact with Metformin?"
```

---

## Example Queries

```
# Summarisation
"Give me an overview of the latest disease study on hypertension"
"Summarize the storage requirements for insulin"

# Question Answering
"What are the contraindications for Warfarin according to the medicine study?"
"How often should the MRI equipment be calibrated?"
"What is the shelf life of Amoxicillin after opening?"

# Question Generation
"Generate study questions on cardiovascular disease risk factors"
"Create a quiz on medicine expiry and storage"
```

---

## Project Structure

```
multi-agent/
├── main.py                       # CLI entry point
├── requirements.txt
├── .env.example
├── config/
│   └── settings.py               # All config via env vars
├── etl/
│   ├── s3_reader.py              # Read PDFs/text from S3
│   ├── document_processor.py     # Word-level chunker
│   ├── opensearch_indexer.py     # Create indices + bulk embed + index
│   └── run_etl.py                # ETL CLI
├── agents/
│   ├── orchestrator.py           # get_intent — routes to sub-agents
│   ├── summarizer_agent.py       # MedSummarizer
│   ├── qa_agent.py               # MedQA
│   └── question_gen_agent.py     # MedQGen
├── tools/
│   └── search_tools.py           # 4 domain hybrid-search @tools
└── utils/
    ├── logger.py                 # HIPAA audit logger → S3
    └── compliance.py             # GDPR erasure, RBAC, PHI guards
```
