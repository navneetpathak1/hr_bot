"""
"contextual_precision",
"contextual_recall",
"answer_relevancy",
"faithfulness",
"hallucination"
"""

import os

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")

import sys
import json
import argparse
import time
import warnings
from pathlib import Path
from typing import List

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import pytest
from deepeval import evaluate
from deepeval.metrics import (
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    HallucinationMetric,
)
from deepeval.test_case import LLMTestCase

from EVALS.groq_deepeval_model import GroqDeepEvalModel

from langchain_core.messages import HumanMessage
from app.graph.workflow import rag_app


TEST_DATA_PATH = Path("test_data/hr_test_cases.json")
RESULTS_PATH = Path("EVALS/eval_results.json")
THRESHOLD = 0.3        
EVAL_USER_ID = 9999     


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_test_cases(
    limit: int | None = None,
    topic: str | None = None,
) -> list[dict]:
    """Load test cases from JSON, raising clearly if the file is missing."""
    if not TEST_DATA_PATH.exists():
        raise FileNotFoundError(
            f"[ERROR] Test data file not found: {TEST_DATA_PATH}\n"
            f"Please create '{TEST_DATA_PATH}' with your HR test cases before running evals."
        )

    with open(TEST_DATA_PATH, encoding="utf-8") as f:
        cases = json.load(f)

    if topic:
        cases = [c for c in cases if c.get("topic", "").lower() == topic.lower()]
    if limit:
        cases = cases[:limit]

    return cases


def invoke_rag(question: str, user_id: int = EVAL_USER_ID) -> dict:
    """
    Call the RAG pipeline and return a dict with:
      actual_output    LLM-generated answer
      retrieval_context  list of retrieved chunk strings
      context          raw context string passed to the LLM
    """
    thread_id = f"user_{user_id}"
    config = {"configurable": {"thread_id": thread_id}}
    initial_input = {
        "question": question,
        "messages": [HumanMessage(content=question)],
        "retry_count": 0,
        "error": None,
    }

    result = rag_app.invoke(initial_input, config=config)

    # Retrieved document chunks as a list of strings
    retrieved_docs = result.get("retrieved_documents", [])
    retrieval_context = [
        doc.page_content for doc in retrieved_docs
        if hasattr(doc, "page_content") and doc.page_content.strip()
    ]

    return {
        "actual_output": result.get("answer", ""),
        "retrieval_context": retrieval_context,
        "context": result.get("context", ""),
    }


def build_deepeval_test_case(
    raw: dict,
    rag_output: dict,
) -> LLMTestCase:
    """
    Combine a raw test case + RAG pipeline output into a DeepEval LLMTestCase.

    DeepEval field mapping:
      input             → employee question
      actual_output     → LLM-generated answer from the pipeline
      expected_output   → reference / ground-truth answer
      retrieval_context → chunks the retriever actually returned
                          (used by contextual metrics)
      context           → ground-truth relevant chunks from test dataset
    """
    return LLMTestCase(
        input=raw["input"],
        actual_output=rag_output["actual_output"],
        expected_output=raw["expected_output"],
        # What the retriever actually returned
        retrieval_context=rag_output["retrieval_context"] or raw["retrieval_context"],
        # Ground-truth context used as reference for hallucination checks
        context=raw["retrieval_context"],
    )

# Metric factory

def build_metrics(model: GroqDeepEvalModel) -> dict:
    """Create all five evaluation metrics with the Groq judge."""
    return {
        "contextual_precision": ContextualPrecisionMetric(
            threshold=THRESHOLD,
            model=model,
            include_reason=True,
        ),
        "contextual_recall": ContextualRecallMetric(
            threshold=THRESHOLD,
            model=model,
            include_reason=True,
        ),
        "answer_relevancy": AnswerRelevancyMetric(
            threshold=THRESHOLD,
            model=model,
            include_reason=True,
        ),
        "faithfulness": FaithfulnessMetric(
            threshold=THRESHOLD,
            model=model,
            include_reason=True,
        ),
        "hallucination": HallucinationMetric(
            threshold=THRESHOLD,
            model=model,
            include_reason=True,
        ),
    }


