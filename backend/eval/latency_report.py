"""Run an explicit live benchmark sample and report node latency/token telemetry.

No provider calls are made unless --live is supplied. The script prints only
aggregate values; it does not persist questions, SQL, database rows, or traces.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import sqlite3
import tempfile
import time
import warnings
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(REPO_DIR / ".env")

from app.agent.graph import run_agent_turn
from app.core.dataset_registry import default_registry
from app.core.telemetry import flush_langfuse
from eval.eval_suite import BENCHMARK_CASES, ensure_evaluation_database

warnings.filterwarnings("ignore", message="Could not infer format")


TRACE_NODE_NAMES = (
    "planner", "generator", "validator", "executor", "repair", "insights", "narrative"
)
EVAL_DATASET_ID = "portfolio_eval_synthetic"


def _load_cases(split: str) -> List[Dict[str, Any]]:
    if split == "development":
        return [{"id": row["id"], "question": row["q"]} for row in BENCHMARK_CASES]
    import json

    with (BACKEND_DIR / "eval" / "held_out_benchmark.json").open(encoding="utf-8") as handle:
        data = json.load(handle)
    return [{"id": row["id"], "question": row["question"]} for row in data["cases"]]


def _percentile(values: List[float], percentile: int):
    return round(float(np.percentile(values, percentile)), 2) if values else None


def _print_value(value, suffix=""):
    return f"{value}{suffix}" if value is not None else "unavailable"


def _failure_category(error: str) -> str:
    message = error.lower()
    if "429" in message or "rate limit" in message or "quota" in message:
        return "provider quota/rate limit"
    if "connection" in message or "timeout" in message or "network" in message:
        return "provider connection failure"
    if "401" in message or "403" in message or "unauthorized" in message or "api key" in message:
        return "provider authentication failure"
    if "schema" in message or "dataset" in message or "sqlite" in message or "database" in message:
        return "dataset/schema failure"
    return "unclassified agent failure"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("development", "held_out"), default="development")
    parser.add_argument("--limit", type=int, help="Run only the first N cases (useful for a low-cost smoke run).")
    parser.add_argument("--live", action="store_true", help="Explicitly allow calls to the configured LLM provider.")
    args = parser.parse_args()

    if not args.live:
        parser.error("No model calls were made. Add --live when you are ready to spend provider quota.")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    if not os.environ.get("GROQ_API_KEY", "").strip():
        parser.error("GROQ_API_KEY is missing. Add it to backend/.env before a live run.")

    cases = _load_cases(args.split)
    if args.limit:
        cases = cases[:args.limit]

    node_latencies: Dict[str, List[float]] = {name: [] for name in TRACE_NODE_NAMES}
    query_token_totals: List[int] = []
    query_costs: List[float] = []
    token_complete_queries = 0
    repair_queries = 0
    failures = 0
    completed_queries = 0
    query_latencies = []

    print(f"Live telemetry run: split={args.split}, cases={len(cases)}, model={os.environ.get('GROQ_MODEL', 'openai/gpt-oss-120b')}")
    print("Dataset: synthetic Telco evaluation fixture only.")
    print("This run may use provider quota. No query text or SQL is written to the report.")
    previous_registry_path = default_registry.db_path
    registry_tmp = tempfile.TemporaryDirectory(prefix="agent_eval_registry_")
    default_registry.db_path = str(Path(registry_tmp.name) / "registry.sqlite3")
    default_registry._init_db()
    fixture_db = ensure_evaluation_database()
    with sqlite3.connect(fixture_db) as conn:
        row_count = int(conn.execute("SELECT COUNT(*) FROM data").fetchone()[0])
    default_registry.register_dataset(
        dataset_id=EVAL_DATASET_ID,
        principal_id="latency_report",
        filename="telco_churn_data.csv",
        table_name="data",
        db_path=fixture_db,
        row_count=row_count,
        column_types={},
    )
    try:
        for index, case in enumerate(cases, 1):
            started = time.perf_counter()
            try:
                result = run_agent_turn(
                    question=case["question"],
                    dataset_id=EVAL_DATASET_ID,
                    session_id=f"latency_{args.split}_{case['id']}_{time.time_ns()}",
                    principal_id="latency_report",
                )
            except Exception as exc:
                failures += 1
                print(f"[{index}/{len(cases)}] {case['id']}: run failed ({type(exc).__name__})")
                continue

            if result.get("terminal_status") == "failed":
                failures += 1
                error = str(result.get("error", ""))
                category = _failure_category(error)
                print(f"[{index}/{len(cases)}] {case['id']}: {category}")
                if category.startswith("provider"):
                    print("Stopping early to avoid repeated provider failures.")
                    break
                continue
            completed_queries += 1
            query_latencies.append((time.perf_counter() - started) * 1000)
            spans = result.get("node_spans", [])
            by_name = {"planner": "analyzer_planner", "generator": "sql_generator", "repair": "repair",
                       "insights": "analytics_insights", "narrative": "narrative_explainer"}
            for report_name, internal_name in by_name.items():
                node_latencies[report_name].extend(
                    float(span["latency_seconds"]) * 1000 for span in spans
                    if span.get("node_name") == internal_name and span.get("latency_seconds") is not None
                )
            node_latencies["validator"].extend(float(s["latency_seconds"]) * 1000 for s in spans
                                                if s.get("node_name") == "validator")
            node_latencies["executor"].extend(float(s["latency_seconds"]) * 1000 for s in spans
                                               if s.get("node_name") == "executor")

            if int(result.get("retry_count", 0) or 0) > 0:
                repair_queries += 1
            llm_spans = [span for span in spans if span.get("model")]
            if llm_spans and all(span.get("total_tokens") is not None for span in llm_spans):
                token_complete_queries += 1
                query_token_totals.append(sum(int(span["total_tokens"]) for span in llm_spans))
            if llm_spans and all(span.get("cost_usd") is not None for span in llm_spans):
                query_costs.append(sum(float(span["cost_usd"]) for span in llm_spans))

            print(f"[{index}/{len(cases)}] {case['id']}: {result.get('terminal_status', 'unknown')}")
    finally:
        flush_langfuse()
        default_registry.db_path = previous_registry_path
        registry_tmp.cleanup()

    print("\nPer-node latency (milliseconds)")
    print(f"{'Node':<14} {'Count':>7} {'p50':>12} {'p95':>12}")
    for name in TRACE_NODE_NAMES:
        values = node_latencies[name]
        print(f"{name:<14} {len(values):>7} {_print_value(_percentile(values, 50)):>12} {_print_value(_percentile(values, 95)):>12}")

    print("\nRun summary")
    print(f"Queries completed: {completed_queries}/{len(cases)} (run errors: {failures})")
    print(f"Repair-loop frequency: {repair_queries}/{completed_queries} ({repair_queries / completed_queries:.1%})" if completed_queries else "Repair-loop frequency: unavailable")
    print(f"Queries with complete provider token usage: {token_complete_queries}/{completed_queries}")
    print(f"Mean tokens/query (complete usage only): {_print_value(round(statistics.mean(query_token_totals), 2) if query_token_totals else None)}")
    print(f"Mean cost/query (known model rate and complete usage only): {_print_value(round(statistics.mean(query_costs), 8) if query_costs else None, ' USD')}")
    if failures:
        print("Note: run errors are excluded from latency and token averages.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
