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

* 🔍 **Natural Language → SQL** (LLM + rule-based fallback)
* 📊 **Automatic insights & KPIs**
* 📈 **Smart chart recommendations**
* 🤖 **LLM-generated executive explanations** (structured, non-hallucinating)
* 🧱 **Fail-safe architecture** (fallbacks when LLMs fail or rate-limit)
* 🌐 **Deployed backend + frontend**

---

## 🏗️ Architecture Overview

```
Frontend (Streamlit)
   │
   │ HTTP requests
   ▼
Backend (FastAPI)
   ├── Dataset upload & schema detection
   ├── Query engine (NL → SQL)
   ├── Rule-based insights engine
   ├── LLM services (SQL, charts, explanation)
   └── SQLite execution layer
```
### Design Philosophy

The system follows a **deterministic-first, LLM-assisted** design:
- LLMs are used for interpretation and explanation
- All computations (SQL execution, KPIs, aggregations) are deterministic
- This prevents hallucinated metrics and ensures analytical correctness

The system is intentionally **modular**, making it easy to extend with:

* MLflow
* Vector databases
* Authentication
* Caching

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
- Vector-based RAG for dataset context enrichment
- Semantic chunking of dataset summaries

These features are enabled in the deployed version and optimized for memory-safe execution on EC2.

## 📝 Future Enhancements

* MLflow experiment tracking
* Dockerization
* CI/CD with GitHub Actions
* Authentication & user sessions
* Vector-based semantic querying
* Vector-based semantic querying (RAG-based NL → SQL context enrichment)

---

## 👤 Author

**Om Rohit Channoji**
AI / Data Science Enthusiast

---

⭐ If you found this project useful, consider starring the repository!
