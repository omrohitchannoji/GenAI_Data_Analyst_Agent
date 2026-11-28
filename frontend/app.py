import os
import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# ============================================================
# CONFIG
# ============================================================
try:
    BACKEND_URL = os.environ.get("BACKEND_URL") or st.secrets.get("BACKEND_URL", "http://localhost:8000")
except Exception:
    BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
BACKEND_URL = str(BACKEND_URL).rstrip("/")


def format_optional_metric(value, spec: str, prefix: str = "", suffix: str = "") -> str:
    """Format available numeric telemetry without treating None as zero."""
    if value is None:
        return "Unavailable"
    try:
        return f"{prefix}{format(value, spec)}{suffix}"
    except (TypeError, ValueError):
        return "Unavailable"


st.set_page_config(
    page_title="Agentic AI Data Analyst",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# STYLES
# ============================================================
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    :root {
        --da-bg: #070a0e;
        --da-glow: radial-gradient(circle at 50% -15%, rgba(16, 185, 129, 0.14), transparent 55%);
        --da-surface: #0f141c;
        --da-surface-2: #151c27;
        --da-surface-hover: #1b2432;
        --da-border: rgba(255, 255, 255, 0.08);
        --da-border-accent: rgba(16, 185, 129, 0.38);
        --da-emerald: #10b981;
        --da-emerald-light: #34d399;
        --da-emerald-dark: #059669;
        --da-cyan: #06b6d4;
        --da-amber: #fbbf24;
        --da-rose: #f87171;
        --da-text: #f1f5f9;
        --da-text-secondary: #cbd5e1;
        --da-text-muted: #8896ab;
        --da-font: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
        --da-mono: 'JetBrains Mono', monospace;
    }

    html, body, [class*="css"] {
        font-family: var(--da-font);
    }

    code, pre {
        font-family: var(--da-mono) !important;
    }

    .stApp {
        background-color: var(--da-bg);
        background-image: var(--da-glow);
        background-attachment: fixed;
        color: var(--da-text);
    }

    #MainMenu, footer, header { visibility: hidden; }

    /* ---- Scrollbar ---- */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.12); border-radius: 999px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.24); }

    /* ---- Sidebar ---- */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0b0f16 0%, #0f141c 100%);
        border-right: 1px solid var(--da-border);
    }

    .brand-box {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px;
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid var(--da-border);
        border-radius: 12px;
        margin-bottom: 16px;
    }

    .brand-logo {
        width: 38px;
        height: 38px;
        border-radius: 10px;
        background: linear-gradient(135deg, var(--da-emerald) 0%, var(--da-cyan) 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.2rem;
        box-shadow: 0 4px 16px rgba(16, 185, 129, 0.3);
    }

    .brand-name {
        font-size: 1.05rem;
        font-weight: 800;
        color: var(--da-text);
        margin: 0;
        letter-spacing: -0.02em;
    }

    .brand-tag {
        font-size: 0.73rem;
        color: var(--da-text-muted);
        margin: 2px 0 0 0;
    }

    .side-label {
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--da-text-muted);
        margin: 14px 0 6px 2px;
    }

    .context-card {
        background: var(--da-surface-2);
        border: 1px solid var(--da-border);
        border-radius: 10px;
        padding: 10px 12px;
        margin-top: 10px;
        font-size: 0.77rem;
    }
    .context-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 5px;
    }
    .context-row:last-child { margin-bottom: 0; }
    .context-key { color: var(--da-text-muted); }
    .context-val {
        font-family: var(--da-mono);
        color: var(--da-emerald-light);
        font-weight: 600;
        font-size: 0.73rem;
    }

    /* ---- Main Container ---- */
    .main .block-container {
        max-width: 1060px;
        padding-top: 1.6rem;
        padding-bottom: 4rem;
    }

    /* ---- Hero Header ---- */
    .analyst-hero {
        background: linear-gradient(135deg, rgba(21, 28, 39, 0.92) 0%, rgba(15, 20, 28, 0.96) 100%);
        border: 1px solid var(--da-border);
        border-radius: 18px;
        padding: 24px 28px;
        margin-bottom: 20px;
        position: relative;
        overflow: hidden;
    }

    .analyst-hero::before {
        content: "";
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, transparent, var(--da-emerald), var(--da-cyan), transparent);
    }

    .hero-heading {
        font-size: 1.7rem;
        font-weight: 800;
        letter-spacing: -0.025em;
        color: var(--da-text);
        margin: 0 0 6px 0;
    }

    .hero-desc {
        color: var(--da-text-muted);
        font-size: 0.92rem;
        margin: 0;
    }

    /* ---- Tabs Styling ---- */
    button[data-baseweb="tab"] {
        font-family: var(--da-font) !important;
        font-weight: 600 !important;
        font-size: 0.92rem !important;
        padding: 10px 18px !important;
        color: var(--da-text-muted) !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: var(--da-emerald-light) !important;
        border-bottom-color: var(--da-emerald) !important;
    }

    /* ---- File Uploader Dropzone ---- */
    section[data-testid="stFileUploaderDropzone"],
    div[data-testid="stFileUploaderDropzone"] {
        background-color: var(--da-surface) !important;
        border: 1px dashed var(--da-border-accent) !important;
        border-radius: 14px !important;
        padding: 18px 20px !important;
        color: var(--da-text-secondary) !important;
        transition: border-color 0.18s ease, background-color 0.18s ease;
    }

    section[data-testid="stFileUploaderDropzone"]:hover,
    div[data-testid="stFileUploaderDropzone"]:hover {
        background-color: var(--da-surface-2) !important;
        border-color: var(--da-emerald) !important;
    }

    section[data-testid="stFileUploaderDropzone"] button,
    div[data-testid="stFileUploaderDropzone"] button {
        background: var(--da-surface-2) !important;
        color: var(--da-emerald-light) !important;
        border: 1px solid var(--da-border-accent) !important;
        box-shadow: none !important;
    }

    /* ---- Cards & Containers ---- */
    .panel-title {
        font-size: 0.95rem;
        font-weight: 700;
        color: var(--da-text);
        margin: 0 0 12px 0;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* ---- KPI Metric Cards ---- */
    .metric-card {
        padding: 18px 16px;
        border-radius: 14px;
        background: linear-gradient(180deg, var(--da-surface-2) 0%, var(--da-surface) 100%);
        border: 1px solid var(--da-border);
        text-align: left;
        transition: border-color 0.18s ease, transform 0.18s ease;
        margin-bottom: 10px;
    }
    .metric-card:hover {
        border-color: var(--da-border-accent);
        transform: translateY(-2px);
    }
    .metric-label {
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--da-text-muted);
    }
    .metric-value {
        font-family: var(--da-mono);
        font-size: 1.65rem;
        font-weight: 800;
        color: var(--da-emerald-light);
        margin-top: 6px;
    }

    /* ---- Executive Narrative Box ---- */
    .narrative-card {
        background: linear-gradient(180deg, rgba(21, 28, 39, 0.85) 0%, rgba(15, 20, 28, 0.95) 100%);
        border: 1px solid var(--da-border);
        border-left: 3px solid var(--da-emerald);
        border-radius: 12px;
        padding: 18px 22px;
        margin: 12px 0;
        line-height: 1.6;
    }

    /* ---- Buttons ---- */
    .stButton > button {
        background: linear-gradient(135deg, var(--da-emerald-dark) 0%, var(--da-emerald) 100%);
        color: #ffffff;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 9px 18px;
        font-weight: 600;
        font-size: 0.86rem;
        transition: all 0.16s ease;
        box-shadow: 0 2px 12px rgba(16, 185, 129, 0.25);
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        filter: brightness(1.07);
        box-shadow: 0 6px 18px rgba(16, 185, 129, 0.35);
    }
    .stButton > button[kind="secondary"] {
        background: var(--da-surface-2);
        border: 1px solid var(--da-border);
        color: var(--da-text-secondary);
        box-shadow: none;
    }
    .stButton > button[kind="secondary"]:hover {
        background: var(--da-surface-hover);
        border-color: var(--da-border-accent);
        color: #ffffff;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Session initialization
if "session_id" not in st.session_state:
    st.session_state["session_id"] = "session_default"
if "dataset_id" not in st.session_state:
    st.session_state["dataset_id"] = "default"
if "question_input" not in st.session_state:
    st.session_state["question_input"] = ""


def get_auth_headers():
    if "bearer_token" in st.session_state:
        return {"Authorization": f"Bearer {st.session_state['bearer_token']}"}
    return {}


# ============================================================
# SIDEBAR — IDENTITY & DEMO/AUTH TOGGLE
# ============================================================
with st.sidebar:
    st.markdown(
        """
        <div class="brand-box">
            <div class="brand-logo">📊</div>
            <div>
                <p class="brand-name">DataAgent</p>
                <p class="brand-tag">LangGraph Text-to-SQL Engine</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="side-label">Identity & Isolation</div>', unsafe_allow_html=True)
    auth_mode = st.radio(
        "Operating Mode",
        ["Shared Demo Mode", "Authenticated Mode"],
        help="Shared Demo Mode runs unauthenticated as demo_user without multi-user isolation. Authenticated Mode derives verified tokens server-side.",
        label_visibility="collapsed",
    )

    if auth_mode == "Authenticated Mode":
        st.markdown('<div class="side-label">Server-Verified Login</div>', unsafe_allow_html=True)
        uname = st.text_input("Username", value=st.session_state.get("username", ""))
        pwd = st.text_input("Password", type="password", value=st.session_state.get("password", ""))
        if st.button("🔑 Authenticate", use_container_width=True):
            try:
                auth_resp = requests.post(
                    f"{BACKEND_URL}/auth/token",
                    json={"username": uname, "password": pwd},
                    timeout=10,
                )
                if auth_resp.status_code == 200:
                    token_data = auth_resp.json()
                    st.session_state["bearer_token"] = token_data["access_token"]
                    st.session_state["principal_id"] = token_data["principal_id"]
                    st.session_state["role"] = token_data["role"]
                    st.toast(f"Authenticated as {token_data['principal_id']}", icon="🔐")
                else:
                    st.error(f"Authentication failed: {auth_resp.text}")
                    st.session_state.pop("bearer_token", None)
            except Exception as e:
                st.error(f"Cannot connect to auth service: {str(e)}")

        if "bearer_token" in st.session_state:
            st.success(
                f"Principal: **{st.session_state.get('principal_id')}** [{st.session_state.get('role')}]"
            )
            if st.button("Log Out", type="secondary", use_container_width=True):
                st.session_state.pop("bearer_token", None)
                st.session_state.pop("principal_id", None)
                st.session_state.pop("role", None)
                st.rerun()
    else:
        st.caption("ℹ️ Running in unisolated `demo_user` namespace.")
        st.session_state.pop("bearer_token", None)

    st.markdown('<div class="side-label">Active Workspace State</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="context-card">
            <div class="context-row">
                <span class="context-key">Dataset ID</span>
                <span class="context-val">{st.session_state.get("dataset_id", "default")}</span>
            </div>
            <div class="context-row">
                <span class="context-key">Session ID</span>
                <span class="context-val">{st.session_state.get("session_id", "session_default")}</span>
            </div>
            <div class="context-row">
                <span class="context-key">SQL Engine</span>
                <span class="context-val">SQLite Read-Only</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ============================================================
# HEADER
# ============================================================
st.markdown(
    """
    <div class="analyst-hero">
        <h1 class="hero-heading">Agentic AI Data Analyst</h1>
        <p class="hero-desc">
            Upload structured CSV datasets and query them in natural language.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# TABS
# ============================================================
tab1, tab2, tab3 = st.tabs(
    [
        "📁  Upload & Schema",
        "💬  Ask Questions (Agent)",
        "📈  Analysis Dashboard",
    ]
)

# ============================================================
# TAB 1 — UPLOAD DATASET
# ============================================================
with tab1:
    st.markdown(
        '<div class="panel-title">📁 Register CSV Dataset (Max 10 MiB)</div>',
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader("Upload CSV file", type=["csv"], label_visibility="collapsed")

    if uploaded_file:
        with st.spinner("Uploading, profiling schema & registering dataset..."):
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/upload_csv",
                    files={"file": (uploaded_file.name, uploaded_file.getvalue(), "text/csv")},
                    headers=get_auth_headers(),
                    timeout=120,
                )
            except Exception as e:
                st.error(f"Cannot connect to backend: {str(e)}")
                st.stop()

        if resp.status_code != 200:
            st.error(f"Upload failed: HTTP {resp.status_code}")
            st.stop()

        data = resp.json()
        if "error" in data:
            st.error(data["error"])
            st.stop()

        st.session_state["dataset_id"] = data.get("dataset_id", "default")
        st.session_state["uploaded"] = True

        col_types = data.get("column_types", {})
        preview_rows = data.get("preview", [])

        if isinstance(col_types, dict) and col_types and isinstance(next(iter(col_types.values())), list):
            total_cols = sum(len(v) for v in col_types.values())
        else:
            total_cols = len(col_types) if isinstance(col_types, dict) else len(pd.DataFrame(preview_rows).columns)

        st.success(
            f"✅ Registered **{data.get('filename')}** · Dataset ID: `{st.session_state['dataset_id']}` · {total_cols} columns detected"
        )

        c1, c2 = st.columns([1.4, 1])
        with c1:
            st.markdown('<div class="panel-title">🔍 Data Preview (First 20 Rows)</div>', unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)

        with c2:
            st.markdown('<div class="panel-title">🧬 Detected Schema</div>', unsafe_allow_html=True)
            if isinstance(col_types, dict) and col_types:
                schema_rows = []
                first_val = next(iter(col_types.values()))

                if isinstance(first_val, list):
                    for dtype_group, cols in col_types.items():
                        for col_name in cols:
                            schema_rows.append(
                                {
                                    "Column": col_name,
                                    "Detected Type": dtype_group.upper(),
                                }
                            )
                else:
                    for col_name, dtype_val in col_types.items():
                        schema_rows.append(
                            {
                                "Column": col_name,
                                "Detected Type": str(dtype_val).upper(),
                            }
                        )

                st.dataframe(
                    pd.DataFrame(schema_rows),
                    use_container_width=True,
                    hide_index=True,
                    height=360,
                )
            else:
                st.caption("No column type metadata returned.")

# ============================================================
# TAB 2 — ASK QUESTIONS
# ============================================================
with tab2:
    st.markdown('<div class="panel-title">💬 Natural Language Analytical Query</div>', unsafe_allow_html=True)

    sample_prompts = [
        "Average MonthlyCharges by Contract",
        "Count of High Value Customers by Tenure Group",
        "Top 5 segments by total revenue contribution",
    ]
    st.caption("Quick prompts:")
    sp_cols = st.columns(len(sample_prompts))
    for col, sp in zip(sp_cols, sample_prompts):
        if col.button(sp, type="secondary", use_container_width=True, key=f"sp_{sp}"):
            st.session_state["question_input"] = sp

    question = st.text_input(
        "Enter your analytical question",
        key="question_input",
        placeholder="e.g., Average MonthlyCharges by Contract, or Count of High Value Customers",
        label_visibility="collapsed",
    )

    col_btn1, col_btn2, _ = st.columns([1.3, 1.7, 3])
    with col_btn1:
        run_btn = st.button("🚀 Run Analysis", use_container_width=True)
    with col_btn2:
        if st.button("🔄 Reset Session Context", type="secondary", use_container_width=True):
            st.session_state["session_id"] = f"session_{os.urandom(4).hex()}"
            st.toast("Session reset! Clean context initiated.", icon="🔄")

    if run_btn:
        if not question.strip():
            st.warning("Please enter an analytical question.")
            st.stop()

        payload = {
            "question": question,
            "dataset_id": st.session_state.get("dataset_id", "default"),
            "session_id": st.session_state.get("session_id", "session_default"),
        }

        with st.status("Agentic AI Workflow in Progress...", expanded=True) as status_box:
            st.write("🔍 Inspecting dataset scope & schema...")

            try:
                resp = requests.post(
                    f"{BACKEND_URL}/query",
                    json=payload,
                    headers=get_auth_headers(),
                    timeout=60,
                )
            except Exception as e:
                status_box.update(label="Connection Failed", state="error")
                st.error(f"Backend error: {str(e)}")
                st.stop()

            if resp.status_code != 200:
                status_box.update(label="Query Failed", state="error")
                st.error(f"Error {resp.status_code}: {resp.text}")
                st.stop()

            res_data = resp.json()

            st.write("✓ Identity & principal scope validated")
            st.write("✓ Intent planned & business glossary definitions retrieved")
            st.write("✓ SQL generated & AST safety verified (sqlglot)")
            st.write("✓ Read-only query executed with timeout protection")
            st.write("✓ Deterministic analytics computed (Pandas)")
            st.write("✓ Grounded narrative summary generated")

            terminal_status = res_data.get("status")
            if terminal_status == "success":
                status_box.update(label="Analysis Completed Successfully!", state="complete", expanded=False)
            elif terminal_status == "needs_clarification":
                status_box.update(label="Clarification Needed", state="complete", expanded=False)
            elif terminal_status == "rejected":
                status_box.update(label="Query Policy Rejection", state="error", expanded=False)
            elif terminal_status == "empty":
                status_box.update(label="Query Returned Empty Result", state="complete", expanded=False)
            else:
                status_box.update(label="Analysis Failed", state="error", expanded=False)

        st.session_state["query_response"] = res_data

        # ============================================================
        # RENDER OUTCOMES
        # ============================================================
        status = res_data.get("status")

        if status == "needs_clarification":
            st.warning(
                f"⚠️ **Clarification Required:** {res_data.get('clarification_question') or res_data.get('answer')}"
            )
        elif status == "rejected":
            st.error(f"🛑 **Query Rejected:** {res_data.get('error') or res_data.get('answer')}")
        elif status == "empty":
            st.info(
                "ℹ️ **No Records Found:** The query executed successfully, but no records matched your filter criteria. (Filters were not relaxed)."
            )
            if res_data.get("sql"):
                st.caption("Executed SQL:")
                st.code(res_data["sql"], language="sql")
        elif status == "failed":
            st.error(f"❌ **Analysis Failed:** {res_data.get('error') or 'Exhausted retry budget.'}")
        elif status == "success":
            st.success("✅ Analysis Succeeded!")

            result_obj = res_data.get("result", {})
            warnings_list = res_data.get("warnings", [])
            if result_obj and result_obj.get("is_truncated"):
                st.warning(
                    "⚠️ **Result Truncated:** The query returned more rows than the 1,000 display cap. The data and charts below reflect the top 1,000 rows."
                )
            for w in warnings_list:
                st.info(f"ℹ️ {w}")

            st.markdown("### 🤖 Executive Narrative")
            st.markdown(
                f'<div class="narrative-card">{res_data.get("answer", "")}</div>',
                unsafe_allow_html=True,
            )

            res_col1, res_col2 = st.columns([1.25, 1])
            rows = result_obj.get("rows", []) if result_obj else []
            with res_col1:
                if rows:
                    st.markdown("**📊 Query Results Table**")
                    df_res = pd.DataFrame(rows)
                    st.dataframe(df_res, use_container_width=True, hide_index=True)
                    st.session_state["analysis_df"] = df_res
            with res_col2:
                if res_data.get("sql"):
                    st.markdown("**🛡️ Validated SQLite Query (AST Checked)**")
                    st.code(res_data["sql"], language="sql")

            # Per-Node Tracing, Latency & Pricing Table Cost Breakdown
            telemetry = res_data.get("metadata", {}).get("telemetry")
            if telemetry:
                with st.expander("⏱️ Per-Node Tracing, Latency & Cost Breakdown", expanded=False):
                    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
                    with m_col1:
                        st.metric(
                            "Total Latency",
                            format_optional_metric(telemetry.get("total_latency_seconds"), ".2f", suffix="s"),
                        )
                    with m_col2:
                        st.metric(
                            "Total Tokens",
                            format_optional_metric(telemetry.get("total_tokens"), ",.0f"),
                        )
                    with m_col3:
                        st.metric(
                            "Inference Cost",
                            format_optional_metric(telemetry.get("total_cost_usd"), ".6f", prefix="$"),
                        )
                    with m_col4:
                        st.metric("Repair Retries", telemetry.get("repair_count", 0))

                    spans = telemetry.get("spans", [])
                    if spans:
                        span_rows = []
                        for s in spans:
                            span_rows.append(
                                {
                                    "Node": s.get("node_name"),
                                    "Status": s.get("status"),
                                    "Latency (ms)": round(s["latency_seconds"] * 1000, 1)
                                    if s.get("latency_seconds") is not None
                                    else "Unavailable",
                                    "Prompt Tok": s.get("prompt_tokens")
                                    if s.get("prompt_tokens") is not None
                                    else "Unavailable",
                                    "Comp Tok": s.get("completion_tokens")
                                    if s.get("completion_tokens") is not None
                                    else "Unavailable",
                                    "Cost (USD)": format_optional_metric(
                                        s.get("cost_usd"), ".6f", prefix="$"
                                    ),
                                }
                            )
                        st.dataframe(pd.DataFrame(span_rows), use_container_width=True, hide_index=True)
                        st.caption(
                            f"Model: {telemetry.get('model_name')}. Cost is shown only when usage and cached-token data are available; query text and database rows are not sent in telemetry."
                        )

            st.info("👉 Switch to the **Analysis Dashboard** tab for interactive visualizations and verified KPI cards.")

# ============================================================
# TAB 3 — DASHBOARD
# ============================================================
with tab3:
    if "query_response" not in st.session_state or st.session_state["query_response"].get("status") != "success":
        st.info("Run a successful analysis in the **Ask Questions (Agent)** tab first to populate this dashboard.")
        st.stop()

    res_data = st.session_state["query_response"]
    df = st.session_state.get("analysis_df", pd.DataFrame())
    chart_cfg = res_data.get("chart") or {}
    metrics = res_data.get("metrics", [])

    st.markdown('<div class="panel-title">📌 Verified Metrics (Pandas Grounded)</div>', unsafe_allow_html=True)
    if metrics:
        cols = st.columns(min(len(metrics), 4))
        for idx, m in enumerate(metrics):
            with cols[idx % len(cols)]:
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <div class="metric-label">{m.get('metric_name')}</div>
                        <div class="metric-value">{m.get('value')}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.caption("No scalar metrics returned for this query.")

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="panel-title">📈 Interactive Visualization</div>', unsafe_allow_html=True)
    chart_type = chart_cfg.get("chart_type", "table")
    x_col = chart_cfg.get("x")
    y_col = chart_cfg.get("y")

    palette = ["#10b981", "#06b6d4", "#34d399", "#38bdf8", "#818cf8", "#fbbf24"]
    chart_layout = dict(
        template="plotly_dark",
        paper_bgcolor="rgba(15, 20, 28, 0.85)",
        plot_bgcolor="rgba(15, 20, 28, 0.4)",
        font=dict(family="Plus Jakarta Sans, sans-serif", color="#f1f5f9"),
        margin=dict(l=24, r=24, t=48, b=24),
        xaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
    )

    if not df.empty and x_col in df.columns and y_col in df.columns:
        if chart_type == "bar":
            fig = px.bar(
                df,
                x=x_col,
                y=y_col,
                color=x_col,
                color_discrete_sequence=palette,
                title=chart_cfg.get("title", ""),
            )
            fig.update_layout(**chart_layout, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        elif chart_type == "line":
            fig = px.line(
                df,
                x=x_col,
                y=y_col,
                markers=True,
                color_discrete_sequence=palette,
                title=chart_cfg.get("title", ""),
            )
            fig.update_traces(line=dict(width=3))
            fig.update_layout(**chart_layout)
            st.plotly_chart(fig, use_container_width=True)
        elif chart_type == "kpi":
            st.metric(label=y_col, value=df[y_col].iloc[0])
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
    elif not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="panel-title">🤖 Executive Summary & Recommendations</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="narrative-card">{res_data.get("answer", "")}</div>',
        unsafe_allow_html=True,
    )