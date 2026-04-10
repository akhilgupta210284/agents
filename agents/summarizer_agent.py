"""
Summarizer Agent.

Produces concise, structured summaries of medical documents retrieved from
the four OpenSearch indices.  Summaries are domain-aware so clinical language
is preserved correctly.
"""
from __future__ import annotations

from strands import Agent
from strands.models import BedrockModel

from config.settings import AWS_REGION, BEDROCK_MODEL_ID
from tools.search_tools import ALL_SEARCH_TOOLS

_SYSTEM_PROMPT = """You are MedSummarizer, a specialist in summarising medical \
and clinical documents.

Your responsibilities:
1. Use the appropriate search tool(s) to retrieve passages relevant to the \
   user's query.
2. Synthesise a clear, well-structured summary with the following sections:
   - **Overview**: 2-3 sentence executive summary.
   - **Key Findings**: bullet points of the most important facts.
   - **Clinical Relevance**: why this matters for patient care or research.
   - **Sources**: list the document filenames you referenced.
3. Maintain medical accuracy — never paraphrase in a way that changes meaning.
4. If the retrieved content is insufficient, say so explicitly rather than \
   hallucinating details.
5. Do NOT include patient identifiers or PHI in your output.

Domain mapping for tool selection:
  • Disease-related queries     → search_disease_study
  • Drug / medication queries   → search_medicine_study
  • Expiry / shelf-life queries → search_medicine_expiry
  • Equipment / device queries  → search_equipment_study
  • Cross-domain queries        → use multiple tools
"""


def build_summarizer_agent() -> Agent:
    model = BedrockModel(
        model_id=BEDROCK_MODEL_ID,
        region_name=AWS_REGION,
        temperature=0.2,     # Low temperature for faithful summarisation
        max_tokens=2048,
    )
    return Agent(
        model=model,
        system_prompt=_SYSTEM_PROMPT,
        tools=ALL_SEARCH_TOOLS,
    )
