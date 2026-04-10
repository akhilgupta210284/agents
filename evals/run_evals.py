"""
RAGAS evaluation entry point.

Usage
-----
# Retrieval only (CI-safe — no AWS credentials required):
    python -m evals.run_evals --mode retrieval

# Generation only (requires AWS Bedrock credentials):
    python -m evals.run_evals --mode generation

# Full pipeline — retrieval + generation:
    python -m evals.run_evals --mode all

# Keep eval indices after the run (default: teardown on exit):
    python -m evals.run_evals --mode retrieval --keep-indices

Output
------
Writes a JSON report to --output (default: eval-report.json).

Exit codes
----------
  0  All metric scores meet or exceed their configured thresholds.
  1  One or more metrics fell below threshold — CI pipeline fails.
  2  Unexpected runtime error.

Thresholds
----------
These are intentionally conservative for a medical RAG system where
hallucinations or retrieval gaps have patient-safety implications.

  Retrieval:
    context_precision  >= 0.50   (≥50 % of returned chunks are relevant)
    context_recall     >= 0.40   (retrieve ≥40 % of reference contexts)

  Generation (LLM-based, optional):
    faithfulness       >= 0.70   (answers strongly grounded in retrieved context)
    response_relevancy >= 0.60   (answers address the question asked)
    rouge_score        >= 0.15   (basic lexical overlap with reference answer)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
_log = logging.getLogger("medical-agent.eval")

# ── Thresholds ────────────────────────────────────────────────────────────────
THRESHOLDS: dict[str, float] = {
    # Retrieval (non-LLM) ─────────────────────────────────────────────────────
    "non_llm_context_precision_with_reference": 0.50,
    "non_llm_context_recall":                   0.40,
    # Generation (LLM) ────────────────────────────────────────────────────────
    "faithfulness":        0.70,
    "response_relevancy":  0.60,
    "rouge_score":         0.15,
}


def _check_thresholds(scores: dict[str, float]) -> list[str]:
    """
    Compare achieved scores against THRESHOLDS.

    Returns a list of failure messages (empty = all pass).
    """
    failures: list[str] = []
    for metric, achieved in scores.items():
        threshold = THRESHOLDS.get(metric)
        if threshold is None:
            continue
        if achieved < threshold:
            failures.append(
                f"FAIL  {metric}: {achieved:.4f} < threshold {threshold:.4f}"
            )
        else:
            _log.info("PASS  %s: %.4f >= threshold %.4f", metric, achieved, threshold)
    return failures


def _run(args: argparse.Namespace) -> int:
    from evals.seed_index import setup_eval_indices, teardown_eval_indices
    from evals.os_client import get_eval_client

    client = get_eval_client()

    # ── Seed eval indices ────────────────────────────────────────────────────
    _log.info("Setting up eval indices…")
    setup_eval_indices(client)

    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "retrieval": None,
        "generation": None,
        "all_scores": {},
        "failures": [],
        "passed": False,
    }

    all_scores: dict[str, float] = {}

    try:
        # ── Retrieval evaluation ─────────────────────────────────────────────
        if args.mode in ("retrieval", "all"):
            _log.info("── Retrieval evaluation ──────────────────────────────────")
            from evals.retrieval_eval import run_retrieval_eval
            ret_result = run_retrieval_eval(top_k=args.top_k)
            report["retrieval"] = ret_result
            all_scores.update(ret_result["scores"])

        # ── Generation evaluation ────────────────────────────────────────────
        if args.mode in ("generation", "all"):
            _log.info("── Generation evaluation ─────────────────────────────────")
            from evals.generation_eval import run_generation_eval
            gen_result = run_generation_eval(top_k=args.top_k)
            report["generation"] = gen_result
            all_scores.update(gen_result["scores"])

    finally:
        if not args.keep_indices:
            _log.info("Tearing down eval indices…")
            teardown_eval_indices(client)

    # ── Threshold checks ─────────────────────────────────────────────────────
    failures = _check_thresholds(all_scores)
    report["all_scores"] = all_scores
    report["failures"] = failures
    report["passed"] = len(failures) == 0

    # ── Write JSON report ─────────────────────────────────────────────────────
    output_path = Path(args.output)
    output_path.write_text(json.dumps(report, indent=2))
    _log.info("Evaluation report written to %s", output_path)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  RAGAS Evaluation — mode: {args.mode.upper()}")
    print("=" * 60)
    for metric, score in all_scores.items():
        threshold = THRESHOLDS.get(metric, float("nan"))
        status = "PASS" if score >= threshold else "FAIL"
        print(f"  [{status}]  {metric:<45} {score:.4f}  (threshold {threshold:.2f})")
    print("=" * 60)

    if failures:
        print(f"\n  {len(failures)} metric(s) below threshold — see {output_path}")
        for msg in failures:
            print(f"  {msg}")
        print()
        return 1

    print(f"\n  All metrics passed.  Report: {output_path}\n")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run RAGAS retrieval and/or generation evaluations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode",
        choices=["retrieval", "generation", "all"],
        default="retrieval",
        help="Which evaluations to run (default: retrieval)",
    )
    parser.add_argument(
        "--top-k", type=int, default=5,
        help="Number of chunks to retrieve per question (default: 5)",
    )
    parser.add_argument(
        "--output", default="eval-report.json",
        help="Path to write the JSON report (default: eval-report.json)",
    )
    parser.add_argument(
        "--keep-indices", action="store_true",
        help="Do not delete eval OpenSearch indices after the run",
    )
    args = parser.parse_args()

    try:
        sys.exit(_run(args))
    except Exception:
        _log.error("Evaluation failed with an unexpected error:\n%s", traceback.format_exc())
        sys.exit(2)


if __name__ == "__main__":
    main()