def run_evals(
    limit: int | None = None,
    topic: str | None = None,
    sleep_between: float = 10.0,
) -> List[dict]:
    """
    Run the full evaluation pipeline and return per-case results.

    Args:
        limit           : number of test cases to run (None = all)
        topic           : optional topic filter
        sleep_between   : seconds to sleep between cases (avoid rate limits)

    Returns:
        List of result dicts with scores and pass/fail per metric.
    """
    # Load test data
    raw_cases = load_test_cases(limit=limit, topic=topic)
    print(f"\n[INFO] Loaded {len(raw_cases)} test case(s).\n")

    # Groq judge model
    groq_model = GroqDeepEvalModel()
    metrics = build_metrics(groq_model)

    all_results = []

    for idx, raw in enumerate(raw_cases, start=1):
        question = raw["input"]
        truncated = question[:80] + ("..." if len(question) > 80 else "")
        print(f"[{idx}/{len(raw_cases)}] Question: {truncated}")

        # ── Step 1: Invoke RAG pipeline ──────────────────────────────────────
        try:
            rag_out = invoke_rag(question, user_id=EVAL_USER_ID + idx)
        except Exception as exc:
            print(f"  [FAIL] RAG invocation failed: {exc}")
            all_results.append({
                "id": raw.get("id", idx),
                "input": question,
                "topic": raw.get("topic"),
                "error": str(exc),
            })
            continue

        print(f"  [OK] RAG answered. Retrieved {len(rag_out['retrieval_context'])} chunks.")

        # ── Step 2: Build DeepEval test case ─────────────────────────────────
        test_case = build_deepeval_test_case(raw, rag_out)

        # ── Step 3: Score each metric ─────────────────────────────────────────
        case_result = {
            "id": raw.get("id", idx),
            "input": question,
            "topic": raw.get("topic"),
            "source": raw.get("source"),
            "actual_output": rag_out["actual_output"],
            "scores": {},
        }

        for metric_name, metric in metrics.items():
            try:
                metric.measure(test_case)
                score = metric.score
                passed = getattr(metric, "success", None)
                if passed is None:
                    passed = score >= THRESHOLD
                reason = getattr(metric, "reason", None) or ""
                print(f"  [SCORE] {metric_name:25s}: {score:.3f}  {'PASS' if passed else 'FAIL'}  {reason[:80]}")
                case_result["scores"][metric_name] = {
                    "score": score,
                    "passed": passed,
                    "reason": reason,
                }
                # Polite sleep to avoid Groq rate limits between metric calls
                time.sleep(sleep_between)

            except Exception as exc:
                err_msg = str(exc)
                is_rate_limit = "429" in err_msg or "rate_limit" in err_msg.lower()
                label = "rate limit" if is_rate_limit else "error"
                print(f"  [WARN] {metric_name:25s}: {label} - {err_msg[:100]}")
                case_result["scores"][metric_name] = {
                    "score": None,
                    "passed": False,
                    "reason": err_msg,
                }

        all_results.append(case_result)
        print()

        # Sleep between test cases
        if idx < len(raw_cases):
            time.sleep(sleep_between * 2)

    return all_results


def save_results(results: List[dict]) -> None:
    """Save evaluation results to EVALS/eval_results.json."""
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Results saved -> {RESULTS_PATH}")


