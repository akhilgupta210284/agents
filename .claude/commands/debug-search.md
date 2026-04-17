# /debug-search — Diagnose hybrid search pipeline issues

You are systematically debugging the hybrid search pipeline in this codebase.
Work through each layer in order. Stop at the first layer that fails — that is the root cause.
Do not skip layers or jump to conclusions.

The user will tell you: which domain, what query, and what they expected vs got.
If they haven't provided these, ask before proceeding.

---

## Layer 1 — OpenSearch connectivity

```bash
curl -sf http://localhost:9200/_cluster/health | python -m json.tool
```

Expected: `"status": "green"` or `"status": "yellow"` (yellow = single-node, acceptable locally).

If this fails:
- Docker not running: `docker compose up opensearch -d`
- Wrong host/port: check `OPENSEARCH_HOST` and `OPENSEARCH_PORT` in `.env`
- SSL mismatch: check `OPENSEARCH_USE_SSL` vs actual endpoint scheme

## Layer 2 — Index exists and has documents

Replace `{index}` with the domain's index from `CLAUDE.md` (e.g. `medical-disease-study`):

```bash
curl -sf "http://localhost:9200/{index}/_count" | python -m json.tool
```

Expected: `"count"` > 0.

If count = 0:
- ETL hasn't been run: `.venv/Scripts/python -m etl.run_etl --domain {domain_key}`
- Wrong index name: verify against `OPENSEARCH_INDICES` in `config/settings.py`
- ETL ran against wrong bucket: check `S3_BUCKET` and `S3_PREFIXES[{domain_key}]` in `.env`

If index doesn't exist (404):
- Run ETL with recreate: `.venv/Scripts/python -m etl.run_etl --domain {domain_key} --recreate`

## Layer 3 — Index mapping is correct

```bash
curl -sf "http://localhost:9200/{index}/_mapping" | python -m json.tool
```

Check that:
- `"text"` field exists with `"type": "text"` (for BM25)
- `"vector"` field exists with `"type": "knn_vector"` and `"dimension": 1024` (for KNN)

If mapping is wrong:
- Recreate the index: `.venv/Scripts/python -m etl.run_etl --domain {domain_key} --recreate`
- If the ETL indexer code changed, read `etl/opensearch_indexer.py` to find the mapping definition

## Layer 4 — Bedrock embed model reachable

Run a quick embed test (replace `{query}` with the failing query):

```python
.venv/Scripts/python -c "
import boto3, json
from config.settings import BEDROCK_EMBED_MODEL_ID, AWS_REGION
client = boto3.client('bedrock-runtime', region_name=AWS_REGION)
resp = client.invoke_model(
    modelId=BEDROCK_EMBED_MODEL_ID,
    body=json.dumps({'inputText': '{query}'}),
    contentType='application/json', accept='application/json'
)
vec = json.loads(resp['body'].read())['embedding']
print(f'OK — vector dim: {len(vec)}, first 3 values: {vec[:3]}')
"
```

Expected: `OK — vector dim: 1024, first 3 values: [...]`

If this fails:
- AWS credentials not set: check `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` in `.env`
- Bedrock model not enabled in your AWS region: enable it in the Bedrock console
- Wrong model ID: verify `BEDROCK_EMBED_MODEL_ID` in `.env` vs `config/settings.py` default

## Layer 5 — BM25 lexical search returns results

```bash
curl -sf -X GET "http://localhost:9200/{index}/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "size": 5,
    "query": {
      "multi_match": {
        "query": "{query}",
        "fields": ["text"],
        "type": "best_fields"
      }
    },
    "_source": ["text", "filename", "chunk_index"]
  }' | python -m json.tool
```

Expected: `"hits.total.value"` > 0 and meaningful passages in `hits.hits[*]._source.text`.

If 0 results:
- Query terms don't appear in indexed documents — try simpler keywords
- Documents indexed without text field: check ETL chunking in `etl/`
- Analyser mismatch: check the index mapping's `analyzer` on the `text` field

## Layer 6 — KNN semantic search returns results

Use the vector from Layer 4 (copy the full vector output):

```bash
curl -sf -X GET "http://localhost:9200/{index}/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "size": 5,
    "query": {
      "knn": {
        "vector": {
          "vector": [PASTE_VECTOR_HERE],
          "k": 5
        }
      }
    },
    "_source": ["text", "filename", "chunk_index"]
  }' | python -m json.tool
```

Expected: results similar to or overlapping with Layer 5 results.

If 0 results:
- KNN plugin not installed: verify with `curl http://localhost:9200/_cat/plugins`
- Vectors not indexed (documents indexed before vector field added): recreate index and re-run ETL
- Dimension mismatch: compare `EMBED_DIMENSIONS` in `config/settings.py` with index mapping

## Layer 7 — RRF merge logic

If Layers 5 and 6 both return results but the final output is wrong, the issue is in `_rrf_merge`.

Read `tools/search_tools.py` lines around `_rrf_merge`. Check:
- Is `k=60` constant correct? (standard RRF, rarely the problem)
- Is `[:top_k]` slice applied after merge? (verify the merged list is being truncated)
- Is `doc_id` consistent between lexical and semantic hits? (should be `hit["_id"]`)

Add a temporary debug print to isolate:
```python
# in _hybrid_search, after merge:
print(f"DEBUG: lexical={len(lexical_hits)}, semantic={len(semantic_hits)}, merged={len(merged)}")
for i, doc in enumerate(merged[:3]):
    print(f"  [{i}] score={doc['score']:.4f} file={doc.get('filename')} chunk={doc.get('chunk_index')}")
```

## Layer 8 — RBAC gate

If results exist in OpenSearch but the tool returns nothing to the user, check RBAC:

Read `utils/compliance.py` and verify:
- The `user_role` being passed matches an entry in `ALLOWED_DOMAINS_BY_ROLE`
- The domain key is in that role's list
- `check_domain_access()` is actually being called before results are returned

## Summary

| Layer | What it tests | Tool to check |
|---|---|---|
| 1 | OpenSearch up | curl /_cluster/health |
| 2 | Index populated | curl /{index}/_count |
| 3 | Mapping correct | curl /{index}/_mapping |
| 4 | Bedrock reachable | Python embed test |
| 5 | BM25 returns results | curl _search (multi_match) |
| 6 | KNN returns results | curl _search (knn) |
| 7 | RRF merge correct | Read _rrf_merge code |
| 8 | RBAC not blocking | Read compliance.py |

Report which layer fails and paste the exact output. Do not guess — each layer's output
directly determines the root cause.
