"""
Retrieval evaluation using RAGAS non-LLM metrics.

Metrics computed (no LLM calls — CI-safe)
------------------------------------------
  NonLLMContextPrecisionWithReference
      Of the chunks returned by the retriever, what fraction are
      genuinely relevant to the question (compared against reference_contexts)?
      A score of 1.0 means every returned chunk is relevant.

  NonLLMContextRecall
      What fraction of the reference_contexts were retrieved?
      A score of 1.0 means the retriever found every relevant chunk.

How the retrieval works in eval mode
--------------------------------------
* The four `search_*` Strands tools are called directly (bypassing the agent).
* OPENSEARCH_INDICES is monkey-patched to point at the eval indices so
  production data is never touched.
* _embed_query is monkey-patched with a deterministic fake so no Bedrock call
  is made. BM25 lexical search still works correctly; the KNN branch returns
  noise but RRF still surfaces the BM25 winner.

Returns
-------
  dict with per-metric aggregate scores and per-sample breakdowns.
"""
from __future__ import annotations

import logging
from unittest.mock import patch

from evals.golden_dataset import SAMPLES
from evals.os_client import EVAL_INDEX_MAP
from evals.seed_index import _deterministic_vector

_log = logging.getLogger("medical-agent.eval.retrieval")

# ── RAGAS imports ─────────────────────────────────────────────────────────────
try:
    from ragas.dataset_schema import EvaluationDataset, SingleTurnSample
except ImportError:
    from ragas import EvaluationDataset, SingleTurnSample   # type: ignore[no-redef]

from ragas import evaluate
from ragas.metrics import NonLLMContextPrecisionWithReference, NonLLMContextRecall

# ── Domain → search tool mapping ─────────────────────────────────────────────
_DOMAIN_SEARCH_FN: dict[str, str] = {
    "disease_study":   "search_disease_study",
    "medicine_study":  "search_medicine_study",
    "medicine_expiry": "search_medicine_expiry",
    "equipment_study": "search_equipment_study",
}


def _fake_embed(text: str) -> list[float]:
    """
    Return a deterministic pseudo-random vector without calling Bedrock.

    The vector is seeded from the query text so the same question always
    produces the same vector.  KNN results will be random-ish, but RRF
    still surfaces BM25 hits, which is what we're evaluating.
    """
    return _deterministic_vector(text)


def _retrieve(domain: str, question: str, top_k: int = 5) -> list[str]:
    """
    Call the appropriate domain search tool and return a list of retrieved
    text passages.  OPENSEARCH_INDICES and _embed_query are patched so only
    the eval indices are touched and no Bedrock call is made.
    """
    from tools import search_tools as _st
    from config import settings as _cfg

    # Patch indices to eval versions and embed to deterministic fake
    with (
        patch.object(_cfg, "OPENSEARCH_INDICES", EVAL_INDEX_MAP),
        patch.object(_st, "_embed_query", _fake_embed),
    ):
        raw_result: str = _st._hybrid_search(domain, question, top_k)

    if raw_result in ("No relevant documents found.", f"Unknown domain: {domain}"):
        return []

    # _hybrid_search returns passages joined by "\n\n---\n\n"
    # Strip the "[Source: ...]" header lines so RAGAS compares clean text
    passages = []
    for block in raw_result.split("\n\n---\n\n"):
        lines = block.strip().splitlines()
        # First line is "[Source: filename | chunk N]" — drop it
        text_lines = [l for l in lines if not l.startswith("[Source:")]
        passage = "\n".join(text_lines).strip()
        if passage:
            passages.append(passage)
    return passages


def build_ragas_samples() -> list[SingleTurnSample]:
    """
    For each golden Q&A pair, run retrieval and build a RAGAS SingleTurnSample.
    """
    ragas_samples: list[SingleTurnSample] = []
    for sample in SAMPLES:
        retrieved = _retrieve(sample["domain"], sample["question"])
        _log.debug(
            "[%s] question=%r → %d chunks retrieved",
            sample["domain"], sample["question"][:60], len(retrieved),
        )
        ragas_samples.append(
            SingleTurnSample(
                user_input=sample["question"],
                retrieved_contexts=retrieved if retrieved else [""],
                reference_contexts=sample["reference_contexts"],
                # response / reference not needed for retrieval-only metrics
            )
        )
    return ragas_samples


def run_retrieval_eval(top_k: int = 5) -> dict:
    """
    Execute retrieval evaluation for all 12 golden samples.

    Returns a dict with:
      scores      — {"context_precision": float, "context_recall": float}
      per_sample  — list of per-question breakdowns
    """
    _log.info("Building retrieval samples (top_k=%d)…", top_k)
    ragas_samples = build_ragas_samples()
    dataset = EvaluationDataset(samples=ragas_samples)

    metrics = [
        NonLLMContextPrecisionWithReference(),
        NonLLMContextRecall(),
    ]

    _log.info("Running RAGAS non-LLM retrieval metrics on %d samples…", len(ragas_samples))
    result = evaluate(dataset=dataset, metrics=metrics)

    # result is a ragas EvaluationResult — convert to plain dict
    scores_df = result.to_pandas()

    aggregate: dict[str, float] = {}
    for col in scores_df.columns:
        if col not in ("user_input", "retrieved_contexts", "reference_contexts",
                       "response", "reference"):
            aggregate[col] = float(scores_df[col].mean())

    per_sample = []
    for i, row in scores_df.iterrows():
        per_sample.append(
            {
                "sample_index": int(i),
                "domain": SAMPLES[i]["domain"],
                "question": SAMPLES[i]["question"],
                **{
                    col: float(row[col])
                    for col in scores_df.columns
                    if col not in ("user_input", "retrieved_contexts",
                                   "reference_contexts", "response", "reference")
                },
            }
        )

    _log.info("Retrieval scores: %s", aggregate)
    return {"scores": aggregate, "per_sample": per_sample}
