# Failure Analysis: Text-to-SQL Benchmark

## Run provenance

The original 40-case benchmark recorded a live score of 38/40 under two incorrect or overly permissive expectations. After reviewing the exact SQL and observed behavior, the expectations were corrected. The deterministic offline replay now scores 40/40 by replaying recorded model SQL against local synthetic fixtures. This is a corrected contract replay, not a fresh live-model evaluation and not evidence that the generator is 100% accurate.

The separate 20-question held-out file is `backend/eval/held_out_benchmark.json`. Its 20/20 replay is fixture-driven and checks SQL/contract behavior without calling the model. The repository does not provide independent evidence that this set was hidden from all prompt or rule development, so the score should not be presented as an unbiased generalization result.

## C4_04 — zero-count aggregate contract mismatch

- **Question:** “Total customers with tenure > 500”
- **Original expected status:** `empty`; **corrected expected status:** `success` with one scalar row and `total_customers = 0`.
- **Generated SQL:** `SELECT COUNT(customerID) AS total_customers FROM data WHERE tenure > 500;`
- **Observed result:** `success`, with one row: `{"total_customers": 0}`
- **Why it failed:** The query is valid. An ungrouped SQL `COUNT` returns one row containing zero when no records match. The benchmark expected zero result rows, which is a different behavior from asking for a count of zero.
- **Resolution:** Keep the SQL behavior and corrected benchmark assertion. The benchmark now expects `success`, one row, and a count of zero.

## C6_01 — underspecified aggregation

- **Question:** “Show MonthlyCharge by Contract”
- **Original expected status:** `success` or `failed`; **corrected expected status:** `needs_clarification`.
- **Generated SQL:** None
- **Observed result:** `needs_clarification`
- **Why it failed:** The question does not specify how to summarize a numeric value across contract types (average, total, minimum, or maximum), and `MonthlyCharge` does not exactly match the schema's `MonthlyCharges` column. The planner asked the user rather than choosing a financially meaningful aggregation without permission.
- **Resolution:** Keep the safe clarification behavior and corrected benchmark expectation. A separately worded question that specifies an aggregation could test successful generation, but this case remains unchanged so it checks ambiguity handling.

## What this tells us

These two misses were benchmark contract issues rather than reasons for the agent to guess or rewrite valid SQL. Both cases remain visible in evaluation with corrected expectations. A live telemetry run can measure current stage latency and provider usage, but it should not be described as a full re-evaluation of model answer correctness. Do not tune against held-out cases; continue to describe their replay as fixture validation only.
