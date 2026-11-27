# 📊 GenAI Agentic AI Data Analyst

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.42+-FF4B4B.svg?logo=streamlit&logoColor=white)](https://streamlit.io)
[![LangGraph](https://img.shields.io/badge/LangGraph-Stateful_Workflows-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Groq LPU](https://img.shields.io/badge/Groq-Fast_Inference-f55036.svg)](https://groq.com)
[![sqlglot AST](https://img.shields.io/badge/Security-sqlglot_AST_Enforced-green.svg)](https://github.com/tobymao/sqlglot)
[![CI Workflow](https://img.shields.io/badge/CI-GitHub_Actions_Offline-success.svg)](.github/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A production-grade, stateful **Agentic AI Data Analyst** that converts natural language business questions into verified read-only SQL queries, executes them within sandboxed databases, computes deterministic statistical insights, and delivers grounded executive explanations.

🔗 **[Live Streamlit Application](https://genaidataanalystagent.streamlit.app/)**  
🔗 **[Local Interactive OpenAPI Docs](http://localhost:8000/docs)** *(when running locally)*

---

## 📑 Table of Contents

- [Architectural Philosophy](#-architectural-philosophy)
- [Workflow Architecture](#-workflow-architecture)
- [Key Engineering Pillars](#-key-engineering-pillars)
- [Evaluation & Benchmark Audit](#-evaluation--benchmark-audit)
- [Observability, Telemetry & Cost Engine](#-observability-telemetry--cost-engine)
- [Repository Structure](#-repository-structure)
- [Quickstart & Local Setup](#-quickstart--local-setup)
- [Automated Testing & CI/CD](#-automated-testing--cicd)
- [REST API Reference](#-rest-api-reference)

---

## 🎯 Architectural Philosophy

Naïve text-to-SQL solutions suffer from severe production vulnerabilities: hallucinated columns, ungrounded narrative metrics, SQL injection attacks, runaway token consumption, and missing conversational context.

This system solves these failure modes by enforcing a strict division of responsibility between **Probabilistic LLM Reasoning** and **Deterministic Code Verification**:

| Concern | Probabilistic LLM Layer | Deterministic Code Guardrails |
| :--- | :--- | :--- |
| **Intent & Planning** | Classifies analytical intent; identifies ambiguous questions; searches business glossary | Rejects non-analytical queries (`rejected`); requests input on underspecified dimensions (`needs_clarification`) |
| **SQL Generation** | Generates schema-aligned SQLite queries with column projections | `sqlglot` AST parsing blocks DDL/DML, stacked queries (`;`), system PRAGMAs, and open wildcards (`SELECT *`) |
| **Execution** | Diagnoses syntax and schema errors for bounded self-repair ($\le 2$ retries) | Read-only connection (`mode=ro`), 10-second query deadline, strict 1,000-row limit with truncation flags |
| **Analytics** | Identifies strategic business takeaways and recommended actions | Pandas computes SUM, AVG, MIN, MAX, stdev, % share, and trend shapes deterministically |
| **Fact Grounding** | Drafts concise executive briefings and narrative memos | Validates all numbers in narrative against Pandas output; rejects text if hallucinated figures are detected |

---

## 🔄 Workflow Architecture

The core agent is built as a stateful **LangGraph** workflow with persistent session memory (`SqliteSaver` checkpoints):

```
                        ┌────────────────────────────────────────────────────────┐
                        │             User Query via Streamlit UI / API          │
                        └───────────────────────────┬────────────────────────────┘
                                                    │ POST /query (session_id, dataset_id)
                                                    ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       LANGGRAPH STATE MACHINE                                          │
│                                                                                                        │
│   ┌───────────────────────────┐         ┌───────────────────────────┐         ┌────────────────────┐   │
│   │   analyzer_planner_node   │ ──────> │    sql_generator_node     │ ──────> │ sql_validator_node │   │
│   │   - Intent classification │         │   - Few-shot schema prompt│         │ - sqlglot AST check│   │
│   │   - Glossary RAG lookup   │         │   - Scoped column mapping │         │ - DDL/DML rejection│   │
│   │   - Ambiguity detection   │         │   - Dialect: SQLite       │         │ - Wildcard block   │   │
│   └─────────────┬─────────────┘         └───────────────────────────┘         └─────────┬──────────┘   │
│                 │                                                                       │              │
│       [Ambiguous / Out-of-Scope]                                                 [Pass / Fail]         │
│                 │                                                                  /        \          │
│                 ▼                                                  ┌──────────────┐          ▼         │
│       needs_clarification / rejected                               │ query_exec   │     repair_node    │
│                                                                    │ - Read-only  │     (Max 2 retries)│
│                                                                    │ - 10s deadline      ▲             │
│                                                                    └──────┬───────┘      │             │
│                                                                           │              │             │
│                                                            [Syntax/Runtime Error]────────┘             │
│                                                                           │                            │
│                                                                    [Rows Returned]                     │
│                                                                           │                            │
│                                                                           ▼                            │
│                                                            ┌──────────────────────────────┐            │
│                                                            │   analytics_insights_node    │            │
│                                                            │   - Pandas KPI calculations  │            │
│                                                            │   - Plotly chart selection   │            │
│                                                            └──────────────┬───────────────┘            │
│                                                                           │                            │
│                                                                           ▼                            │
│                                                            ┌──────────────────────────────┐            │
│                                                            │   narrative_explainer_node   │            │
│                                                            │   - Grounded executive memo  │            │
│                                                            │   - Metric hallucination check│           │
│                                                            └──────────────────────────────┘            │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛡️ Key Engineering Pillars

### 1. AST-Based SQL Security Sandboxing
All generated queries pass through Abstract Syntax Tree (AST) inspection via `sqlglot` before touching SQLite:
* **Blocked Statements:** `DROP`, `DELETE`, `INSERT`, `UPDATE`, `ALTER`, `ATTACH`, `DETACH`, `PRAGMA`.
* **Blocked Syntaxes:** Stacked SQL statements (`;`), system table reads (`sqlite_master`), and unrestricted wildcards (`SELECT *`).
* **Enforced Limits:** Queries lacking explicit limits are automatically capped at 1,000 rows.

### 2. Verified Authentication & Dataset Isolation
* **Server-Derived Identity:** Tokens are minted exclusively through `/auth/token` via `AUTH_USERS_JSON` using constant-time comparison (`hmac.compare_digest`). Callers cannot forge identities or roles via headers.
* **Fail-Closed Security:** The application refuses to sign tokens if `AUTH_SECRET_KEY` is unset; no insecure default fallback secrets are permitted.
* **Tenant Isolation:** Uploaded datasets are strictly mapped to the caller's verified `principal_id`. Cross-tenant dataset access attempts return `403 Forbidden`.
* **Explicit Operating Modes:**
  * **Authenticated Mode:** Strict multi-tenant isolation enforced via HS256 Bearer JWTs.
  * **Shared Demo Mode:** Clearly designated single-tenant mode for public demonstrations and synthetic datasets.

### 3. Multi-Turn Context & Bounded Self-Repair
* **Conversational Checkpointing:** Durable `SqliteSaver` checkpoints maintain previous turn SQL and filter contexts (e.g. *"Filter that down to only Fiber optic"* or *"Break that down by Contract"*).
* **Self-Healing Loop:** If SQLite throws a syntax or schema runtime error, the `repair_node` diagnoses the error message and regenerates SQL. The repair loop is strictly bounded to $\le 2$ retries (3 total attempts).

---

## 🏆 Evaluation & Benchmark Audit

The system is evaluated against an end-to-end benchmark suite using a **two-tier grading methodology**:
1. **Tier 1 (Contract Compliance):** Verifies termination in the expected status (`success`, `empty`, `needs_clarification`, `rejected`).
2. **Tier 2 (Semantic Data Correctness):** Checks row counts against expected bounds, verifies scalar totals, and validates self-repair recovery.

### 40-Case Benchmark Scorecard

| Category | Cases | Live Baseline | Offline Replay | Key Verification Finding |
| :--- | :---: | :---: | :---: | :--- |
| **1. Aggregation & Grouping** | 12 | 12/12 (100%) | 12/12 (100%) | Schema-aligned aggregations without `SELECT *`. |
| **2. Comparisons & Dates** | 6 | 6/6 (100%) | 6/6 (100%) | Numerical boundaries (`BETWEEN`, `>=`, `<=`) correctly parsed. |
| **3. Glossary RAG & Follow-Ups** | 6 | 6/6 (100%) | 6/6 (100%) | Multi-turn filters preserved; acronyms (`ARPU`, `Churn`) mapped. |
| **4. Ambiguity & Rejection** | 6 | 5/6 (83.3%) | 6/6 (100%)* | Non-analytical queries rejected; ambiguous questions clarified. |
| **5. SQL Security & Injection** | 6 | 6/6 (100%) | 6/6 (100%) | `DROP TABLE`, stacked queries, and wildcards blocked at AST level. |
| **6. Repair & Edge Recovery** | 4 | 3/4 (75.0%) | 4/4 (100%)* | Self-repair recovery bounded to 2 retries. |
| **TOTAL** | **40** | **38/40 (95.0%)** | **40/40 (100%)** | Verified end-to-end contract and data assertions. |

*\* Detailed failure analysis and reconciliation documented in [`specs/failure_analysis.md`](specs/failure_analysis.md):*
* **`C4_04` ("Total customers with tenure > 500"):** The query returned `COUNT(customerID) = 0` as a valid 1-row scalar. The original assertion expected 0 rows. Corrected to expect `success` with `total_customers = 0`.
* **`C6_01` ("Show MonthlyCharge by Contract"):** Ambiguous request (did not specify `AVG`, `SUM`, `MIN`, or `MAX`). Rather than guessing financial metrics, the agent properly triggered `status: needs_clarification`.

### 20-Case Frozen Held-Out Benchmark
To ensure generalization without test set contamination, a separate 20-question suite ([`backend/eval/held_out_benchmark.json`](backend/eval/held_out_benchmark.json)) was created and frozen.
* **Held-Out Replay Score:** **20/20 (100%)** across multivariable aggregations, range filters, empty matches, and injection payloads.
* *Provenance Note:* Offline replay verifies pipeline contracts, AST rules, and SQLite query semantics deterministically without calling external LLM APIs.

---

## 📈 Observability, Telemetry & Cost Engine

The backend includes a local, privacy-first telemetry engine ([`backend/app/core/telemetry.py`](backend/app/core/telemetry.py)):

* **Per-Node Tracing Spans:** Records individual latencies, provider token consumption, and status across `planner`, `sql_generator`, `validator_executor`, `repair`, `insights`, and `narrative`.
* **Exact Cost Accounting:** Calculates USD cost per query using official published provider token rates ($0.59 / $0.79 per 1M tokens for Groq models) rather than guessing.
* **Privacy by Default:** User questions, generated SQL, raw database rows, and credentials are automatically scrubbed from external telemetry payloads unless `TELEMETRY_CAPTURE_CONTENT=true` is explicitly enabled.

---

## 📁 Repository Structure

```
GenAI_Data_Analyst_Agent/
├── .github/
│   └── workflows/
│       └── ci.yml                      # GitHub Actions CI (runs 38 offline tests deterministically)
├── backend/
│   ├── app/
│   │   ├── agent/
│   │   │   ├── graph.py                # LangGraph state machine & SqliteSaver persistence
│   │   │   ├── nodes.py                # Graph nodes (planner, sql_gen, validator, repair, insights, narrative)
│   │   │   ├── state.py                # Typed Pydantic models (AgentState, QueryRequest, QueryResponse)
│   │   │   └── tools.py                # Structured tool schemas & fallback parsers
│   │   ├── core/
│   │   │   ├── auth.py                 # Fail-closed HMAC-SHA256 JWT auth & credential verification
│   │   │   ├── dataset_registry.py     # Multi-tenant dataset isolation & size limits
│   │   │   ├── logger.py               # Structured JSON logging
│   │   │   ├── rate_limiter.py         # Sliding-window rate limiting
│   │   │   ├── schema_inspector.py     # SQLite schema and column introspection
│   │   │   ├── sql_validator.py        # sqlglot AST security parser
│   │   │   ├── telemetry.py            # Trace spans, token accounting & exact cost engine
│   │   │   └── utils.py                # Column type coercion & date helpers
│   │   ├── services/
│   │   │   ├── glossary.py             # SQLite-backed Business Glossary RAG
│   │   │   ├── insights_engine.py      # Deterministic Pandas metrics & Plotly chart logic
│   │   │   ├── query_executor.py       # Sandboxed SQLite execution with timeout enforcement
│   │   │   └── providers/
│   │   │       ├── base.py             # LLMProvider abstract interface
│   │   │       └── groq_provider.py    # Groq provider with structured output & token usage
│   │   └── main.py                     # FastAPI application & REST endpoints
│   ├── eval/
│   │   ├── fixtures/                   # Synthetic Telco dataset fixtures
│   │   ├── eval_suite.py               # Benchmark runner (--replay / --held-out-replay / --live)
│   │   ├── held_out_benchmark.json     # 20-case frozen held-out benchmark
│   │   ├── offline_replay_results.json # 40-case deterministic replay results (100%)
│   │   ├── held_out_replay_results.json# 20-case held-out replay results (100%)
│   │   └── latency_report.py           # Per-node p50/p95 latency aggregation
│   ├── tests/                          # 38 unit & regression tests (offline passing + skipped live)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app.py                          # Streamlit UI with telemetry breakdown & auth modes
│   ├── Dockerfile
│   └── requirements.txt
├── docs/
│   ├── specs/001-agentic-analyst/      # Architecture specifications & baseline reports
│   └── deployment_guide.md             # Docker and cloud deployment runbook
├── specs/
│   └── failure_analysis.md             # In-depth root cause analysis of historical misses
├── docker-compose.yml
├── .env.example
└── Readme.md
```

---

## ⚡ Quickstart & Local Setup

### Prerequisites
* Python 3.11+
* Git
* A free [Groq API Key](https://console.groq.com)

### 1. Clone & Set Up Environment

```bash
git clone https://github.com/omrohitchannoji/GenAI_Data_Analyst_Agent.git
cd GenAI_Data_Analyst_Agent

# Copy environment configuration
cp backend/.env.example backend/.env
# On Windows PowerShell: Copy-Item backend\.env.example backend\.env
```

Edit `backend/.env` and insert your credentials:
```ini
GROQ_API_KEY=gsk_your_actual_key_here
GROQ_MODEL=openai/gpt-oss-120b

# Security Configuration
AUTH_SECRET_KEY=your_secure_random_hmac_key_here_minimum_32_chars
AUTH_USERS_JSON={"analyst_user": {"password": "secure_password_123", "role": "analyst"}}
```

### 2. Backend Installation & Startup

```bash
cd backend
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
*API interactive documentation will be available at [http://localhost:8000/docs](http://localhost:8000/docs).*

### 3. Frontend Installation & Startup

In a new terminal window:
```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py --server.port 8501
```
*The Streamlit web interface will open at [http://localhost:8501](http://localhost:8501).*

### 4. Running with Docker Compose (Alternative)

```bash
docker compose up --build
```
This automatically boots FastAPI on port `8000` and Streamlit on port `8501`.

---

## 🧪 Automated Testing & CI/CD

The project enforces high test reliability using GitHub Actions ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)). The CI pipeline runs **100% offline** without needing external API credentials or secrets:

### Run Unit & Integration Tests (38 Tests)
```bash
pytest backend/tests/ -v -rs
```
*Status: 33 passed, 5 skipped (live Groq tests skip gracefully when credentials are unset), 0 failed.*

### Run Deterministic Evaluation Replays
```bash
# 40-case evaluation replay:
python backend/eval/eval_suite.py --replay

# 20-case frozen held-out evaluation replay:
python backend/eval/eval_suite.py --held-out-replay
```

---

## 🔌 REST API Reference

| Endpoint | Method | Auth Required | Description |
| :--- | :---: | :---: | :--- |
| `/health` | `GET` | No | Health check and system uptime status. |
| `/auth/token` | `POST` | No | Authenticates credentials and returns a signed HS256 JWT bearer token. |
| `/upload` | `POST` | Optional* | Uploads CSV dataset with schema inspection and principal scoping. |
| `/datasets` | `GET` | Optional* | Lists datasets accessible to the authenticated principal. |
| `/query` | `POST` | Optional* | Executes full LangGraph analysis pipeline for natural language question. |
| `/run_sql` | `POST` | Admin | Executes raw read-only SQL with AST validation and 10s deadline. |

*\* In Authenticated Mode, endpoints require an `Authorization: Bearer <token>` header. In Shared Demo Mode, unauthenticated callers default to `demo_user`.*

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
