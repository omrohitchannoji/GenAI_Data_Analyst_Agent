# Audit Document: Existing GenAI Data Analyst Application
**Task Reference:** T01 (Requirement R01)  
**Date:** 29 September 2026  
**Auditor:** AI Assistant & Omrohit Channoji  

---

## 1. Executive Summary

An audit of the existing repository was performed prior to making any code modifications.
The current project is a prototype GenAI Data Analyst composed of:
- **Backend:** FastAPI with SQLite, Pandas, Chroma, and direct HTTP calls to the Groq API (`llama-3.1-8b-instant`).
- **Frontend:** Streamlit application providing CSV upload, question asking, and dashboard visualization.

While the baseline contains functional data processing components (specifically Pandas-based statistical summaries in `insights_engine.py`), the query and LLM execution flows are linear, stateless, vulnerable to SQL injection bypass, and lack agentic self-correction or durable session tracking.

---

## 2. Component Inventory & Data Flow

### 2.1 Backend Architecture (`backend/`)
- **`backend/app/main.py`**:
  - `POST /upload_csv`: Ingests uploaded CSV into an SQLite file (`uploaded_data.db`) under table `data`. Extracts column types via `detect_column_types()` and stores them in a global variable `stored_column_types`. Builds a dataset context and vector store using `sentence-transformers/all-MiniLM-L6-v2`.
  - `POST /run_sql`: Accepts a SQL string, checks if it starts with `"select"` (case-insensitive string prefix), and queries SQLite.
  - `POST /ask_data`: Accepts `{"question": "...", "session_id": "..."}`, calls `run_sql_with_correction()`, coerces the second column to numeric, stores the turn in an in-memory dictionary `conversation_memory`, and returns the SQL and rows.
  - `POST /insights`: Re-runs `run_sql_with_correction()`, passes the resulting DataFrame to `insights_engine.py` for rule-based summaries, and then makes an LLM call to Groq via `llm_agent.py` to produce a consulting-style explanation.
  - `POST /dataset_summary`: Queries first 10 rows of `data` and returns an LLM dataset summary.
- **`backend/app/services/insights_engine.py`**:
  - Computes `top_bottom_groups()`, `detect_anomalies()` (z-score $> 2$), `summarize_grouped()` (mean, median, % difference top vs median), and `suggest_chart()`.
  - **Verdict:** Highly reusable, deterministic, and statistically sound. To be preserved and integrated directly into the Agentic graph.
- **`backend/app/services/query_engine.py`**:
  - Contains keyword-based heuristics (`AGG_KEYWORDS`) and string similarity matching for fallback SQL generation.
- **`backend/app/services/llm_sql.py` & `llm_agent.py`**:
  - Handcrafted prompt templates making raw `requests.post()` calls to `https://api.groq.com/openai/v1/chat/completions` using `llama-3.1-8b-instant`.
  - Basic backoff on HTTP 429; no structured output validation or provider abstraction.
- **`backend/rag/`**:
  - Prototype RAG pipeline using Chroma and LangChain embeddings. Has minor typos (e.g. `as_retrieve` instead of `as_retriever`).

### 2.2 Frontend Architecture (`frontend/`)
- **`frontend/app.py`**:
  - Streamlit dashboard with 3 tabs: Upload Dataset, Ask Questions, and Analysis Dashboard.
  - Currently hardcodes `BACKEND_URL = "http://13.201.45.117:8000/"` (an external EC2 IP).
  - When the user runs an analysis, it makes **two sequential HTTP requests**:
    1. First to `/ask_data` (generating SQL and fetching rows).
    2. Second to `/insights` (re-generating SQL, re-executing query, computing insights, and generating LLM narrative).
  - This double-execution adds unnecessary latency and doubles LLM token consumption.

---

## 3. Critical Findings & Technical Debt

| Area | Current Implementation | Risk / Limitation | Upgrade Action |
|---|---|---|---|
| **SQL Security** | `sql.strip().lower().startswith("select")` | Bypassed by comments, chained queries (`SELECT 1; DROP TABLE data`), subquery mutations. | Enforce AST parsing with `sqlglot`; ensure root AST is strictly `exp.Select` and disallow wildcards/mutations. |
| **State & Memory** | Python dictionary `conversation_memory` and global `stored_column_types` | Lost upon server restart; no dataset isolation; multi-user session collisions. | Introduce typed `AgentState` with durable LangGraph checkpointing and explicit `dataset_id`/`session_id` scoping. |
| **Workflow Architecture** | Procedural script with basic fallback | No iterative repair loop; no validation layers; cannot recover from schema hallucination. | Implement LangGraph `StateGraph` with bounded repair loop ($\le 3$ SQL attempts). |
| **Terminal Outcomes** | Ad-hoc error strings or fallback text | Client cannot distinguish between empty results, safety rejections, ambiguity, or failure. | Return explicit 5 terminal statuses: `success`, `empty`, `needs_clarification`, `rejected`, `failed`. |
| **Frontend/Backend Contract** | Dual endpoint calls (`/ask_data` then `/insights`) | High latency; duplicate SQL generation and LLM calls. | Single unified query endpoint invoking the LangGraph agent, returning SQL, data, chart spec, and verified insights. |

---

## 4. Reproducible Run & Deployment Baseline

### Environment
- **Python Version:** 3.13.2
- **Virtual Environment:** `backend/venv`

### Startup Commands
- **Backend:**
  ```powershell
  cd backend
  .\venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000 --reload
  ```
- **Frontend:**
  ```powershell
  cd frontend
  streamlit run app.py
  ```

---

## 5. Reuse, Replace, and Wrap Decisions

1. **REUSE (Keep Intact):**
   - `backend/app/services/insights_engine.py`: Retain core statistical computations (`summarize_grouped`, `detect_anomalies`, `top_bottom_groups`).
   - `backend/app/core/utils.py`: Retain `detect_column_types()`.
   - `emplyee_attrition.csv`: Use as standard testing fixture.
2. **WRAP / ADAPT:**
   - `backend/app/main.py`: Preserve `/upload_csv` for backward compatibility; add modern agentic `/query` contract.
   - `frontend/app.py`: Update to target configurable backend URL (`http://localhost:8000`) and consume unified agent payload with genuine progress status tracking (`st.status`).
3. **REPLACE / INTRODUCE:**
   - Introduce `backend/app/core/sql_validator.py` (`sqlglot` AST security).
   - Introduce `backend/app/agent/` (`state.py`, `tools.py`, `nodes.py`, `graph.py`).
   - Introduce `backend/app/services/providers/` (Groq adapter with capability testing).
   - Introduce `backend/eval/eval_suite.py` (Rigorous benchmark evaluation).
