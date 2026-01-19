# 🤖 GenAI Data Analyst Agent

A production-ready **AI Data Analyst Agent** that allows users to upload datasets, ask natural-language business questions, automatically generate SQL, visualize results, and receive **LLM-powered executive insights** — all through a clean web interface.
> ⚠️ Designed with real-world GenAI constraints in mind (token limits, fallback logic, deterministic execution).


🔗 [Live App](https://genaidataanalystagent-omrohit.streamlit.app/)
🔗 [API Docs](http://13.201.45.117:8000//docs)

---

## 🚀 What This Project Does

This project simulates how a **real-world AI Data Analyst** works:

1. **Upload a dataset (CSV)**
2. **Ask questions in plain English** (e.g., *average daily rate by department*)
3. System automatically:

   * Converts the question into **SQL**
   * Executes it safely on the dataset
   * Generates **rule-based insights**
   * Creates **charts**
   * Produces a **consulting-style AI explanation** (executive summary, observations, recommendation)

---

## 🧠 Key Features

* 🔍 **Natural Language → SQL**
  - LLM-powered SQL generation grounded in dataset context
  - Rule-based SQL fallback for reliability

* 🧠 **RAG-based Dataset Understanding (LangChain)**
  - Dataset schema, column semantics, and summaries embedded
  - Retrieval-Augmented Generation (RAG) ensures SQL is context-aware, not guessed

* 📊 **Deterministic Insights & KPIs**
  - Aggregations, trends, and anomaly detection computed via code
  - Ensures correctness and reproducibility

* 📈 **Smart Chart Recommendations**
  - Automatic bar, line, KPI, or table selection based on result structure

* 🤖 **LLM-Generated Executive Explanations**
  - Consulting-style summaries grounded in computed insights
  - No hallucinated metrics

* 🧱 **Fail-Safe Architecture**
  - Graceful degradation when LLMs fail or rate-limit

---

## 🏗️ Architecture Overview

```
Frontend (Streamlit)
   │
   │ HTTP requests
   ▼
Backend (FastAPI)
   ├── Dataset upload & schema analysis
   ├── RAG context builder (LangChain + vector store)
   ├── Query engine (NL → SQL)
   ├── SQLite execution layer
   ├── Deterministic insights engine
   ├── Visualization recommendation
   └── LLM-based executive explanation
```
### Design Philosophy

### Design Philosophy

The system follows a **dataset-first, RAG-grounded, LLM-assisted** design:

- **LangChain-based RAG** is used to ground the LLM in:
  - Dataset schema
  - Column semantics
  - Statistical summaries

- LLMs are used for:
  - Business intent interpretation
  - SQL generation (with dataset grounding)
  - Executive-level explanations

- Deterministic code is used for:
  - SQL execution
  - Aggregations and KPIs
  - Trend and anomaly detection
  - Chart recommendation

This hybrid approach reduces hallucinations while preserving analytical flexibility.

---

## 🧰 Tech Stack

**Frontend**

* Streamlit
* Plotly

**Backend**

* FastAPI
* SQLite
* Pandas

**GenAI / LLMs**

* Groq API
* LLaMA 3.1 (Instant)
* LangChain (RAG orchestration)
* Vector embeddings for dataset context

**Deployment**

* Backend: AWS EC2 (Ubuntu) + systemd (always-on)
* Frontend: Streamlit Community Cloud

---

## ⚠️ Known Limitations & Design Tradeoffs

### Free-Tier LLM Constraints
- Groq free tier enforces rate and token limits
- Some requests may fall back to deterministic logic

### Why This Is Intentional
- The system is designed to
   - Expose real-world GenAI reliability issues
   - Demonstrate graceful degradation strategies
   - Avoid “demo-only” behavior

### In production, this would be mitigated via:
- Caching
- Batching
- Higher-tier LLM quotas
- Async execution

---

## 📦 How to Run Locally

### 1️⃣ Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend runs at:

```
http://localhost:8000
```

---

### 2️⃣ Frontend

```bash
cd frontend
streamlit run app.py
```

Frontend runs at:

```
http://localhost:8501
```

Update this line in `frontend/app.py` when running locally:

```python
BACKEND_URL = "http://localhost:8000"
```

---

## 🔐 Environment Variables

Create a `.env` file or set variables directly:

```bash
GROQ_API_KEY=your_api_key_here
```

---
### 🧪 Experimental Features
- RAG-based dataset context enrichment using LangChain
- Semantic chunking and embedding of dataset metadata

These features are enabled in the deployed version and optimized for memory-safe execution on EC2.

## 📝 Future Enhancements

* MLflow experiment tracking
* Improved semantic grounding for NL → SQL accuracy  
* Multi-turn analytical conversations  
* Optimized RAG retrieval & caching  
* Query confidence scoring & validation  
* Dockerization & CI/CD pipeline  
---

## 👤 Author

**Om Rohit Channoji**
AI / Data Science Enthusiast

---

⭐ If you found this project useful, consider starring the repository!
