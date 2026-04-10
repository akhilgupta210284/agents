"""
Generation evaluation using RAGAS LLM-based metrics.

Metrics computed (requires AWS Bedrock credentials)
----------------------------------------------------
  Faithfulness
      Are the claims in the generated answer supported by the retrieved
      context?  Critical for a medical RAG system — hallucinations here
      can be clinically dangerous.  Score range: [0, 1].

  ResponseRelevancy
      Does the generated answer actually address the user's question?
      Uses the embedding model to measure semantic similarity between
      the question and the answer.  Score range: [0, 1].

  RougeScore  (ROUGE-L)
      Lexical overlap between the generated answer and the reference
      answer.  Does not require an LLM.  Score range: [0, 1].

How generation works
--------------------
For each golden question the QA sub-agent is called directly (not through
the orchestrator) to get a deterministic, citation-grounded answer.  The
retrieved contexts are captured from the same retrieval step used in
retrieval_eval.py so both evaluations share identical retrieval behaviour.

RAGAS LLM / embeddings configuration
--------------------------------------
RAGAS uses AWS Bedrock via the LangChain adapter.  The same model IDs
from config/settings.py are re-used so the evaluation mirrors production.

Run only when AWS credentials are available:
    python -m evals.run_evals --mode generation
    python -m evals.run_evals --mode all
"""
from __future__ import annotations

import logging
from unittest.mock import patch

from evals.golden_dataset import SAMPLES
from evals.os_client import EVAL_INDEX_MAP
from evals.retrieval_eval import _fake_embed, _retrieve

_log = logging.getLogger("medical-agent.eval.generation")

# ── RAGAS imports ─────────────────────────────────────────────────────────────
try:
    from ragas.dataset_schema import EvaluationDataset, SingleTurnSample
except ImportError:
    from ragas import EvaluationDataset, SingleTurnSample  # type: ignore[no-redef]

from ragas import evaluate
from ragas.metrics import Faithfulness, ResponseRelevancy, RougeScore
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper


def _build_ragas_llm():
    """Wrap AWS Bedrock Claude as the RAGAS evaluator LLM."""
    from langchain_aws import ChatBedrock
    from config.settings import AWS_REGION, BEDROCK_MODEL_ID

    chat = ChatBedrock(
        model_id=BEDROCK_MODEL_ID,
        region_name=AWS_REGION,
        model_kwargs={"temperature": 0.0, "max_tokens": 2048},
    )
    return LangchainLLMWrapper(chat)


def _build_ragas_embeddings():
    """Wrap AWS Bedrock Titan embeddings for RAGAS ResponseRelevancy."""
    from langchain_aws import BedrockEmbeddings
    from config.settings import AWS_REGION, BEDROCK_EMBED_MODEL_ID

    embeddings = BedrockEmbeddings(
        model_id=BEDROCK_EMBED_MODEL_ID,
        region_name=AWS_REGION,
    )
    return LangchainEmbeddingsWrapper(embeddings)


def _generate_answer(domain: str, question: str) -> str:
    """
    Call the QA sub-agent directly and return its answer as a string.

    The agent's search tools are patched to use eval indices so no
    production data is touched.
    """
    from agents.qa_agent import build_qa_agent
    from tools import search_tools as _st
    from config import settings as _cfg

    with (
        patch.object(_cfg, "OPENSEARCH_INDICES", EVAL_INDEX_MAP),
        patch.object(_st, "_embed_query", _fake_embed),
    ):
        agent = build_qa_agent()
        response = agent(question)
    return str(response)


def build_ragas_samples(top_k: int = 5) -> list[SingleTurnSample]:
    """
    For every golden sample: retrieve → generate → build SingleTurnSample.
    """
    ragas_samples: list[SingleTurnSample] = []
    for i, sample in enumerate(SAMPLES):
        _log.info(
            "[%d/%d] Generating answer for domain=%s question=%r…",
            i + 1, len(SAMPLES), sample["domain"], sample["question"][:60],
        )
        retrieved = _retrieve(sample["domain"], sample["question"], top_k=top_k)
        answer = _generate_answer(sample["domain"], sample["question"])

        _log.debug("Answer (%d chars): %s…", len(answer), answer[:120])

        ragas_samples.append(
            SingleTurnSample(
                user_input=sample["question"],
                response=answer,
                retrieved_contexts=retrieved if retrieved else [""],
                reference=sample["reference"],
                reference_contexts=sample["reference_contexts"],
            )
        )
    return ragas_samples


def run_generation_eval(top_k: int = 5) -> dict:
    """
    Execute generation evaluation for all 12 golden samples.

    Returns a dict with:
      scores     — {"faithfulness": float, "response_relevancy": float,
                    "rouge_score": float}
      per_sample — list of per-question breakdowns
    """
    ragas_llm = _build_ragas_llm()
    ragas_emb = _build_ragas_embeddings()

    metrics = [
        Faithfulness(llm=ragas_llm),
        ResponseRelevancy(llm=ragas_llm, embeddings=ragas_emb),
        RougeScore(),               # ROUGE-L vs reference — no LLM needed
    ]

    _log.info("Building generation samples (top_k=%d)…", top_k)
    ragas_samples = build_ragas_samples(top_k=top_k)
    dataset = EvaluationDataset(samples=ragas_samples)

    _log.info("Running RAGAS generation metrics on %d samples…", len(ragas_samples))
    result = evaluate(dataset=dataset, metrics=metrics)

    scores_df = result.to_pandas()

    aggregate: dict[str, float] = {}
    _skip = {"user_input", "response", "retrieved_contexts",
             "reference", "reference_contexts"}
    for col in scores_df.columns:
        if col not in _skip:
            aggregate[col] = float(scores_df[col].mean())

    per_sample = []
    for i, row in scores_df.iterrows():
        per_sample.append(
            {
                "sample_index": int(i),
                "domain": SAMPLES[i]["domain"],
                "question": SAMPLES[i]["question"],
                "answer_snippet": str(row.get("response", ""))[:200],
                **{col: float(row[col]) for col in scores_df.columns if col not in _skip},
            }
        )

    _log.info("Generation scores: %s", aggregate)
    return {"scores": aggregate, "per_sample": per_sample}
