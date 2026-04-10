"""
Medical Multi-Agent Application — Amazon Bedrock AgentCore Runtime Entry Point.

Wraps the Strands orchestrator with BedrockAgentCoreApp for hosting on
AgentCore Runtime.  AgentCore calls the @app.entrypoint function via
HTTP POST /invocations on port 8080.

Expected request payload (JSON):
    { "prompt": "<user query>", "user_id": "<optional user id>" }

Response:
    Plain string — the orchestrator's answer.
"""
from __future__ import annotations

import uuid

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from agents.orchestrator import build_orchestrator
from utils.logger import audit

app = BedrockAgentCoreApp()

# Build orchestrator once at cold-start — reused across all invocations
# within the same container instance.
_orchestrator = build_orchestrator()


@app.entrypoint
def invoke(payload: dict) -> str:
    """Route a user query through the orchestrator and return the response."""
    user_id = payload.get("user_id") or f"anon-{uuid.uuid4().hex[:8]}"
    query = payload.get("prompt", "")
    audit("QUERY", user_id=user_id, query=query, agent_name="orchestrator")
    response = _orchestrator(query)
    return str(response)


if __name__ == "__main__":
    app.run()
