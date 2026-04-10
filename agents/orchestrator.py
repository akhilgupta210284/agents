"""
Orchestrator Agent — get_intent.

The entry point for all user queries.  It:
  1. Detects the intent of the user's prompt.
  2. Routes to the appropriate specialist agent via a @tool wrapper.
  3. Returns the specialist's response verbatim.

Routing table:
  summarize / overview / brief     → Summarizer Agent
  question / ask / what / how / why → QA Agent
  generate questions / quiz / test  → Question Generation Agent
"""
from __future__ import annotations

from strands import Agent, tool
from strands.models import BedrockModel

from agents.qa_agent import build_qa_agent
from agents.question_gen_agent import build_question_gen_agent
from agents.summarizer_agent import build_summarizer_agent
from config.settings import AWS_REGION, BEDROCK_MODEL_ID

# ─── Sub-agent tool wrappers ──────────────────────────────────────────────────
# Each sub-agent is instantiated fresh per call so there is no cross-user
# state leakage — important for HIPAA multi-tenant isolation.

@tool
def summarizer(query: str) -> str:
    """
    Delegate to the Summarizer Agent.
    Use this tool when the user asks for a summary, overview, or brief
    of medical documents.

    Args:
        query: The user's full summarisation request.

    Returns:
        Structured document summary with key findings and sources.
    """
    agent = build_summarizer_agent()
    return str(agent(query))


@tool
def qa(query: str) -> str:
    """
    Delegate to the QA Agent.
    Use this tool when the user asks a specific question and wants a precise,
    evidence-backed answer from the medical documents.

    Args:
        query: The user's question.

    Returns:
        Direct answer with supporting evidence and source citations.
    """
    agent = build_qa_agent()
    return str(agent(query))

@tool
def question_generator(query: str) -> str:
    """
    Delegate to the Question Generation Agent.
    Use this tool when the user wants to generate study questions, quiz items,
    or assessment questions from medical reference documents.

    Args:
        query: The user's request, including the topic and any preferences
               for question type or difficulty.

    Returns:
        A set of questions across recall, comprehension, and application levels.
    """
    agent = build_question_gen_agent()
    return str(agent(query))

# ─── Orchestrator system prompt ───────────────────────────────────────────────

_ORCHESTRATOR_PROMPT = """You are MedOrchestrator (get_intent), the intelligent \
routing layer of a medical document intelligence platform.

Your ONLY job is to understand the user's intent and delegate to the correct \
specialist agent tool.  You must NOT answer questions directly.

Routing rules — choose ONE tool per request:
┌──────────────────────────────────────────────────────────────────────┐
│ Intent signals               │ Tool to call                          │
├──────────────────────────────┼───────────────────────────────────────┤
│ summarize, overview, brief,  │ summarizer(query)                     │
│ highlights, key points       │                                       │
├──────────────────────────────┼───────────────────────────────────────┤
│ what is, how does, explain,  │ qa(query)                             │
│ tell me about, answer,       │                                       │
│ find information             │                                       │
├──────────────────────────────┼───────────────────────────────────────┤
│ generate questions, create   │ question_generator(query)             │
│ quiz, test me, make questions│                                       │
└──────────────────────────────┴───────────────────────────────────────┘

Document domains available (pass the full user query to the sub-agent — it \
will pick the right search tool):
  • Disease Study       — diseases, symptoms, clinical trials, epidemiology
  • Medicine Study      — drugs, pharmacology, dosage, interactions
  • Medicine Expiry     — shelf-life, storage conditions, stability
  • Equipment Study     — medical devices, calibration, maintenance

Compliance notes:
  • Never repeat or log PHI/PII from user queries in your own response text.
  • If a query is ambiguous, ask ONE clarifying question before routing.
  • If a query is out of scope (not medical-domain), politely decline.
"""

def build_orchestrator() -> Agent:
    model = BedrockModel(
        model_id=BEDROCK_MODEL_ID,
        region_name=AWS_REGION,
        temperature=0.0,   # Deterministic routing
        max_tokens=4096,
    )
    return Agent(
        model=model,
        system_prompt=_ORCHESTRATOR_PROMPT,
        tools=[summarizer, qa, question_generator],
    )
