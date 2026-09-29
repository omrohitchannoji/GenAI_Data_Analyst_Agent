# Implementation Plan: Stateful Agentic AI Data Analyst System Upgrade

## Goal Description
Upgrade the existing GenAI Data Analyst codebase (`backend/` and `frontend/`) from a stateless script-based LLM query pipeline into a production-grade, stateful **Agentic AI Data Analyst System**.

The target architecture uses **LangGraph** to model a single-agent stateful workflow with:
- **LLM Reasoning**: Intent parsing, multi-step planning, SQL query generation, repair strategy, and executive narrative generation.
- **Deterministic Execution**: AST SQL security parsing via `sqlglot`, SQLite database querying, Pandas quantitative calculations (sums, averages, top/bottom, anomalies, %, variance), and Plotly chart rendering.
- **Self-Correction & Bounded Repair Loop**: Multi-layered validation with an automated retry loop capped at $\le 3$ retries.
- **Business Glossary RAG**: Context retrieval using ChromaDB vector store.
- **Evaluation Benchmark Suite**: 20-30 end-to-end evaluation queries covering aggregations, filters, time analysis, glossary lookups, and malicious code injection prevention.
- **Streamlit Status Tracking UI**: Real-time event state visualization (`st.status`).

---

## Technical & Agentic Concepts Explained (For Learning)

To build intuition for Agentic AI, here is a conceptual breakdown of the 6 core components being introduced:

### 1. What is an "Agent State" (`AgentState`)?
In traditional API flows, data is passed linearly through function arguments. In **Agentic AI**, an **AgentState** acts as the *central memory chalkboard*. Every node in the agent graph reads from this state and writes back updates (such as updated plans, generated SQL, validation results, or error messages).

```python
class AgentState(TypedDict):
    question: str
    resolved_question: str
    intent: dict
    plan: dict
    schema: dict
    glossary_context: list
    generated_sql: str
    sql_result: list
    validation_status: str
    validation_reason: str
    retry_count: int
    analysis_result: dict
    chart_config: dict
    final_response: str
```

### 2. What is LangGraph & StateGraph?
Unlike simple chain abstractions (like basic LangChain `LLMChain`), **LangGraph** models AI decision-making as a **Directed Graph**:
- **Nodes**: Standard Python functions or LLM prompts that take `AgentState` as input and return updated state fields.
- **Edges**: Connections between nodes. **Conditional Edges** allow dynamic branching (e.g., *if validation passes $\rightarrow$ compute insights; if validation fails $\rightarrow$ go to repair node*).

### 3. What is AST-based SQL Security Parsing (`sqlglot`)?
Standard string checking (like `if "SELECT" in query`) can easily be bypassed by SQL injection. An **Abstract Syntax Tree (AST)** converts SQL text into a structural parse tree. Using `sqlglot`, we inspect the root operator to ensure it is strictly `exp.Select` and guarantee that destructive statements (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `CREATE`, `TRUNCATE`) are structurally impossible to execute.

### 4. Why Bounded Repair Loops ($\le 3$ Retries)?
Agents can get stuck in infinite retry loops if SQL generation repeatedly fails. A **Bounded Repair Loop** allows the LLM to analyze the execution/validation error, adjust its SQL query or filtering logic, increment a `retry_count`, and retry up to 3 times before cleanly failing with an informative error message.

### 5. Why LLM Reasoning + Deterministic Execution?
LLMs are prone to arithmetic halluncinations (e.g., miscalculating standard deviations or percentage differences).
- **LLM Responsibility**: Understanding human intent, structuring SQL queries, planning analysis, and translating analytical findings into executive English.
- **Deterministic Responsibility**: Executing SQL queries, running Pandas computations (accurate math), and rendering charts.

### 6. Business Glossary RAG (ChromaDB)
Users often use business domain terms like *"Active Customers"* or *"High Value Orders"*. The agent uses ChromaDB vector store to fetch relevant domain definitions (e.g., `"Active Customer" -> status = 'Active' AND last_login_days <= 30`) and feed them as context to the SQL generator.

---

## User Review Required

> [!IMPORTANT]
> - **Zero Execution Policy**: Per instructions, no code changes will be committed until you explicitly review the plan, ask any learning questions, and say "Proceed".
> - **Dependency Additions**: We will add `langgraph>=0.2.0`, `sqlglot>=20.0.0`, `langchain-groq>=0.2.0`, `pydantic>=2.0.0`, `chromadb>=0.4.0` to `backend/requirements.txt`.
> - **Architecture Shift**: The current `/query` endpoint in `backend/app/main.py` will route queries through `agent_graph.invoke()`.

---

## Proposed Changes

### Component 1: Core Dependencies & Infrastructure

#### [MODIFY] [requirements.txt](file:///c:/Users/OM/Desktop/data_analyst_agent/backend/requirements.txt)
- Add `langgraph>=0.2.0`, `sqlglot>=20.0.0`, `langchain-groq>=0.2.0`, `pydantic>=2.0.0`, `chromadb>=0.4.0`.

