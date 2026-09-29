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
