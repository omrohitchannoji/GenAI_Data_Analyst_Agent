import streamlit as st
import pandas as pd
import plotly.express as px
import requests

BACKEND_URL = "http://localhost:8000"


st.set_page_config(page_title="AI Data Analyst", page_icon="📊", layout="wide")

# CUSTOM CSS (Professional UI)
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

hr {
    margin-top: 40px;
    margin-bottom: 40px;
}
</style>
""", unsafe_allow_html=True)

st.title("📊 AI Data Analyst Agent")
st.caption("Upload → Ask → Analyze → Visualize → Explain")

tab1, tab2, tab3 = st.tabs(["📁 Upload Dataset", "💬 Ask Questions", "📊 Analysis Dashboard"])

# TAB 1 — Upload Dataset
with tab1:
    st.markdown("### 📁 Upload Your CSV Dataset")
    with st.container():
        uploaded_file = st.file_uploader("Upload CSV", type=["csv"])

        if uploaded_file:
            with st.spinner("Processing dataset..."):
                resp = requests.post(
                    f"{BACKEND_URL}/upload_csv",
                    files={"file": (uploaded_file.name, uploaded_file.getvalue(), "text/csv")}
                )

            data = resp.json()

            if "error" in data:
                st.error(data["error"])
                st.stop()

            st.success("Dataset uploaded successfully!")

            st.markdown("#### 🔍 Preview")
            st.dataframe(pd.DataFrame(data["preview"]))

            st.markdown("#### 🧬 Column Types Detected")
            st.json(data["column_types"])

# TAB 2 — Ask Questions (Chat-like)
with tab2:
    st.markdown("### 💬 Ask a Business Question")
    st.markdown("Enter natural language questions such as:")
    st.markdown("- *average daily rate by department*")
    st.markdown("- *count employees by job role*")
    st.markdown("- *max salary by education level*")
    st.markdown("---")

    question = st.text_input("Ask your question:", placeholder="e.g., average daily rate by department")
    run_btn = st.button("🚀 Run Analysis")

    if run_btn:
        if not uploaded_file:
            st.error("Please upload a dataset first.")
            st.stop()

        if not question.strip():
            st.error("Enter a question first.")
            st.stop()

        # 1. CALL /ask_data
        with st.spinner("Generating SQL & running query..."):
            ask_resp = requests.post(
                f"{BACKEND_URL}/ask_data",
                json={"question": question}
            ).json()

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

        # 2. CALL /insights
        with st.spinner("Generating insights + AI explanation..."):
            insights = requests.post(
                f"{BACKEND_URL}/insights",
                json={"question": question}
            ).json()

        st.session_state["insights"] = insights

        st.success("Analysis complete! Go to **Analysis Dashboard** tab →")

# TAB 3 — Results + Insights + LLM Narrative
with tab3:

    if "analysis_df" not in st.session_state:
        st.info("Run an analysis first from the **Ask Questions** tab.")
        st.stop()

    df = st.session_state["analysis_df"]
    insights = st.session_state["insights"]

    # SECTION: Metrics Cards
    st.markdown("### 📌 Key Metrics")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <h3>Rows Returned</h3>
            <div class="metric-value">{len(df)}</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <h3>Columns</h3>
            <div class="metric-value">{df.shape[1]}</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <h3>Chart Suggested</h3>
            <div class="metric-value">{insights.get("suggested_chart", "N/A").upper()}</div>
        </div>
        """, unsafe_allow_html=True)

    # SECTION: Visualization
    st.markdown("### 📈 Visualization")

    chart_type = insights.get("suggested_chart")
    details = insights.get("details", {})

    if chart_type == "bar":
        x = details.get("group_column")
        y = details.get("value_column")

        fig = px.bar(df, x=x, y=y, color=x, title="Bar Chart")
        st.plotly_chart(fig, use_container_width=True)

    elif chart_type == "kpi":
        st.metric("KPI Value", round(details.get("value", 0), 2))

    else:
        st.dataframe(df)

    # SECTION: Insights
    st.markdown("### 💡 Insights Generated")
    for b in insights.get("insights", []):
        st.markdown(f"- {b}")

    # SECTION: AI Narrative
    st.markdown("### 🤖 AI Explanation")
    st.text(insights.get("llm_explanation", "No explanation available."))
