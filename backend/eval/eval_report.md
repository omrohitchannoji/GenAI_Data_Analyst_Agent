# Evaluation Benchmark Report (40-Question Suite)
**Provenance:** Recorded 29 September 2026 using `openai/gpt-oss-120b` via Groq Cloud  
**Scorecard:** 38 / 40 Passed (**95.0%**)  
**Offline Replay Status:** 38 / 40 Passed (**95.0%**) via `backend/eval/eval_suite.py --replay`

---

## 1. Scorecard Summary

| Category | Cases | Passed | Accuracy (%) | Key Finding |
|---|---:|---:|---:|---|
| **1. Aggregations, Grouping & Ranking** | 12 | 12 | **100%** | Valid SQL generation without `SELECT *`. Groupings and aggregations matched schema. |
| **2. Dates & Comparison Arithmetic** | 6 | 6 | **100%** | Numerical comparison boundaries (`between`, `>=`, `<=`) correctly parsed. |
| **3. Glossary RAG & Multi-Turn Follow-Ups** | 6 | 6 | **100%** | Follow-up context (`prior_context`) preserved across turns. Approved glossary definitions applied accurately. |
| **4. Ambiguity, Empty Results & Rejections** | 6 | 5 | **83.3%** | Ambiguous questions triggered `needs_clarification`. Non-analytical questions rejected. |
| **5. SQL Safety & Access Isolation** | 6 | 6 | **100%** | `DROP TABLE`, stacked statements, `DELETE`, `UPDATE`, wildcards, and unauthorized tables blocked by AST. |
| **6. Repair Recovery & Edge Cases** | 4 | 3 | **75.0%** | Successfully recovered from schema column misalignments; bounded to 2 retries. |
| **TOTAL** | **40** | **38** | **95.0%** | Verified against two-tier contract compliance and semantic data bounds. |

---

## 2. Detailed Root-Cause Analysis of the 2 Failures

1. **Case `C4_04` (Category: Ambiguity, Empty Results & Rejections):**
   - **Question:** *"Total customers with tenure > 500"*
   - **Expected Status:** `empty` (0 rows expected since max tenure in data is 72).
   - **Actual Result:** Model generated `SELECT COUNT(customerID) AS total_customers FROM data WHERE tenure > 500;`. In SQLite, `COUNT(*)` returns exactly 1 row containing `{"total_customers": 0}`. The system marked the query as `success` with 1 row returned instead of `empty`.
   - **Remediation Recommendation:** Introduce a post-execution normalization rule: if an analytical query returns a single scalar row where all aggregated count columns equal `0`, evaluate whether the semantic contract required `empty`.

2. **Case `C6_01` (Category: Repair Recovery & Edge Cases):**
   - **Question:** *"Show MonthlyCharge by Contract"*
   - **Expected Status:** `success` (SQL generation with grouping).
   - **Actual Result:** The intent planner classified the request as ambiguous because no aggregation function (`AVG`, `SUM`, `MIN`, `MAX`) was specified for `MonthlyCharge` across the `Contract` categorical dimension. It transitioned to `needs_clarification`.
   - **Remediation Recommendation:** Provide a default grouping behavior (e.g., default to `AVG` when a numeric metric is grouped by a categorical attribute) if clarification is not desired.

---

## 3. Evaluation Modes & Reproduction Commands

### Offline Deterministic Replay (Zero API Keys Required)
Exercises the full AST security validation, SQLite query execution against `fixtures/eval_benchmark.db`, and two-tier assertion verification without model calls:
```bash
python backend/eval/eval_suite.py --replay
```
Or via pytest:
```bash
pytest backend/tests/test_offline_eval_replay.py -v
```

### Live Model Benchmark (Requires Groq API Key)
Executes end-to-end turns against the live Groq LLM API (`openai/gpt-oss-120b`):
```bash
python backend/eval/eval_suite.py --live
```
*Note: Measured latency during the live benchmark (average 19.69s, p50 22.02s, p95 30.21s) reflects network roundtrips to Groq Cloud across multi-node LangGraph execution.*
