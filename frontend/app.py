import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# ============================================================
# CONFIG
# ============================================================
BACKEND_URL = "https://genai-data-analyst-agent.onrender.com"

st.set_page_config(
    page_title="AI Data Analyst",
    page_icon="📊",
    layout="wide"
)

# ============================================================
# BACKEND WARM-UP (CRITICAL FOR RENDER)
# ============================================================
st.info(
    "🚀 This demo uses a free-tier backend. "
    "On first load, the backend may take ~20–40 seconds to wake up."
)

try:
    requests.get(f"{BACKEND_URL}/docs", timeout=5)
except:
    pass

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
    font-size: 28px;
    font-weight: bold;
    color: #4CAF50;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# HEADER
# ============================================================
st.title("📊 AI Data Analyst Agent")
st.caption("Upload → Ask → Analyze → Visualize → Explain")

# ============================================================
# TABS
# ============================================================
tab1, tab2, tab3 = st.tabs([
    "📁 Upload Dataset",
    "💬 Ask Questions",
    "📊 Analysis Dashboard"
])

# ============================================================
# TAB 1 — UPLOAD DATASET
# ============================================================
with tab1:
    st.subheader("📁 Upload CSV Dataset")

    uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])

    if uploaded_file:
        with st.spinner("Uploading dataset..."):
            resp = requests.post(
                f"{BACKEND_URL}/upload_csv",
                files={"file": (uploaded_file.name, uploaded_file.getvalue(), "text/csv")},
                timeout=30
            )

        if resp.status_code != 200:
            st.warning(
                "⏳ Backend is still starting. "
                "Please wait ~20 seconds and upload again."
            )
            st.stop()

        try:
            data = resp.json()
        except ValueError:
            st.warning(
                "⏳ Backend is waking up. "
                "Please retry the upload once."
            )
            st.stop()

        if "error" in data:
            st.error(data["error"])
            st.stop()

        st.success("Dataset uploaded successfully!")

        st.subheader("🔍 Preview")
        st.dataframe(pd.DataFrame(data["preview"]))

        st.subheader("🧬 Column Types")
        st.json(data["column_types"])

        st.session_state["uploaded"] = True

# ============================================================
# TAB 2 — ASK QUESTIONS
# ============================================================
with tab2:
    st.subheader("💬 Ask a Business Question")

    if not st.session_state.get("uploaded"):
        st.info("Upload a dataset first.")
        st.stop()

    question = st.text_input(
        "Enter your question",
        placeholder="e.g., average daily rate by department"
    )

    if st.button("🚀 Run Analysis"):
        if not question.strip():
            st.warning("Please enter a question.")
            st.stop()

        # ----------------------------
        # CALL /ask_data
        # ----------------------------
        with st.spinner("Generating SQL & running query..."):
            resp = requests.post(
                f"{BACKEND_URL}/ask_data",
                json={"question": question},
                timeout=30
            )

        if resp.status_code != 200:
            st.warning("⏳ Backend is starting. Please retry.")
            st.stop()

        try:
            ask_resp = resp.json()
        except ValueError:
            st.warning("⏳ Backend response not ready. Please retry.")
            st.stop()

        if "error" in ask_resp:
            st.error(ask_resp["error"])
            st.code(ask_resp.get("generated_sql", ""))
            st.stop()

        df = pd.DataFrame(ask_resp["rows"])
        st.code(ask_resp["generated_sql"])
        st.dataframe(df)

        st.session_state["analysis_df"] = df

        # ----------------------------
        # CALL /insights
        # ----------------------------
        with st.spinner("Generating insights & explanation..."):
            resp = requests.post(
                f"{BACKEND_URL}/insights",
                json={"question": question},
                timeout=30
            )

        if resp.status_code != 200:
            st.warning("⏳ Backend is starting. Please retry.")
            st.stop()

        try:
            insights = resp.json()
        except ValueError:
            st.warning("⏳ Backend response not ready. Please retry.")
            st.stop()

        st.session_state["insights"] = insights
        st.success("Analysis complete! Go to Analysis Dashboard →")

# ============================================================
# TAB 3 — DASHBOARD
# ============================================================
with tab3:
    if "analysis_df" not in st.session_state:
        st.info("Run an analysis first.")
        st.stop()

    df = st.session_state["analysis_df"]
    insights = st.session_state["insights"]

    st.subheader("📌 Key Metrics")
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(
            f"<div class='metric-card'>Rows<br><div class='metric-value'>{len(df)}</div></div>",
            unsafe_allow_html=True
        )
    with c2:
        st.markdown(
            f"<div class='metric-card'>Columns<br><div class='metric-value'>{df.shape[1]}</div></div>",
            unsafe_allow_html=True
        )
    with c3:
        st.markdown(
            f"<div class='metric-card'>Chart<br><div class='metric-value'>{insights.get('suggested_chart','N/A')}</div></div>",
            unsafe_allow_html=True
        )

    st.subheader("📈 Visualization")
    chart = insights.get("suggested_chart")
    details = insights.get("details", {})

    if chart == "bar":
        fig = px.bar(
            df,
            x="group_col",
            y="value",
            color="group_col"
        )
        st.plotly_chart(fig, use_container_width=True)
    elif chart == "kpi":
        st.metric("KPI", round(details.get("value", 0), 2))
    else:
        st.dataframe(df)

    st.subheader("💡 Insights")
    for i in insights.get("insights", []):
        st.markdown(f"- {i}")

    st.subheader("🤖 AI Explanation")
    st.text(insights.get("llm_explanation", "No explanation available."))
