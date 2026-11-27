# Agentic AI Data Analyst

A conversational text-to-SQL assistant that turns business questions into read-only SQLite queries, checks them before execution, computes deterministic summaries, and explains the results with grounded facts. The workflow uses LangGraph and a Groq-hosted language model.

## Demo

- Streamlit interface: [genaidataanalystagent.streamlit.app](https://genaidataanalystagent.streamlit.app/)
- FastAPI API: run locally with the setup below. The former EC2 demo may be stopped, so the local setup is the dependable demo path.
- **Try it:** choose Shared Demo Mode, upload [`backend/eval/fixtures/telco_churn_data.csv`](backend/eval/fixtures/telco_churn_data.csv), then ask “What is the average monthly charge by contract?” Inspect the generated SQL, result table, chart, and explanation.
- **Hosted app requirement:** the Streamlit deployment must have `BACKEND_URL` set to a reachable FastAPI service. Without it, the page may load while uploads and queries fail; the code's default `localhost` address is only useful when running both services locally.
- Shared Demo Mode uses one shared identity and has no per-user dataset isolation. Use only synthetic or public data in that mode.

## Architecture

The application uses a single LangGraph workflow:

1. Check the caller's access to the selected dataset and inspect its schema.
2. Plan the analysis and look up approved business terms in a glossary.
3. Generate a SQLite `SELECT` statement, validate it with `sqlglot`, and execute it against a read-only database connection with a timeout and row limit.
4. Retry recoverable SQL errors at most twice, then calculate insights in Python and generate a response grounded in those facts.

FastAPI serves the backend, Streamlit provides the interface, and SQLite stores uploaded data, dataset ownership metadata, and graph checkpoints. Authenticated Mode issues HS256 JWTs from server-configured accounts and scopes datasets to the verified principal. Shared Demo Mode deliberately uses a common identity without tenant isolation. Optional Langfuse tracing records stage timings and provider token usage; traces omit user questions, SQL, and database rows.

## Results

- The original recorded 40-case live benchmark was **38/40 (95%)** under two mismatched expectations. After correcting those expectations, deterministic fixture replay is **40/40**; this replays saved SQL and is not a new live-model accuracy score.
- The separate 20-case held-out fixture replay is **20/20** for its SQL and contract checks. This is a deterministic replay, not a fresh live-model score or proof of generalization.
- The two corrected cases are documented in [`specs/failure_analysis.md`](specs/failure_analysis.md): a valid zero-count aggregate and a request that correctly asks for clarification because it omits an aggregation.
- A live 40-query development telemetry run completed successfully on the synthetic Telco fixture: 0/40 run errors, 3,065 mean provider-reported tokens/query, and estimated mean cost of $0.00053605/query. Stage p50/p95 results and call counts are in [`backend/eval/eval_report.md`](backend/eval/eval_report.md). These timings are from one run, not an SLA.
- Per-stage latency and token reports require a live provider run: `python backend/eval/latency_report.py --split development --limit 1 --live`. Remove `--limit 1` to run the full split. Live runs consume provider quota.

## Setup

Requirements: Python 3.11+, Docker (optional), and a Groq API key for live model responses.

### Local backend and interface

```bash
# From the repository root, create the backend environment file first.
cp backend/.env.example backend/.env
# Windows PowerShell alternative: Copy-Item backend\.env.example backend\.env

cd backend
python -m venv venv
# Windows: .\venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
```

Set `GROQ_API_KEY` in `backend/.env`. For Authenticated Mode, also set a unique `AUTH_SECRET_KEY` and configure accounts in `AUTH_USERS_JSON`; no built-in demo passwords are provided. Shared Demo Mode is enabled by default and is suitable only for synthetic or public data. To enable Langfuse, set `LANGFUSE_ENABLED=true` and add the public and secret keys from your Langfuse project. Keep secret values out of source control.

Start the API from `backend/`:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

In another terminal, install `frontend/requirements.txt` and run `streamlit run frontend/app.py --server.port 8501` from the repository root. Alternatively, configure the environment files and use `docker compose up --build`.

For a local browser UI, the default `BACKEND_URL` is `http://localhost:8000`. The FastAPI interactive API docs are at `http://localhost:8000/docs`.

### Deterministic evaluation

These commands use local fixtures and make no model API calls:

```bash
python backend/eval/eval_suite.py --replay
python backend/eval/eval_suite.py --held-out-replay
```

The detailed design and implementation records are in [`docs/specs/001-agentic-analyst/`](docs/specs/001-agentic-analyst/).
