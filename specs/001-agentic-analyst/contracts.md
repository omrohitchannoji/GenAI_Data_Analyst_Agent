# System Contracts & Data Schemas
**Project:** Agentic AI Data Analyst  
**Version:** 1.0  
**Specification:** specs/001-agentic-analyst/  

---

## 1. Public API Contracts

### 1.1 Ingestion Contract: `POST /upload_csv`
- **Request:** `multipart/form-data` with field `file: UploadFile`.
- **Response:**
```json
{
  "dataset_id": "dataset_20260929_123456",
  "filename": "sales_data.csv",
  "row_count": 150,
  "columns": ["order_id", "order_date", "revenue", "region"],
  "column_types": {
    "numerical_columns": ["revenue", "order_id"],
    "categorical_columns": ["region"],
    "date_columns": ["order_date"]
  },
  "preview": [{"order_id": 1001, "revenue": 120.5}]
}
```

### 1.2 Query Contract: `POST /query`
- **Request:** `application/json`
```json
{
  "question": "Show average revenue by region for 2025",
  "dataset_id": "dataset_20260929_123456",
  "session_id": "session_default"
}
```

- **Response:** `application/json`
```json
{
  "request_id": "req_abc123",
  "session_id": "session_default",
  "dataset_id": "dataset_20260929_123456",
  "status": "success",
  "resolved_question": "Average revenue by region for year 2025",
  "sql": "SELECT region, AVG(revenue) AS avg_revenue FROM data WHERE strftime('%Y', order_date) = '2025' GROUP BY region ORDER BY avg_revenue DESC;",
  "result": {
    "columns": ["region", "avg_revenue"],
    "rows": [
      {"region": "North", "avg_revenue": 542.10},
      {"region": "South", "avg_revenue": 412.30}
    ],
    "row_count": 2,
    "is_truncated": false
  },
  "metrics": [
    {
      "fact_id": "F01",
      "metric_name": "top_group",
      "value": "North (542.10)",
      "unit": "USD",
      "scope": "region"
    }
  ],
  "chart": {
    "chart_type": "bar",
    "x": "region",
    "y": "avg_revenue",
    "title": "Average Revenue by Region"
  },
  "answer": "The North region recorded the highest average revenue at $542.10, outperforming the South region.",
  "clarification_question": null,
  "warnings": [],
  "error": null,
  "metadata": {
    "sql_attempts": 1,
    "model_calls": 2,
    "latency_seconds": 1.84,
    "provider": "groq",
    "model": "openai/gpt-oss-120b"
  }
}
```

---

## 2. Internal Agent State Contract (`AgentState`)

```python
from typing import TypedDict, List, Dict, Any, Optional

class AgentState(TypedDict):
    # Identity & Scope
    request_id: str
    session_id: str
    dataset_id: str
    principal_id: str
    
    # User Inputs & Intent
    question: str
    resolved_question: str
    intent: Dict[str, Any]
    plan: Dict[str, Any]
    prior_context: List[Dict[str, Any]]
    
    # Schema & Domain Retrieval
    schema: Dict[str, Any]
    glossary_context: List[Dict[str, Any]]
    
    # SQL Generation & Validation
    generated_sql: Optional[str]
    sql_result: Optional[List[Dict[str, Any]]]
    sql_columns: Optional[List[str]]
    validation_status: str  # "valid", "invalid", "rejected", "empty"
    validation_error: Optional[str]
    retry_count: int        # Max 2 repairs (3 total SQL attempts)
    
    # Deterministic Analytics & Visuals
    analysis_result: Dict[str, Any]
    metrics: List[Dict[str, Any]]
    chart_config: Optional[Dict[str, Any]]
    
    # Final Narrative & Status
    final_response: str
    clarification_question: Optional[str]
    warnings: List[str]
    error: Optional[Dict[str, str]]
    terminal_status: str   # "success", "empty", "needs_clarification", "rejected", "failed"
    
    # Metadata & Budgets
    start_time: float
    model_calls: int
    execution_events: List[Dict[str, Any]]
```

---

## 3. Tool Contracts

### 3.1 `inspect_schema(dataset_id: str) -> Dict[str, Any]`
- Input: `dataset_id` (server-verified string)
- Output: Dictionary with tables, column names, normalized types (`numeric`, `categorical`, `date`), and sample non-null values.

### 3.2 `execute_sql_query(dataset_id: str, sql: str, timeout_seconds: int = 10) -> Dict[str, Any]`
- Input: `dataset_id`, `sql`, `timeout_seconds`
- Output:
  ```json
  {
    "success": true,
    "columns": ["region", "avg_revenue"],
    "rows": [{"region": "North", "avg_revenue": 542.1}],
    "row_count": 1,
    "is_truncated": false,
    "error": null
  }
  ```

### 3.3 `search_business_glossary(query: str, dataset_id: str, top_k: int = 3) -> List[Dict[str, Any]]`
- Input: `query`, `dataset_id`, `top_k`
- Output: List of approved definitions containing `term_id`, `term_name`, `definition`, and `sql_expression_template`.
