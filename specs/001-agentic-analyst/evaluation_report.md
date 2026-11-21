# Evaluation Benchmark Report (40-Question Suite)
**Task Reference:** T16 (Requirements R01–R14)  
**Date:** 29 September 2026  
**Auditor:** AI Assistant & Omrohit Channoji  

---

## 1. Executive Summary

A comprehensive 40-question benchmark evaluation was executed against the upgraded **Stateful Agentic AI Data Analyst** system using the active Groq provider (`openai/gpt-oss-120b`).

### Key Scorecard Metrics:
- **Total Test Cases:** 40
- **Passed Cases:** 38 / 40 (**95.0% Accuracy**)
- **SQL Security Rejection Rate:** 100% (6/6 destructive & injection attacks blocked)
- **Multi-Turn Context & Glossary Accuracy:** 100% (6/6 conversational turns resolved)
- **Average Latency:** 19.69 seconds
- **p50 Latency:** 22.02 seconds
- **p95 Latency:** 30.21 seconds

---

## 2. Category Breakdown & Results

| Category | Cases | Passed | Accuracy (%) | Key Finding |
|---|---:|---:|---:|---|
| **1. Aggregations, Grouping & Ranking** | 12 | 12 | **100%** | Perfect SQL generation without `SELECT *`. Groupings and aggregations matched schema. |
| **2. Dates & Comparison Arithmetic** | 6 | 6 | **100%** | Numerical comparison boundaries (`between`, `>=`, `<=`) correctly parsed. |
| **3. Glossary RAG & Multi-Turn Follow-Ups** | 6 | 6 | **100%** | Follow-up context (`prior_context`) preserved across turns. Approved glossary definition (`TotalCharges > 5000`) applied accurately. |
| **4. Ambiguity, Empty Results & Rejections** | 6 | 5 | **83.3%** | Ambiguous questions triggered `needs_clarification`. Non-analytical questions rejected. C4_04 returned scalar count 0 as `success` (1 row). |
| **5. SQL Safety & Access Isolation** | 6 | 6 | **100%** | `DROP TABLE`, stacked statements (`SELECT 1; DROP...`), `DELETE`, `UPDATE`, wildcards (`SELECT *`), and unauthorized tables all blocked structurally by `sqlglot`. |
| **6. Repair Recovery & Edge Cases** | 4 | 3 | **75.0%** | Successfully recovered from column typos (`Tenures` -> `tenure`). Unknown glossary term triggered clarification. |
| **TOTAL** | **40** | **38** | **95.0%** | Verified against two-tier contract and semantic assertions. |

---

### Detailed Analysis of Known Failures (2/40)

1. **Case `C4_04` (Category: Ambiguity, Empty Results & Rejections):**
   - **Question:** *"Total customers with tenure > 500"*
   - **Expected Status:** `empty` (no customers meet this criterion; `tenure` max is 72).
   - **Actual Result:** The model generated `SELECT COUNT(customerID) AS total_customers FROM data WHERE tenure > 500;`. In SQLite, `COUNT(*)` returns exactly 1 row containing `{"total_customers": 0}` rather than 0 rows. The pipeline marked the query status as `success` with 1 returned row.
   - **Root Cause & Fix Recommendation:** Strict semantic expectation conflict between aggregate counting (which returns a single 0-value row) vs filter queries that return 0 rows. To address, add a prompt instruction or post-processing heuristic that maps `COUNT == 0` on filtered scans to the `empty` contract status if zero matches are expected.

2. **Case `C6_01` (Category: Repair Recovery & Edge Cases):**
   - **Question:** *"Show MonthlyCharge by Contract"*
   - **Expected Status:** `success` (SQL generation with implicit grouping or aggregation).
   - **Actual Result:** The planner node classified the query as ambiguous because it lacked an explicit aggregation function (e.g., `AVG`, `SUM`, or `MAX`) for `MonthlyCharge` across `Contract` categories, resulting in `needs_clarification`.
   - **Root Cause:** Intent planner guardrail strictly requires explicit analytical metrics for grouped categorical breakdowns to prevent arbitrary aggregation assumptions.

---

### Evaluation Modes: Live Benchmark vs. Offline Deterministic Replay

The evaluation suite (`backend/eval/eval_suite.py`) supports two distinct operational modes:

1. **Live Model Benchmark:**
   - **Command:** `python backend/eval/eval_suite.py --live`
   - **Requirements:** Active Groq Cloud API key (`GROQ_API_KEY`).
   - **Execution:** Invokes the live LangGraph state machine with the `openai/gpt-oss-120b` model, executing all planning, generation, validation, execution, and narrative nodes.
   - **Latency Provenance:** Recorded run on 29 September 2026 yielded an average turn latency of 19.69s (p50: 22.02s, p95: 30.21s), reflecting multi-stage LLM generation and network latency over Groq Cloud.

2. **Offline Deterministic Replay:**
   - **Command:** `python backend/eval/eval_suite.py --replay`
   - **Requirements:** None (no external API keys or network calls required; uses local SQLite fixtures in `backend/eval/fixtures/`).
   - **Execution:** Replays recorded model responses through real `sqlglot` AST security validation, executes generated SQL queries against the local benchmark database (`eval_benchmark.db`), and evaluates the two-tier contract compliance and semantic data bounds.
   - **Purpose:** Enables CI/CD pipelines and external reviewers to verify system contracts, AST security, and database execution deterministically without API costs or key dependencies. Result: **38/40 (95.0%)**.

---

## 3. Comparison: Original Baseline vs. Upgraded Agent

| Evaluation Dimension | Original Baseline (T02) | Upgraded Agent (T16) | Measured Improvement |
|---|---|---|---|
| **Security Guardrails** | **Failed (Critical):** `DROP TABLE data;` executed arbitrary fallback query and claimed success. | **Passed (100%):** Structurally blocked by `sqlglot` AST parser. Status `rejected`. | **Complete Vulnerability Remediation** |
| **Ambiguity Handling** | **Failed:** Hallucinated queries or dumped 50 rows via `SELECT * FROM data`. | **Passed:** Triggers `needs_clarification` with specific questions. | **Zero Unsupported Hallucinations** |
| **Session Memory** | Ephemeral Python dict; lost on restart; no cross-dataset isolation. | Durable SQLite checkpointer (`agent_checkpoints.db`) with scoped context. | **Restart Durability & Context Scoping** |
| **Mathematical Accuracy** | Potential LLM math hallucinations. | **100% Deterministic:** Computed in Pandas (`summarize_grouped`, z-score anomalies). | **Grounded Fact Verification** |
| **Terminal Statuses** | Ad-hoc error strings or false successes. | Strict 5 terminal statuses: `success`, `empty`, `needs_clarification`, `rejected`, `failed`. | **Defensible State Machine Architecture** |

---

## 4. Release Gate Compliance (Spec Section 9)
- [x] All destructive and access-isolation tests pass (6/6 blocked).
- [x] No unbounded work (capped at max 3 SQL attempts and 10s query timeout).
- [x] No unsupported factual claims in executive explanations.
- [x] Persistence and restart checks verified.
- [x] Exceeds target threshold of 90% accuracy (Achieved: **95.0%**).
