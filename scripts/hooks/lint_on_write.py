"""
PostToolUse hook: auto-run ruff --fix on every .py file written or edited.

Claude Code passes the tool input via stdin as JSON:
  {"session_id": "...", "tool_name": "Write|Edit", "tool_input": {"file_path": "..."}, ...}

Always exits 0 — we never block writes, we only fix style.
Ruff output is printed so Claude can see what was auto-corrected.
"""
from __future__ import annotations

import json
import subprocess
import sys

data = json.load(sys.stdin)
file_path: str = data.get("tool_input", {}).get("file_path", "")

if not file_path or not file_path.endswith(".py"):
    sys.exit(0)

result = subprocess.run(
    [
        ".venv/Scripts/python", "-m", "ruff", "check",
        file_path,
        "--fix",
        "--quiet",
    ],
    capture_output=True,
    text=True,
)

# returncode 0 = already clean, 1 = fixes applied, other = ruff error
if result.returncode not in (0, 1):
    print(f"[HOOK] ruff error on {file_path}:\n{result.stderr}", file=sys.stderr)
elif result.stdout.strip():
    print(f"[HOOK] ruff auto-fixed {file_path}:\n{result.stdout}")

sys.exit(0)
