# /new-agent — Scaffold a new sub-agent

You are adding a new specialist sub-agent to the Medical Document Intelligence platform.
The user will tell you the agent's name and purpose. Follow every step below exactly —
this is the established team pattern; deviation creates inconsistency across the codebase.

## What you need from the user first

If any of the following are missing from their request, ask for them before proceeding:
- **Agent name** (e.g. `classifier`, `comparator`, `translator`)
- **One-sentence purpose** (what medical task does it perform?)
- **Intent signals** (what user phrases should the orchestrator route to this agent?)

---

## Step 1 — Read existing agents for context

Read these files before writing a single line:
- `agents/qa_agent.py` — the canonical sub-agent pattern
- `agents/orchestrator.py` — where you will register the new agent
- `config/settings.py` — for AWS_REGION and BEDROCK_MODEL_ID imports
- `tools/search_tools.py` — for ALL_SEARCH_TOOLS import

## Step 2 — Create `agents/{name}_agent.py`

Follow this exact structure (copy from `qa_agent.py`):

```python
"""
{Name} Agent.

{One-sentence description of purpose}.
"""
from __future__ import annotations

from strands import Agent
from strands.models import BedrockModel

from config.settings import AWS_REGION, BEDROCK_MODEL_ID
from tools.search_tools import ALL_SEARCH_TOOLS

_SYSTEM_PROMPT = """You are Med{Name}, a ... {role-specific instructions}

Your responsibilities:
1. ...
2. ...
3. Do NOT include patient identifiers or PHI in your output.
"""


def build_{name}_agent() -> Agent:
    model = BedrockModel(
        model_id=BEDROCK_MODEL_ID,
        region_name=AWS_REGION,
        temperature=0.0,
        max_tokens=2048,
    )
    return Agent(
        model=model,
        system_prompt=_SYSTEM_PROMPT,
        tools=ALL_SEARCH_TOOLS,
    )
```

**HIPAA rule**: the system prompt MUST include "Do NOT include patient identifiers or PHI in your output."

**Isolation rule**: `build_{name}_agent()` must construct a NEW `Agent` instance on every
call — never cache the agent object at module level. This is mandatory for multi-tenant isolation.

## Step 3 — Register in `agents/orchestrator.py`

Add two things:

**A) A `@tool` wrapper function** (after the existing tool wrappers, before `_ORCHESTRATOR_PROMPT`):

```python
@tool
def {name}(query: str) -> str:
    """
    Delegate to the {Name} Agent.
    Use this tool when the user {intent signals from the user's request}.

    Args:
        query: The user's full request.

    Returns:
        {Description of what the agent returns}.
    """
    agent = build_{name}_agent()
    return str(agent(query))
```

**B) Import** at the top of orchestrator.py:
```python
from agents.{name}_agent import build_{name}_agent
```

**C) Routing row** in `_ORCHESTRATOR_PROMPT` routing table:
```
├──────────────────────────────┼───────────────────────────────────────┤
│ {intent signals}             │ {name}(query)                         │
```

**D) Add to tools list** in `build_orchestrator()`:
```python
tools=[summarizer, qa, question_generator, {name}],
```

## Step 4 — Write unit tests

Create `tests/unit/test_{name}_agent.py`. It must cover:
1. `build_{name}_agent()` returns an `Agent` instance
2. Each call to `build_{name}_agent()` returns a **new** object (isolation test)
3. The system prompt contains "PHI" (compliance marker test)

Pattern to follow: `tests/unit/test_search_tools.py`

Run the tests immediately:
```bash
.venv/Scripts/python -m pytest tests/unit/test_{name}_agent.py -v
```
Do not report the task complete if any test fails.

## Step 5 — Verify routing end-to-end

Run a quick smoke test of the orchestrator import:
```bash
.venv/Scripts/python -c "from agents.orchestrator import build_orchestrator; o = build_orchestrator(); print('OK')"
```

## Checklist before reporting done

- [ ] `agents/{name}_agent.py` created with `build_{name}_agent()` factory
- [ ] Agent constructed fresh on every call (not cached)
- [ ] System prompt includes PHI prohibition
- [ ] `@tool` wrapper added to `orchestrator.py`
- [ ] Routing row added to `_ORCHESTRATOR_PROMPT`
- [ ] `tools=[...]` list updated in `build_orchestrator()`
- [ ] Unit tests written and passing
- [ ] Orchestrator imports without error
