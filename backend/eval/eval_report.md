# Evaluation Report

## 40-case development benchmark

- **Recorded live benchmark (original expectations):** 38/40 (95%). This historical run is not a new live-model result.
- **Corrected deterministic offline replay:** 40/40. It replays recorded model SQL against local SQLite fixtures and checks corrected expectations. It makes no model API calls and does not measure current live model quality or latency.
- **Expectation corrections:** C4_04 now checks for a successful scalar count of zero; C6_01 now expects clarification because the request omits an aggregation. See [`../../specs/failure_analysis.md`](../../specs/failure_analysis.md) for the evidence and rationale.

## Separate 20-case held-out fixture

- **Deterministic replay:** 20/20 (100%) on the local rule/SQL fixtures.
- The replay does not call the generator. The repository cannot independently establish that the questions remained hidden during all development, so this is not evidence of a blind or representative live-model test. Do not compare it directly with the 40-case live score.

## Live tracing and reporting

`latency_report.py` runs model requests only when `--live` is explicitly supplied. Live runs register and query only the synthetic Telco fixture, never the default uploaded-data database. It reports per-stage p50/p95 latency, repair-loop frequency, and tokens/query when all relevant provider calls returned usage data. It also reports cost only when the model has an explicit price in `MODEL_PRICING_TABLE` and token usage is complete. Unknown prices and missing token counts remain unavailable rather than being estimated.

Langfuse tracing is optional and disabled by default. It records stage status, latency, model, and available token usage; query text, generated SQL, and database rows are not attached to Langfuse observations.

The explicit cost table in `backend/app/core/telemetry.py` uses Groq's published per-million-token rates for GPT-OSS 120B and 20B, including the documented cached-input rate. Cost remains unavailable when cached-token counts or token usage are missing. [Groq model rates](https://console.groq.com/docs/models) · [Prompt-cache usage fields](https://console.groq.com/docs/prompt-caching).

### Live development telemetry run — 2026-11-27

The full 40-question development run completed against the synthetic Telco fixture with no run errors. Model: `openai/gpt-oss-120b` (Groq). These are observed stage timings from this run, not a latency guarantee; stage counts are lower where a case did not reach that node.

| Stage | Calls | p50 (ms) | p95 (ms) |
|---|---:|---:|---:|
| Planner | 40 | 12,319.25 | 15,510.38 |
| SQL generator | 24 | 6,603.70 | 10,075.35 |
| Validator | 24 | 1.85 | 6.21 |
| Executor | 24 | 1.60 | 4.74 |
| Repair | 0 | unavailable | unavailable |
| Insights | 23 | 2.90 | 17.27 |
| Narrative | 23 | 4,337.80 | 8,317.34 |

- Repair-loop frequency: **0/40 (0%)**.
- Mean provider-reported usage: **3,065.15 tokens/query**, with complete token usage for **40/40** cases.
- Mean estimated cost: **$0.00053605/query** using the configured model pricing table. Treat this as an estimate based on provider usage fields and configured rates.
- All 40 runs completed successfully. This telemetry run does not replace the separate answer-quality evaluation.

Example low-volume live run (uses provider quota):

```bash
python backend/eval/latency_report.py --split development --limit 1 --live
```

Full development and held-out runs:

```bash
python backend/eval/latency_report.py --split development --live
python backend/eval/latency_report.py --split held_out --live
```

## No-call replays

```bash
python backend/eval/eval_suite.py --replay
python backend/eval/eval_suite.py --held-out-replay
```
