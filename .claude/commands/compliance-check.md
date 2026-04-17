# /compliance-check — HIPAA / GDPR audit of current branch changes

You are performing a pre-PR compliance audit on the changes in this branch.
This is a read-only audit — do NOT modify code unless the user explicitly asks you to fix findings.

## Step 1 — Identify changed files

```bash
git diff --name-only main
```

For each changed `.py` file, read it fully before auditing.

## Step 2 — HIPAA § 164.312: Audit logging

For every changed file, check:

**2a. No raw query strings in logs**
Search for any direct use of `logging.info`, `logging.debug`, `print`, `logger.info`, etc.
that passes a query string or user-provided text without masking:
```bash
git diff main -- '*.py' | grep -E "^\+" | grep -E "(log\.|print|logger)\("
```
Flag any that log `query`, `user_input`, or similar variables without `_mask_phi()` wrapping.

**2b. All data-access events use `audit()`**
Every function that reads from OpenSearch, calls Bedrock, or returns data to a user
must call `audit(event_type=..., user_id=..., ...)` from `utils/logger.py`.
Flag any new search tool or agent function that skips this.

**2c. `audit()` call completeness**
For each `audit()` call in changed files, verify all required fields are present:
- `event_type` — non-empty string
- `user_id` — passed through, not hardcoded
- `query` — the user's query (will be masked internally)
- `domain` — one of the four known domains

## Step 3 — HIPAA § 164.308: Access control (RBAC)

**3a. New search tools have RBAC gate**
Every new `@tool` function in `tools/search_tools.py` or any new file must call
`check_domain_access(user_role, domain)` before returning search results.

Check if `check_domain_access` is imported and called in every new tool:
```bash
git diff main -- 'tools/*.py' | grep -E "^\+"
```

**3b. New domains added to `ALLOWED_DOMAINS_BY_ROLE`**
If `OPENSEARCH_INDICES` was changed, verify the new domain key also appears in
`ALLOWED_DOMAINS_BY_ROLE` in `utils/compliance.py`.

**3c. No role escalation**
Verify that no existing role was given broader access than it had before.
Compare the before/after of `ALLOWED_DOMAINS_BY_ROLE`.

## Step 4 — HIPAA § 164.312(e): Encryption in transit

**4a. `assert_tls_endpoint()` called for new connections**
If any new OpenSearch client is created outside `etl/opensearch_indexer.py`,
verify `assert_tls_endpoint(host)` is called before use.

**4b. No hardcoded `http://` endpoints**
```bash
git diff main -- '*.py' | grep -E "^\+" | grep -E "http://"
```
Flag any `http://` that isn't `localhost` or a test fixture.

## Step 5 — GDPR Art. 25: Data minimisation

**5a. `strip_sensitive_metadata()` called before indexing**
If `etl/` files were changed, verify that `strip_sensitive_metadata(metadata)` from
`utils/compliance.py` is called on document metadata before it's passed to
`opensearch_client.index()`.

**5b. No new PHI fields added to index mappings**
Check that no new field names match `SENSITIVE_METADATA_KEYS`:
`{"patient_id", "mrn", "dob", "ssn", "nhs_number"}`

## Step 6 — GDPR Art. 17: Data retention

**6a. `DATA_RETENTION_DAYS` not reduced**
If `config/settings.py` was changed:
```bash
git diff main -- config/settings.py | grep DATA_RETENTION_DAYS
```
Flag if the value was reduced below 2555 (7-year HIPAA minimum).

## Step 7 — Terraform safety

**7a. `terraform/shared/` not modified**
```bash
git diff --name-only main | grep terraform/shared
```
If any files appear: STOP and flag immediately. Shared infra requires manager confirmation.

**7b. No role ARN cross-contamination**
If Terraform files were changed, verify that no environment's IAM role ARN is referenced
in another environment's module.

## Step 8 — Architecture integrity

**8a. Sub-agent isolation**
In any changed `agents/*.py` file, verify that `build_*_agent()` functions construct
a new `Agent(...)` on every call. Flag any module-level `Agent(...)` instantiation.

**8b. No secrets in code**
```bash
git diff main -- '*.py' '*.tf' '*.yml' | grep -E "^\+" | grep -iE "(secret|password|key|token)\s*=\s*['\"][^'\"]{8,}"
```

## Output format

Report findings in this format:

```
COMPLIANCE AUDIT — {branch name} vs main
Date: {today}
Files reviewed: {count}

CRITICAL (must fix before merge):
  [C1] {file}:{line} — {description of violation}

WARNING (should fix, will not block):
  [W1] {file}:{line} — {description}

PASSED:
  ✓ Audit logging — all data-access events use audit()
  ✓ RBAC gates — all search tools call check_domain_access()
  ... etc

VERDICT: PASS / FAIL
```

If FAIL, list the minimum changes required to reach PASS.
Do not auto-fix unless the user asks. Present findings and wait.