---

### Component 2: Agent Architecture (`backend/app/agent/`)

#### [NEW] [state.py](file:///c:/Users/OM/Desktop/data_analyst_agent/backend/app/agent/state.py)
- Define `AgentState(TypedDict)` containing `question`, `resolved_question`, `intent`, `plan`, `schema`, `glossary_context`, `generated_sql`, `sql_result`, `validation_status`, `validation_reason`, `retry_count`, `analysis_result`, `chart_config`, `final_response`.

#### [NEW] [tools.py](file:///c:/Users/OM/Desktop/data_analyst_agent/backend/app/agent/tools.py)
- `@tool inspect_schema()`: Extracts table schema, columns, data types, and sample distinct values.
- `@tool execute_sql_query()`: Runs AST security check and executes SQLite queries safely.

#### [NEW] [nodes.py](file:///c:/Users/OM/Desktop/data_analyst_agent/backend/app/agent/nodes.py)
- `analyzer_planner_node`: Combines intent understanding and multi-step plan generation into one node for lower latency.
- `sql_generator_node`: Generates SQLite SQL using schema & glossary RAG context.
- `validator_node`: Evaluates Layer 1 (execution), Layer 2 (non-empty & data types), and Layer 3 (dimension/filters).
- `repair_node`: Formulates repair prompt when validation fails and increments `retry_count`.
- `pandas_insights_node`: Wraps existing `insights_engine.py` functions to compute deterministic summary, percent diffs, top/bottom, anomalies.
- `chart_mapping_node`: Deterministic mapping to Plotly chart types (line, bar, kpi, table).
- `insight_explainer_node`: Generates executive summary strictly grounded in Pandas outputs.

#### [NEW] [graph.py](file:///c:/Users/OM/Desktop/data_analyst_agent/backend/app/agent/graph.py)
- Constructs and compiles the `StateGraph`. Defines conditional routing: `should_repair` (if validation fails & `retry_count < 3` $\rightarrow$ `repair_node`, else $\rightarrow$ `pandas_insights_node`).

---

### Component 3: Security & Services (`backend/app/core/` & `backend/app/services/`)

#### [NEW] [sql_validator.py](file:///c:/Users/OM/Desktop/data_analyst_agent/backend/app/core/sql_validator.py)
- Implement `validate_sql_security(sql: str) -> tuple[bool, str]` using `sqlglot`.
- Verify AST root is `exp.Select` and check for forbidden nodes (`exp.Drop`, `exp.Delete`, `exp.Update`, `exp.Insert`, `exp.Alter`, `exp.Create`, `exp.Truncate`).

#### [NEW] [glossary.py](file:///c:/Users/OM/Desktop/data_analyst_agent/backend/app/services/glossary.py)
- Implement ChromaDB vector store service for business metrics glossary retrieval.

#### [MODIFY] [main.py](file:///c:/Users/OM/Desktop/data_analyst_agent/backend/app/main.py)
- Integrate `agent_graph` into FastAPI endpoints (`/query` and streaming status).

---

### Component 4: Evaluation Benchmark Suite (`backend/eval/`)

#### [NEW] [eval_suite.py](file:///c:/Users/OM/Desktop/data_analyst_agent/backend/eval/eval_suite.py)
- Benchmark test runner with 25 test questions across 7 categories:
  1. Aggregations (SUM, AVG, COUNT)
  2. Filtering & Conditions
  3. Grouping & Breakdowns
  4. Time-based Trend Analysis
  5. Ranking & Top-N
  6. Business Glossary Metrics
  7. Malicious Queries (e.g. `DROP TABLE sales;`)
- Outputs metrics: SQL Execution Accuracy %, Task Completion Accuracy %, Retry Rate, Average Latency (seconds).

---

### Component 5: Frontend UI (`frontend/`)

#### [MODIFY] [app.py](file:///c:/Users/OM/Desktop/data_analyst_agent/frontend/app.py)
- Add real-time event status visualization via `st.status()` tracking steps:
  - Resolving Intent & Planning
  - Searching Business Glossary (if needed)
  - Inspecting Schema
  - Validating SQL Safety (AST)
  - Executing Query
  - Computing Pandas Analytics
  - Explaining Executive Insights

---

## Verification Plan

### Automated Tests
1. Run evaluation suite:
   ```powershell
   python backend/eval/eval_suite.py
   ```
2. Verify security enforcement against SQL injections:
   ```powershell
   python -c "from backend.app.core.sql_validator import validate_sql_security; print(validate_sql_security('DROP TABLE sales;'))"
   ```

### Manual Verification
1. Test Streamlit frontend UI event status accordion.
2. Verify end-to-end execution on sample dataset (e.g. `emplyee_attrition.csv`).
