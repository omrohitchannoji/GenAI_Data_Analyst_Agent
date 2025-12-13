import streamlit as st
import pandas as pd
import plotly.express as px
import requests

BACKEND_URL = "https://genai-data-analyst-agent.onrender.com"

# SAFE JSON HELPER (CRITICAL)
def safe_json_response(resp):
    if resp.status_code != 200:
        st.error(f"Backend error ({resp.status_code})")
        st.text(resp.text)
        st.stop()

    try:
        return resp.json()
    except Exception:
        st.error("Backend is waking up or returned non-JSON. Please retry.")
        st.text(resp.text)
        st.stop()

st.set_page_config(
    page_title="AI Data Analyst",
    page_icon="📊",
    layout="wide"
)

st.markdown("""
<style>
body {
    font-family: 'Inter', sans-serif;
}
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
.metric-card h3 {
    font-size: 20px;
    margin-bottom: 5px;
}
.metric-value {
    font-size: 28px;
    font-weight: bold;
    color: #4CAF50;
}
</style>
""", unsafe_allow_html=True)

st.title("📊 AI Data Analyst Agent")
st.caption("Upload → Ask → Analyze → Visualize → Explain")

tab1, tab2, tab3 = st.tabs([
    "📁 Upload Dataset",
    "💬 Ask Questions",
    "📊 Analysis Dashboard"
])

# TAB 1 — UPLOAD DATASET
with tab1:
    st.markdown("### 📁 Upload Your CSV Dataset")

    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])

    if uploaded_file:
        with st.spinner("Processing dataset..."):
            resp = requests.post(
                f"{BACKEND_URL}/upload_csv",
                files={"file": (uploaded_file.name, uploaded_file.getvalue(), "text/csv")},
                timeout=60
            )

        data = safe_json_response(resp)

        if "error" in data:
            st.error(data["error"])
            st.stop()

        st.success("Dataset uploaded successfully!")

        st.markdown("#### 🔍 Preview")
        st.dataframe(pd.DataFrame(data["preview"]))

        st.markdown("#### 🧬 Column Types Detected")
        st.json(data["column_types"])

# TAB 2 — ASK QUESTIONS
with tab2:
    st.markdown("### 💬 Ask a Business Question")

    question = st.text_input(
        "Ask your question:",
        placeholder="e.g., count employees by job role"
    )

    run_btn = st.button("🚀 Run Analysis")

    if run_btn:
        if not uploaded_file:
            st.error("Please upload a dataset first.")
            st.stop()

        if not question.strip():
            st.error("Enter a question first.")
            st.stop()

        # -------- ASK DATA --------
        with st.spinner("Generating SQL & running query..."):
            ask_resp = safe_json_response(
                requests.post(
                    f"{BACKEND_URL}/ask_data",
                    json={"question": question},
                    timeout=60
                )
            )

        if "error" in ask_resp:
            st.error(ask_resp["error"])
            st.code(ask_resp.get("generated_sql", ""))
            st.stop()

        df_results = pd.DataFrame(ask_resp["rows"])

        st.markdown("### 🧾 SQL Generated")
        st.code(ask_resp["generated_sql"])

        st.markdown("### 📊 Query Results")
        st.dataframe(df_results)

        st.session_state["analysis_df"] = df_results

        # -------- INSIGHTS --------
        with st.spinner("Generating insights + AI explanation..."):
            insights = safe_json_response(
                requests.post(
                    f"{BACKEND_URL}/insights",
                    json={"question": question},
                    timeout=60
                )
            )

        st.session_state["insights"] = insights
        st.success("Analysis complete! Go to **Analysis Dashboard** tab →")

# TAB 3 — DASHBOARD
with tab3:
    if "analysis_df" not in st.session_state:
        st.info("Run an analysis first from the **Ask Questions** tab.")
        st.stop()

    df = st.session_state["analysis_df"]
    insights = st.session_state["insights"]

    # -------- METRICS --------
    st.markdown("### 📌 Key Metrics")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Rows Returned", len(df))

    with col2:
        st.metric("Columns", df.shape[1])

    with col3:
        st.metric(
            "Chart Suggested",
            insights.get("suggested_chart", "N/A").upper()
        )

    # -------- VISUALIZATION --------
    st.markdown("### 📈 Visualization")

    chart_type = insights.get("suggested_chart")
    details = insights.get("details", {})

    if chart_type == "bar":
        fig = px.bar(
            df,
            x=details.get("group_column"),
            y=details.get("value_column"),
            color=details.get("group_column"),
            title="Bar Chart"
        )
        st.plotly_chart(fig, use_container_width=True)

    elif chart_type == "kpi":
        st.metric(
            "KPI Value",
            round(details.get("value", 0), 2)
        )

    else:
        st.dataframe(df)

    # -------- INSIGHTS --------
    st.markdown("### 💡 Insights Generated")
    for bullet in insights.get("insights", []):
        st.markdown(f"- {bullet}")

    # -------- AI EXPLANATION --------
    st.markdown("### 🤖 AI Explanation")
    st.write(insights.get("llm_summary", "No explanation available."))
