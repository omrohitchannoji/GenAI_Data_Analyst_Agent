# 🤖 Agentic AI Data Analyst

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![sqlglot](https://img.shields.io/badge/sqlglot-AST_Security-purple.svg)](https://github.com/tobymao/sqlglot)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-FF4B4B.svg)](https://streamlit.io)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)

A production-grade, stateful **Agentic AI Data Analyst** that converts business questions into secure, validated SQL, deterministically computes analytical metrics and interactive charts, and delivers grounded, consulting-style executive narratives.

Built with a **single-agent LangGraph state machine**, strict **`sqlglot` AST security parsing**, **read-only SQLite query sandboxing**, and **durable session checkpoints (`SqliteSaver`)**.

🔗 [Live Streamlit App](https://genaidataanalystagent-omrohit.streamlit.app/)  
🔗 [Live FastAPI Docs (AWS EC2)](http://13.203.201.200:8000/docs)  
🔗 [API Health Check](http://13.203.201.200:8000/health)

---

## 🎯 Architecture & Design Philosophy

The system strictly divides responsibilities between **Probabilistic LLM Reasoning** and **Deterministic Code Execution**:

```
                       ┌────────────────────────────────────────────────────────┐
                       │               User Query via Streamlit UI             │
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
│                                                            │   - Metric hallucination check│            │
│                                                            └──────────────────────────────┘            │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 1. LLM Reasoning (Probabilistic)
* **Intent & Ambiguity Detection:** Classifies analytical intent and identifies genuinely underspecified questions before touching databases.
* **Domain Glossary RAG:** Matches business acronyms (e.g., `ARPU`, `Churn Rate`, `High Value Customer`) to concrete database columns and formulas.
* **SQL Generation & Bounded Self-Repair:** Generates clean SQLite queries. If execution or validation errors occur, it diagnoses errors and repairs SQL (strictly bounded to $\le 2$ repair retries, 3 attempts total).
* **Executive Explanations:** Synthesizes business context, observations, and recommendations grounded strictly in computed facts.

### 2. Deterministic Code (Zero Hallucination)
* **`sqlglot` AST Security Policy:** Analyzes query Abstract Syntax Trees before execution. Blocks all DDL/DML (`DROP`, `INSERT`, `UPDATE`, `ALTER`, `ATTACH`), stacked statements (`;`), system PRAGMAs, and open `SELECT *` wildcards.
* **Read-Only SQLite Execution:** Queries run against URI connection strings in `mode=ro` with an active `progress_handler` timeout (10-second hard deadline).
* **Statistical Insights Engine:** Computes SUM, AVG, MIN, MAX, standard deviation, percentage contributions, and trend shapes deterministically in Pandas.
* **Chart Routing:** Selects bar, line, scatter, KPI card, or tabular views using deterministic data shape rules.
* **Grounded Narrative Fallback:** Replaces or rejects generated text if the LLM invents numbers not present in the deterministic facts.

---

## 🚦 Exactly 5 Terminal Statuses

Every execution terminates in one of five well-defined contract states:

| Status | Meaning | Typical Trigger |
|---|---|---|
| `success` | Valid SQL executed, deterministic insights computed, grounded narrative generated. | Clean analytical query. |
| `empty` | Valid SQL executed without errors, but returned 0 rows. | Strict filters (e.g., `MonthlyCharges > 10000`). |
| `needs_clarification` | Query is ambiguous or underspecified; requests user input. | *"Show me the best one"* (no metric or dimension specified). |
| `rejected` | Security violation, destructive DDL/DML, stacked statement, or out-of-scope query. | *"DROP TABLE customers"*, *"What is the weather in Paris?"* |
| `failed` | Max repair budget exhausted ($3$ attempts) or unrecoverable system exception. | Invalid table join unresolvable after 2 repair retries. |

---

## 🏆 Evaluation Benchmark & Scorecard

Evaluated against an exhaustive **40-Question End-to-End Test Suite** (`backend/eval/eval_suite.py`) spanning 8 analytical categories on real-world Telco Churn and Sales data:

| Category | Questions | Passed | Success Rate | Baseline Pass Rate |
|---|---|---|---|---|
| **Simple Aggregation** | 5 | 5 | **100%** | 80% |
| **Grouping & Top-N** | 5 | 5 | **100%** | 80% |
| **Multi-Column Filtering** | 5 | 5 | **100%** | 60% |
| **Domain Glossary Mapping** | 5 | 5 | **100%** | 20% |
| **Multi-Turn Context Follow-Ups** | 5 | 5 | **100%** | 0% (Stateless) |
| **Security & Injection Attack** | 5 | 5 | **100%** | 0% (Arbitrary fallback execution) |
| **Edge Cases & Empty Results** | 5 | 4 | **80%** | 40% |
| **Ambiguity & Clarification** | 5 | 4 | **80%** | 20% |
| **TOTAL** | **40** | **38** | **95.0%** | **37.5%** |

### Key Improvements Over Baseline
1. **Security:** Malicious queries like `DROP TABLE data` are blocked at the AST validator (`rejected`), preventing catastrophic data loss or erratic fallback queries.
2. **Multi-Turn Memory:** Conversational follow-ups (*"Filter that only for Fiber optic"* or *"Break that down by Contract"*) resolve using prior turn SQL and filters via durable `SqliteSaver` checkpoints.
3. **Domain Glossary:** Acronyms like `ARPU` or `churn rate` resolve to accurate database column formulas rather than hallucinated column names.
4. **Zero Metric Hallucination:** All numbers reported in the executive summary match the Pandas computation to two decimal places.

---

## 📁 Repository Structure

```
data_analyst_agent/
├── backend/
│   ├── app/
│   │   ├── agent/
│   │   │   ├── graph.py               # LangGraph state machine & SqliteSaver persistence
│   │   │   ├── nodes.py               # Planner, SQL generator, validator, repair, insights, narrative
│   │   │   ├── state.py               # Typed Pydantic models (AgentState, QueryRequest, QueryResponse)
│   │   │   └── tools.py               # Structured LLM tool schemas & fallback parsers
│   │   ├── core/
│   │   │   ├── config.py              # Application settings (Pydantic Settings)
│   │   │   ├── dataset_registry.py    # Multi-tenant dataset tracking, authorization & size caps
│   │   │   ├── logger.py              # Structured JSON logging
│   │   │   ├── rate_limiter.py        # Sliding-window rate limiter (20 req / 60s)
│   │   │   ├── schema_inspector.py    # SQLite table and column introspection
│   │   │   └── sql_validator.py       # sqlglot AST security parser
│   │   ├── services/
│   │   │   ├── glossary.py            # SQLite-backed Business Glossary RAG
│   │   │   ├── insights_engine.py     # Deterministic Pandas metrics & Plotly chart logic
│   │   │   ├── query_executor.py      # Read-only SQLite executor with 10s deadline
│   │   │   └── providers/
│   │   │       ├── base.py            # LLMProvider abstract interface
│   │   │       └── groq_provider.py   # Groq provider with structured JSON mode & token accounting
│   │   └── main.py                    # FastAPI application & REST endpoints
│   ├── eval/
│   │   ├── fixtures/                  # Benchmark datasets (sales_data.csv)
│   │   └── eval_suite.py              # 40-question automated evaluation runner
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app.py                         # Modern Streamlit UI with real-time progress timeline
│   ├── Dockerfile
│   └── requirements.txt
├── specs/001-agentic-analyst/
│   ├── constitution.md                # System invariants & architectural contracts
│   ├── contracts.md                   # API & state schema specifications
│   ├── evaluation_report.md           # 40-question benchmark report & latency breakdown
│   ├── baseline_report.md             # Flaws and benchmark of legacy system
│   └── tasks.md                       # Implementation ledger & verification evidence
├── docs/
│   └── deployment_guide.md            # AWS EC2 / Docker deployment runbook
├── docker-compose.yml
├── .env.example
└── Readme.md
```

---

## ⚡ Quickstart Guide

### Option 1: Docker Compose (Recommended)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/omrohitchannoji/GenAI_Data_Analyst_Agent.git
   cd GenAI_Data_Analyst_Agent
   ```

2. **Configure Environment Variables:**
   ```bash
   cp .env.example .env
   # Edit .env and insert your GROQ_API_KEY
   ```

3. **Start backend and frontend services:**
   ```bash
   docker-compose up --build
   ```

4. **Access the application:**
   * **Streamlit UI:** `http://localhost:8501`
   * **FastAPI Docs:** `http://localhost:8000/docs`
   * **Health Check:** `http://localhost:8000/health`

---

### Option 2: Local Development

#### Prerequisites
* Python 3.11+
* Active [Groq Cloud API Key](https://console.groq.com/)

#### 1. Backend Setup
```bash
cd backend
python -m venv venv

# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file in `backend/` (or repository root):
```env
GROQ_API_KEY=gsk_your_actual_groq_key_here
GROQ_MODEL=openai/gpt-oss-120b
DATASET_DIR=data
DB_PATH=uploaded_data.db
CHECKPOINT_DB_PATH=agent_checkpoints.db
LOG_LEVEL=INFO
```

Start the FastAPI server:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Frontend Setup
In a new terminal window:
```bash
cd frontend
python -m venv venv

# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

Start Streamlit:
```bash
streamlit run app.py --server.port 8501
```

---

## 🧪 Running the Test Suite & Evaluation

The repository includes complete test coverage across all architectural boundaries:

```bash
# Run unit & integration tests
pytest tests/ -v

# Run the 40-question end-to-end benchmark suite
python backend/eval/eval_suite.py
```

---

## 🛡️ Security & Guardrails

1. **AST Validation vs. Regex:** Traditional regex checks (`if "DROP" in query`) are trivially bypassed by comments or string literals (e.g. `WHERE status = 'DROPPED'`). This agent uses `sqlglot` to parse the Abstract Syntax Tree, strictly permitting only `Select` and `CTE` roots.
2. **SQLite Read-Only Pragmas:** The database file is opened with `file:...mode=ro` flags. Even if a statement bypassed AST checks, the SQLite storage engine raises an operational error on any write operation.
3. **Execution Deadlines:** Large cross-joins or infinite query loops are interrupted via SQLite's `set_progress_handler` every 10,000 instructions, terminating execution if runtime exceeds 10 seconds.
4. **Row Truncation:** Result sets are capped at 1,000 rows for serialization and display, preventing memory exhaustion and UI lockups.
5. **Rate Limiting:** Sliding-window in-memory rate limiter enforces 20 requests per 60-second window per IP.

---

## 💡 Key Design Decisions & Interview FAQ

### Why LangGraph instead of Multi-Agent Swarms (AutoGen / CrewAI)?
Multi-agent swarms introduce compounding non-determinism, unpredictable token consumption, and complex debugging surfaces for a single-domain task. This project uses a **single-agent cyclic state machine (LangGraph)** with explicit conditional edges (`should_repair`, `route_intent`). State is strictly typed, transitions are deterministic, and repair loops are capped at 2 iterations.

### Why not execute raw Python code generated by the LLM?
Executing arbitrary Python code generated by an LLM in a production analytical app is a major remote code execution (RCE) risk requiring complex gVisor or Docker sandboxes. By restricting the LLM to **pure SQL generation** validated via AST, and running **deterministic Pandas calculations** in the host runtime, the system is 100% secure, reproducible, and verifiable.

### How are multi-turn conversations handled?
User conversations are identified by `session_id`. The LangGraph workflow persists states via an SQLite checkpointer (`SqliteSaver`). When a follow-up query is received (e.g., *"Filter only for contract month-to-month"*), the planner inspects `prior_context` and reformulates the SQL using the previous query's dimensions and filters. Switching datasets automatically clears prior context to prevent cross-dataset contamination.

---

## 📄 License
This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
