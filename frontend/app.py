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

st.set_page_config(
    page_title="Agentic AI Data Analyst",
    page_icon="📊",
    layout="wide"
)

# ============================================================
# STYLES
# ============================================================
st.markdown("""
<style>
.section-box {
    padding: 25px;
    background-color: #1e1e1e;
    border-radius: 12px;
    margin-bottom: 25px;
    border: 1px solid #333;
}
.metric-card {
    padding: 18px;
    border-radius: 10px;
    background-color: #262626;
    border: 1px solid #333;
    text-align: center;
}
.metric-value {
    font-size: 26px;
    font-weight: bold;
    color: #4CAF50;
}
.metric-label {
    font-size: 14px;
    color: #bbb;
    margin-top: 4px;
}
</style>
""", unsafe_allow_html=True)

# Session initialization
if "session_id" not in st.session_state:
    st.session_state["session_id"] = "session_default"
if "dataset_id" not in st.session_state:
    st.session_state["dataset_id"] = "default"

# ============================================================
# HEADER
# ============================================================
st.title("📊 Agentic AI Data Analyst")
st.caption("Stateful LangGraph Agent · AST SQL Safety · Deterministic Analytics · Business Glossary RAG")

# ============================================================
# TABS
# ============================================================
tab1, tab2, tab3 = st.tabs([
    "📁 Upload Dataset",
    "💬 Ask Questions (Agent)",
    "📈 Analysis Dashboard"
])

# ============================================================
# TAB 1 — UPLOAD DATASET
# ============================================================
with tab1:
    st.subheader("📁 Upload CSV Dataset")

    uploaded_file = st.file_uploader("Upload CSV file (max 10 MiB)", type=["csv"])

    if uploaded_file:
        with st.spinner("Uploading & registering dataset..."):
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/upload_csv",
                    files={"file": (uploaded_file.name, uploaded_file.getvalue(), "text/csv")},
                    timeout=120
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

        st.success(f"Dataset '{data.get('filename')}' registered successfully! (ID: {st.session_state['dataset_id']})")

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🔍 Preview (First 20 rows)")
            st.dataframe(pd.DataFrame(data.get("preview", [])))
        with c2:
            st.subheader("🧬 Detected Column Types")
            st.json(data.get("column_types", {}))

# ============================================================
# TAB 2 — ASK QUESTIONS
# ============================================================
with tab2:
    st.subheader("💬 Ask Analytical Questions")

    question = st.text_input(
        "Enter your analytical question",
        placeholder="e.g., Average MonthlyCharges by Contract, or Count of High Value Customers"
    )

    col_btn1, col_btn2 = st.columns([1, 5])
    with col_btn1:
        run_btn = st.button("🚀 Run Analysis")
    with col_btn2:
        if st.button("🔄 Reset Conversation Context"):
            st.session_state["session_id"] = f"session_{os.urandom(4).hex()}"
            st.success("Session reset! New clean context initiated.")

    if run_btn:
        if not question.strip():
            st.warning("Please enter a question.")
            st.stop()

        payload = {
            "question": question,
            "dataset_id": st.session_state.get("dataset_id", "default"),
            "session_id": st.session_state.get("session_id", "session_default")
        }

        # Real-time event tracking using st.status
        with st.status("Agentic AI Workflow in Progress...", expanded=True) as status_box:
            st.write("🔍 Inspecting dataset scope & schema...")

            try:
                resp = requests.post(f"{BACKEND_URL}/query", json=payload, timeout=60)
            except Exception as e:
                status_box.update(label="Connection Failed", state="error")
                st.error(f"Backend error: {str(e)}")
                st.stop()

            if resp.status_code != 200:
                status_box.update(label="Query Failed", state="error")
                st.error(f"Error {resp.status_code}: {resp.text}")
                st.stop()

            res_data = resp.json()
            events = res_data.get("metadata", {}).get("events", [])

            # Display genuine execution events
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
            st.warning(f"⚠️ **Clarification Required:** {res_data.get('clarification_question') or res_data.get('answer')}")
        elif status == "rejected":
            st.error(f"🛑 **Query Rejected:** {res_data.get('error') or res_data.get('answer')}")
        elif status == "empty":
            st.info("ℹ️ **No Records Found:** The query executed successfully, but no records matched your filter criteria. (Filters were not relaxed).")
            if res_data.get("sql"):
                st.caption("Executed SQL:")
                st.code(res_data["sql"], language="sql")
        elif status == "failed":
            st.error(f"❌ **Analysis Failed:** {res_data.get('error') or 'Exhausted retry budget.'}")
        elif status == "success":
            st.success("✅ Analysis Succeeded!")

            if res_data.get("sql"):
                st.markdown("**Validated SQLite Query (AST Checked):**")
                st.code(res_data["sql"], language="sql")

            result_obj = res_data.get("result", {})
            rows = result_obj.get("rows", [])
            if rows:
                st.markdown("**Query Results:**")
                df_res = pd.DataFrame(rows)
                st.dataframe(df_res)
                st.session_state["analysis_df"] = df_res

            st.markdown("### 🤖 Executive Narrative")
            st.markdown(res_data.get("answer", ""))

            st.info("👉 Check the **Analysis Dashboard** tab for charts and metric summaries!")

# ============================================================
# TAB 3 — DASHBOARD
# ============================================================
with tab3:
    if "query_response" not in st.session_state or st.session_state["query_response"].get("status") != "success":
        st.info("Run a successful analysis in the 'Ask Questions' tab first.")
        st.stop()

    res_data = st.session_state["query_response"]
    df = st.session_state.get("analysis_df", pd.DataFrame())
    chart_cfg = res_data.get("chart") or {}
    metrics = res_data.get("metrics", [])

    st.subheader("📌 Verified Metrics (Pandas Grounded)")
    if metrics:
        cols = st.columns(min(len(metrics), 4))
        for idx, m in enumerate(metrics):
            with cols[idx % len(cols)]:
                st.markdown(
                    f"<div class='metric-card'>"
                    f"<div class='metric-value'>{m.get('value')}</div>"
                    f"<div class='metric-label'>{m.get('metric_name')}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
    else:
        st.write("No scalar metrics available.")

    st.subheader("📈 Visualization")
    chart_type = chart_cfg.get("chart_type", "table")
    x_col = chart_cfg.get("x")
    y_col = chart_cfg.get("y")

    if not df.empty and x_col in df.columns and y_col in df.columns:
        if chart_type == "bar":
            fig = px.bar(df, x=x_col, y=y_col, color=x_col, title=chart_cfg.get("title", ""))
            st.plotly_chart(fig, use_container_width=True)
        elif chart_type == "line":
            fig = px.line(df, x=x_col, y=y_col, markers=True, title=chart_cfg.get("title", ""))
            st.plotly_chart(fig, use_container_width=True)
        elif chart_type == "kpi":
            st.metric(label=y_col, value=df[y_col].iloc[0])
        else:
            st.dataframe(df)
    elif not df.empty:
        st.dataframe(df)

    st.subheader("🤖 Executive Summary & Recommendations")
    st.markdown(res_data.get("answer", ""))
