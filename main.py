"""
Medical Multi-Agent Application — Entry Point.

Starts an interactive CLI session where users can ask questions about
the four medical document domains.  All queries are routed through the
get_intent orchestrator which delegates to the appropriate specialist agent.

Usage:
    python main.py                          # interactive mode
    python main.py --query "your question"  # single-shot mode
    python main.py --user-id user123        # provide user identifier (audit)
"""
from __future__ import annotations

import argparse
import sys
import uuid

from agents.orchestrator import build_orchestrator
from utils.logger import audit

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║        Medical Document Intelligence Platform                ║
║        Powered by Strands Agents + AWS Bedrock               ║
╠══════════════════════════════════════════════════════════════╣
║  Domains: Disease Study | Medicine Study |                   ║
║           Medicine Expiry | Equipment Study                  ║
╠══════════════════════════════════════════════════════════════╣
║  Agents : Summarizer | QA | Question Generator               ║
║  Type 'exit' or 'quit' to stop                               ║
╚══════════════════════════════════════════════════════════════╝
"""


def run_query(orchestrator, query: str, user_id: str) -> str:
    """Send one query through the orchestrator and return the response."""
    audit("QUERY", user_id=user_id, query=query, agent_name="orchestrator")
    response = orchestrator(query)
    return str(response)


def interactive_mode(user_id: str) -> None:
    print(BANNER)
    orchestrator = build_orchestrator()

    while True:
        try:
            query = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not query:
            continue
        if query.lower() in {"exit", "quit", "q"}:
            print("Session ended.")
            break

        print("\nAgent: ", end="", flush=True)
        response = run_query(orchestrator, query, user_id)
        print(response)


def single_shot_mode(query: str, user_id: str) -> None:
    orchestrator = build_orchestrator()
    response = run_query(orchestrator, query, user_id)
    print(response)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Medical Multi-Agent Application"
    )
    parser.add_argument("--query", "-q", type=str, default=None,
                        help="Run a single query and exit")
    parser.add_argument("--user-id", type=str, default=None,
                        help="Opaque user identifier for audit logging")
    args = parser.parse_args()

    user_id = args.user_id or f"anon-{uuid.uuid4().hex[:8]}"

    if args.query:
        single_shot_mode(args.query, user_id)
    else:
        interactive_mode(user_id)


if __name__ == "__main__":
    main()
