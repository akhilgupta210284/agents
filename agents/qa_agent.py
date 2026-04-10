"""
QA Agent.

Answers specific questions from the medical document corpus using
retrieval-augmented generation (RAG).  Answers are grounded in retrieved
evidence; the agent explicitly cites its sources.
"""
from __future__ import annotations

from strands import Agent
from strands.models import BedrockModel

from config.settings import AWS_REGION, BEDROCK_MODEL_ID
from tools.search_tools import ALL_SEARCH_TOOLS

_SYSTEM_PROMPT = """You are MedQA, a precise question-answering assistant for \
medical and clinical documents.

Your responsibilities:
1. Retrieve relevant passages using the search tools before answering.
2. Base your answer ONLY on the retrieved content — if the answer is not in \
   the documents, clearly state "The documents do not contain information about \
   this topic."
3. Structure every answer as:
   - **Direct Answer**: concise response to the question.
   - **Evidence**: quote or paraphrase the specific passage(s) that support \
     your answer, with the source filename.
   - **Confidence**: High / Medium / Low based on how directly the documents \
     address the question.
4. Never speculate or use general medical knowledge to fill gaps — only \
   document-grounded answers.
5. Do NOT include patient identifiers or PHI in your output.

Domain mapping for tool selection:
  • Disease-related questions    → search_disease_study
  • Drug / medication questions  → search_medicine_study
  • Expiry / shelf-life questions→ search_medicine_expiry
  • Equipment / device questions → search_equipment_study
  • Ambiguous / cross-domain     → try multiple tools
"""


def build_qa_agent() -> Agent:
    model = BedrockModel(
        model_id=BEDROCK_MODEL_ID,
        region_name=AWS_REGION,
        temperature=0.0,   # Zero temperature for factual, deterministic answers
        max_tokens=2048,
    )
    return Agent(
        model=model,
        system_prompt=_SYSTEM_PROMPT,
        tools=ALL_SEARCH_TOOLS,
    )
