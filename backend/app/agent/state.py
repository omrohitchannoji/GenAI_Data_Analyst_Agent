from typing import TypedDict, List, Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field

# ============================================================
# 1. ENUMS & DATA MODELS
# ============================================================

class TerminalStatus(str, Enum):
    SUCCESS = "success"
    EMPTY = "empty"
    NEEDS_CLARIFICATION = "needs_clarification"
    REJECTED = "rejected"
    FAILED = "failed"

class FactMetric(BaseModel):
    fact_id: str
    metric_name: str
    value: Any
    unit: Optional[str] = None
    scope: Optional[str] = None

class ChartConfig(BaseModel):
    chart_type: str  # "bar", "line", "kpi", "table"
    x: Optional[str] = None
    y: Optional[str] = None
    title: Optional[str] = None
    details: Optional[Dict[str, Any]] = Field(default_factory=dict)

class QueryResult(BaseModel):
    columns: List[str] = Field(default_factory=list)
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    is_truncated: bool = False

# ============================================================
# 2. REQUEST & RESPONSE SCHEMAS
# ============================================================

class QueryRequest(BaseModel):
    question: str
    dataset_id: str = "default"
    session_id: str = "default"

class QueryResponse(BaseModel):
    request_id: str
    session_id: str
    dataset_id: str
    status: TerminalStatus
    resolved_question: str
    sql: Optional[str] = None
    result: Optional[QueryResult] = None
    metrics: List[FactMetric] = Field(default_factory=list)
    chart: Optional[ChartConfig] = None
    answer: Optional[str] = None
    clarification_question: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class UploadResponse(BaseModel):
    dataset_id: str
    filename: str
    row_count: int
    columns: List[str]
    column_types: Dict[str, List[str]]
    preview: List[Dict[str, Any]]

# ============================================================
# 3. STRUCTURED MODEL OUTPUTS
# ============================================================

class IntentPlanOutput(BaseModel):
    resolved_question: str
    intent_type: str = Field(description="aggregation, trend, ranking, comparison, or unsupported")
    requires_glossary: bool = False
    is_ambiguous: bool = False
    clarification_question: Optional[str] = None
    metric: Optional[str] = None
    aggregation: Optional[str] = None
    group_by: Optional[str] = None
    filters: List[str] = Field(default_factory=list)
    order_by: Optional[str] = None
    limit: Optional[int] = None

class SQLGenerationOutput(BaseModel):
    sql: str = Field(description="Strict SQLite SELECT query without markdown formatting")
    explanation: Optional[str] = None

class RepairPlanOutput(BaseModel):
    diagnosed_error: str
    repair_strategy: str
    repaired_sql: str

class InsightNarrativeOutput(BaseModel):
    executive_summary: str
    key_observations: List[str]
    recommendation: str
    fact_ids_used: List[str] = Field(default_factory=list)

# ============================================================
# 4. TYPED AGENT STATE (LangGraph State)
# ============================================================

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
    error: Optional[str]
    terminal_status: str   # "success", "empty", "needs_clarification", "rejected", "failed"
    
    # Metadata & Budgets
    start_time: float
    model_calls: int
    execution_events: List[Dict[str, Any]]