def print_summary(results: List[dict]) -> None:
    """Print a human-readable summary table."""
    metric_names = [
        "contextual_precision",
        "contextual_recall",
        "answer_relevancy",
        "faithfulness",
        "hallucination",
    ]

    print("\n" + "=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)

    totals = {m: [] for m in metric_names}
    for r in results:
        for m in metric_names:
            sc = r.get("scores", {}).get(m, {}).get("score")
            if sc is not None:
                totals[m].append(sc)

    print(f"\n{'Metric':<28} {'Avg Score':>10}  {'Min':>6}  {'Max':>6}  {'Pass Rate':>10}")
    print("-" * 70)
    for m in metric_names:
        scores = totals[m]
        if scores:
            avg = sum(scores) / len(scores)
            mn = min(scores)
            mx = max(scores)
            passed = sum(1 for s in scores if s >= THRESHOLD)
            rate = f"{passed}/{len(scores)} ({100*passed//len(scores)}%)"
        else:
            avg = mn = mx = 0.0
            rate = "N/A"
        print(f"  {m:<26} {avg:>10.3f}  {mn:>6.3f}  {mx:>6.3f}  {rate:>10}")

    errors = sum(1 for r in results if "error" in r)
    print(f"\n  Cases run: {len(results)}   Errors: {errors}")
    print("=" * 70 + "\n")


# pytest integration  (run via: deepeval test run EVALS/eval_rag.py)

def _load_cases_for_pytest(limit=5):
    """Return test cases for the pytest-based deepeval test runner."""
    raw_cases = load_test_cases(limit=limit)
    groq_model = GroqDeepEvalModel()
    metrics_map = build_metrics(groq_model)
    result_pairs = []
    for raw in raw_cases:
        try:
            rag_out = invoke_rag(raw["input"], user_id=EVAL_USER_ID + raw.get("id", 0))
        except Exception:
            rag_out = {
                "actual_output": "RAG pipeline error",
                "retrieval_context": raw["retrieval_context"],
                "context": "",
            }
        tc = build_deepeval_test_case(raw, rag_out)
        result_pairs.append((tc, list(metrics_map.values())))
    return result_pairs


# Generate pairs once at module level so pytest can discover them
_pytest_pairs: list | None = None


def _get_pytest_pairs():
    global _pytest_pairs
    if _pytest_pairs is None:
        _pytest_pairs = _load_cases_for_pytest(limit=5)
    return _pytest_pairs

_IS_PYTEST = (
    "pytest" in sys.modules
    or os.getenv("PYTEST_CURRENT_TEST") is not None
    or any("pytest" in arg for arg in sys.argv)
    or any("deepeval" in arg for arg in sys.argv)
)


@pytest.mark.parametrize("test_case,metrics", _get_pytest_pairs() if _IS_PYTEST else [])
def test_hr_rag_pipeline(test_case: LLMTestCase, metrics: list):
    """
    Parametrised pytest test — each test case is scored against all 5 metrics.
    Run with: deepeval test run EVALS/eval_rag.py
    """
    evaluate([test_case], metrics)


def main():
    parser = argparse.ArgumentParser(
        description="Run DeepEval RAG evaluations for the HR-RAG project."
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Maximum number of test cases to evaluate (default: all).",
    )
    parser.add_argument(
        "--topic", type=str, default=None,
        help="Only evaluate test cases matching this topic (e.g. 'Leave Policy').",
    )
    parser.add_argument(
        "--sleep", type=float, default=3.0,
        help="Seconds to sleep between metric calls (default: 3).",
    )
    parser.add_argument(
        "--no-rag", action="store_true",
        help=(
            "Skip live RAG invocation; use the ground-truth retrieval context "
            "and a stub answer. Useful for testing the eval pipeline itself."
        ),
    )
    args = parser.parse_args()

    if args.no_rag:
        # Quick smoke-test mode: bypass the RAG pipeline
        print("[INFO] --no-rag mode: using ground-truth context as stub output.\n")
        raw_cases = load_test_cases(limit=args.limit, topic=args.topic)
        groq_model = GroqDeepEvalModel()
        metrics_map = build_metrics(groq_model)
        test_cases = []
        for raw in raw_cases:
            stub_output = raw["expected_output"]  # use reference as stub
            tc = LLMTestCase(
                input=raw["input"],
                actual_output=stub_output,
                expected_output=raw["expected_output"],
                retrieval_context=raw["retrieval_context"],
                context=raw["retrieval_context"],
            )
            test_cases.append(tc)
        evaluate(test_cases, list(metrics_map.values()))
        return

    results = run_evals(limit=args.limit, topic=args.topic, sleep_between=args.sleep)
    save_results(results)
    print_summary(results)


if __name__ == "__main__":
    main()

# uv run python -m EVALS.eval_rag --limit 2 --sleep 15
