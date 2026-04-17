# /pr-review — Pull request review for this codebase

You are reviewing a pull request against the Medical Document Intelligence platform standards.
Be thorough, direct, and specific. Reference file paths and line numbers.
Do not approve a PR that has CRITICAL findings.

## Step 1 — Understand what changed

```bash
git diff --stat main
git log --oneline main..HEAD
git diff main
```

Read every changed file fully before forming opinions.

## Step 2 — Correctness

**2a. Does the code do what the PR description claims?**
Trace the execution path for the primary use case described in the PR.

**2b. Edge cases**
- What happens if OpenSearch returns 0 results?
- What happens if Bedrock embed call fails?
- What happens if a user's role is not in `ALLOWED_DOMAINS_BY_ROLE`?

**2c. Logic errors**
- Off-by-one in `_rrf_merge` rank calculation?
- Incorrect `top_k` slicing after merge?
- Missing `await` or wrong return type in async paths?

## Step 3 — HIPAA / GDPR compliance

Run `/compliance-check` mentally or explicitly for all changed files:

- All logging through `audit()` or `_mask_phi()` — no raw query strings
- `check_domain_access()` called before returning search results in new tools
- `strip_sensitive_metadata()` before any new OpenSearch index calls
- `assert_tls_endpoint()` for any new non-localhost connections
- `DATA_RETENTION_DAYS` not reduced
- No PHI field names in new index mappings
- `terraform/shared/` not touched

Flag any violation as **CRITICAL**.

## Step 4 — Architecture

**4a. Sub-agent isolation (HIPAA multi-tenant)**
Verify that every `build_*_agent()` call creates a fresh `Agent(...)`.
No agent instance should be assigned at module level or cached between requests.

**4b. Search tool registration**
If a new `@tool` is added, verify it appears in `ALL_SEARCH_TOOLS`.
If it doesn't, sub-agents won't have access to it.

**4c. Orchestrator routing completeness**
If a new agent is added, verify:
- `@tool` wrapper exists in `orchestrator.py`
- Routing row added to `_ORCHESTRATOR_PROMPT`
- Tool listed in `build_orchestrator()` `tools=[...]`

**4d. Config vs hardcodes**
No hardcoded index names, bucket names, region strings, or model IDs.
All must come from `config/settings.py` via `os.getenv()`.

## Step 5 — Tests

**5a. Coverage**
Run unit tests and check coverage on changed files:
```bash
.venv/Scripts/python -m pytest tests/unit -v --cov=. --cov-report=term-missing
```
New code with no test coverage is a **WARNING** (CRITICAL if it's a compliance path).

**5b. Test quality**
- Do tests mock at the right boundary (Bedrock/OpenSearch — not internal logic)?
- Is the agent isolation test present for any new `build_*_agent()` function?
- Are PHI-masking tests present for any new logging paths?

**5c. Integration tests**
If ETL or OpenSearch indexing code changed, are integration tests updated?
Note: integration tests require Docker — flag if they can't be run locally.

## Step 6 — Performance

**6a. No N+1 OpenSearch calls**
A single user query must result in at most 2 OpenSearch calls per domain tool
(1 lexical + 1 semantic). Flag if there's a loop calling `client.search()`.

**6b. Embed model efficiency**
`_embed_query` calls Bedrock on every search. Flag if it's called more than once
per tool invocation — embedding should happen once, then reused for both BM25 and KNN.

**6c. `top_k` bounds**
Verify `top_k` is not unbounded. Default 5, maximum should be reasonable (≤ 20).

## Step 7 — Terraform (if changed)

**7a. `shared/` not modified** — CRITICAL if it is
**7b. `prevent_destroy = true`** still on S3 state bucket and ECR repos
**7c. AWS provider version** still pinned to `~> 6.18`
**7d. No role ARNs shared across environments**
**7e. Backend config not stored in `.tf` files** — must use `-backend-config` flags

## Step 8 — CI/CD

If `.github/workflows/` changed:
- Lint → unit → integration → docker → tf-validate → tf-plan order preserved
- OIDC auth used (no static AWS keys)
- `ENABLE_GENERATION_EVAL` gate still in place for generation evals
- Prod deployment still requires manual approval in GitHub Environments

## Output format

```
PR REVIEW — {branch} → main
Author: {author}
Files: {count} changed, +{additions} -{deletions}

━━━ CRITICAL (must fix before merge) ━━━
[C1] tools/search_tools.py:45 — new search_foo tool missing check_domain_access() call
[C2] ...

━━━ WARNING (should fix) ━━━
[W1] agents/foo_agent.py — no unit tests for build_foo_agent()
[W2] ...

━━━ SUGGESTIONS ━━━
[S1] ...

━━━ PASSED ━━━
✓ Sub-agent isolation — all build_*_agent() construct fresh instances
✓ Audit logging — all new data-access events use audit()
✓ Terraform shared/ — not modified
✓ Tests — coverage on changed files ≥ existing baseline
... (list every check that passed)

VERDICT: APPROVE / REQUEST CHANGES / DISCUSS
```

Be specific. Vague comments ("consider adding tests") are not useful.
Cite the exact file, line, and what specifically needs to change.
