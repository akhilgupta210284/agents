# /add-domain — Add a new search domain end-to-end

You are adding a new document domain to the Medical Document Intelligence platform.
This touches **six files** across config, tools, compliance, ETL, and tests.
Missing any step will cause silent failures (RBAC gaps, missing indices, broken ETL).

## What you need from the user first

If any of the following are missing, ask before proceeding:
- **Domain key** — snake_case identifier, e.g. `clinical_trial`
- **Display name** — e.g. "Clinical Trial"
- **OpenSearch index name** — e.g. `medical-clinical-trial`
- **S3 prefix** — e.g. `medical-docs/clinical-trial/`
- **Which roles** should have access (clinician / lab_technician / administrator / researcher)
- **Example queries** — 2-3 queries a user would ask to hit this domain

---

## Step 1 — Read every file you will modify

Read these before writing anything:
- `config/settings.py` — OPENSEARCH_INDICES and S3_PREFIXES dicts
- `tools/search_tools.py` — domain tool pattern and ALL_SEARCH_TOOLS list
- `utils/compliance.py` — ALLOWED_DOMAINS_BY_ROLE dict
- `etl/opensearch_indexer.py` — index mapping pattern
- `.env.example` — env var documentation
- `agents/orchestrator.py` — domain list in _ORCHESTRATOR_PROMPT
- `tests/unit/test_search_tools.py` — test pattern to follow

## Step 2 — `config/settings.py`

Add to **both** dicts:

```python
OPENSEARCH_INDICES: dict[str, str] = {
    ...existing...
    "{domain_key}": "{index_name}",       # ADD THIS
}

S3_PREFIXES: dict[str, str] = {
    ...existing...
    "{domain_key}": os.getenv("S3_PREFIX_{DOMAIN_UPPER}", "{s3_prefix}"),  # ADD THIS
}
```

## Step 3 — `tools/search_tools.py`

Add a new `@tool` function following the exact pattern of `search_disease_study`:

```python
@tool
def search_{domain_key}(query: str, top_k: int = 5) -> str:
    """
    Hybrid search over the {Display Name} document corpus.

    Args:
        query: {Natural-language description of valid query topics}.
        top_k: Maximum number of passages to return (default 5).

    Returns:
        Relevant text passages with source file references.
    """
    return _hybrid_search("{domain_key}", query, top_k)
```

Then add it to `ALL_SEARCH_TOOLS`:
```python
ALL_SEARCH_TOOLS = [
    search_disease_study,
    search_medicine_study,
    search_medicine_expiry,
    search_equipment_study,
    search_{domain_key},   # ADD THIS
]
```

## Step 4 — `utils/compliance.py`

Add the domain to every role that should have access:

```python
ALLOWED_DOMAINS_BY_ROLE: dict[str, list[str]] = {
    "clinician":      [..., "{domain_key}"],   # if clinicians need access
    "lab_technician": [...],
    "administrator":  list(OPENSEARCH_INDICES.keys()),   # auto-includes new domain
    "researcher":     list(OPENSEARCH_INDICES.keys()),   # auto-includes new domain
}
```

**HIPAA rule**: "administrator" and "researcher" use `list(OPENSEARCH_INDICES.keys())` which
auto-includes new domains. Only clinician and lab_technician need manual updates.
Confirm with the user which roles need access before adding.

## Step 5 — `etl/opensearch_indexer.py`

Read the file first. Add the new index name to any list/dict that iterates over all indices
for index creation or mapping setup. The index mapping must match the existing pattern
(text field + vector field with dimension 1024).

## Step 6 — `agents/orchestrator.py`

Add the new domain to the domain list in `_ORCHESTRATOR_PROMPT`:
```
  • {Display Name} — {brief description of document types}
```

## Step 7 — `.env.example`

Add the new env var with a descriptive comment:
```bash
S3_PREFIX_{DOMAIN_UPPER}=medical-docs/{domain-slug}/   # S3 prefix for {Display Name} docs
```

## Step 8 — `CLAUDE.md`

Add the new domain to the OpenSearch Index Names table:
```markdown
| {Display Name} | `{index_name}` |
```

## Step 9 — Unit tests

Add tests to `tests/unit/test_search_tools.py` (or create `tests/unit/test_{domain_key}_search.py`):
1. `search_{domain_key}` is in `ALL_SEARCH_TOOLS`
2. Calling `search_{domain_key}` with a mocked `_hybrid_search` routes to the correct domain key
3. The new role access is correct in `ALLOWED_DOMAINS_BY_ROLE`

Run tests:
```bash
.venv/Scripts/python -m pytest tests/unit -v
```

## Checklist before reporting done

- [ ] `OPENSEARCH_INDICES` updated in `config/settings.py`
- [ ] `S3_PREFIXES` updated in `config/settings.py`
- [ ] `search_{domain_key}` tool added to `tools/search_tools.py`
- [ ] New tool added to `ALL_SEARCH_TOOLS`
- [ ] `ALLOWED_DOMAINS_BY_ROLE` updated in `utils/compliance.py` for correct roles
- [ ] `etl/opensearch_indexer.py` updated for new index
- [ ] Domain added to orchestrator system prompt
- [ ] `.env.example` updated with new env var
- [ ] `CLAUDE.md` index table updated
- [ ] Unit tests written and passing
