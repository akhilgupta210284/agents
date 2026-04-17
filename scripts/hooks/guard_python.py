"""
PreToolUse hook: block bare python / pip in Bash tool calls.

Claude Code passes the Bash tool input via stdin as JSON:
  {"session_id": "...", "tool_name": "Bash", "tool_input": {"command": "..."}}

Exit 0  → allow the command through.
Exit 2  → block the command; stderr is shown to Claude as the reason.

Rule (from CLAUDE.md): always use .venv/Scripts/python, never bare python/pip.
"""
from __future__ import annotations

import json
import re
import sys

data = json.load(sys.stdin)
command: str = data.get("tool_input", {}).get("command", "")

# These patterns indicate bare python/pip usage (not prefixed with a venv path)
FORBIDDEN_RE = re.compile(
    r'(?:^|[\s;&|`(])'   # start of line or shell separator
    r'(python3?|pip3?)'  # bare interpreter or package manager
    r'(?=\s|$)',         # must be followed by whitespace or end
    re.MULTILINE,
)

# These patterns are safe even if they match FORBIDDEN_RE
ALLOWED_RE = re.compile(
    r'(?:'
    r'\.venv[/\\](?:Scripts|bin)[/\\]python'  # virtualenv python
    r'|python:3\.'                              # Docker image tag  e.g. python:3.11-slim
    r'|setup-python'                            # actions/setup-python step
    r'|which\s+python'                          # introspection only
    r'|command\s+-v\s+python'                   # introspection only
    r'|#.*python'                               # comment
    r')',
    re.IGNORECASE,
)

if ALLOWED_RE.search(command):
    sys.exit(0)

match = FORBIDDEN_RE.search(command)
if match:
    print(
        f"\n[HOOK] BLOCKED — bare '{match.group(1)}' detected.\n"
        f"  CLAUDE.md rule: always use .venv/Scripts/python\n"
        f"  Fix:  .venv/Scripts/python -m pip ...  (for pip)\n"
        f"        .venv/Scripts/python ...          (for python)\n"
        f"  Command: {command[:400]}\n",
        file=sys.stderr,
    )
    sys.exit(2)

sys.exit(0)
