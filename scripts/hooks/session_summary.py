"""
Stop hook: print a compliance checklist at the end of every Claude Code session.

Reminds engineers of the HIPAA/GDPR gates and test requirements before they push.
Always exits 0 — informational only.
"""
from __future__ import annotations

import json
import sys

try:
    json.load(sys.stdin)  # consume stdin (Stop hook may pass session data)
except Exception:
    pass

CHECKLIST = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SESSION COMPLETE — pre-push compliance checklist
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [ ] No raw PHI in logs — audit() / _mask_phi() only
  [ ] New search tools call check_domain_access() before returning results
  [ ] Sub-agents instantiated fresh per call (no cached agent state)
  [ ] assert_tls_endpoint() called for any new non-localhost OpenSearch connections
  [ ] strip_sensitive_metadata() used before indexing any document metadata
  [ ] DATA_RETENTION_DAYS not reduced below 2555 (7-year HIPAA minimum)
  [ ] Unit tests pass: .venv/Scripts/python -m pytest tests/unit -v
  [ ] terraform/shared/ NOT modified without explicit manager confirmation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

print(CHECKLIST)
sys.exit(0)
