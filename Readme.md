# 🤖 GenAI Data Analyst Agent

A production-ready **AI Data Analyst Agent** that allows users to upload datasets, ask natural-language business questions, automatically generate SQL, visualize results, and receive **LLM-powered executive insights** — all through a clean web interface.

🔗 **Live App**: [https://genai-data-analyst-agent.onrender.com](https://genai-data-analyst-agent.onrender.com)
🔗 **API Docs**: [https://genai-data-analyst-agent.onrender.com/docs](https://genai-data-analyst-agent.onrender.com/docs)

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

This is not a demo toy — it is designed to be **resume-, interview-, and recruiter-ready**.

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

* Render (Web Service)

---

## 🧊 Cold Start Notice (Important)

⚠️ **Cold Start Behavior (Render Free Tier)**

* The backend may **sleep after inactivity**
* First request can take **20–40 seconds** to respond

✅ This is expected behavior on free-tier deployments.

**What to do if the app feels stuck:**

1. Open the API docs directly:
   👉 [https://genai-data-analyst-agent.onrender.com/docs](https://genai-data-analyst-agent.onrender.com/docs)
2. Wait for the backend to wake up
3. Refresh the frontend page

Once warmed, the app works normally.

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

## 📝 Future Enhancements

* MLflow experiment tracking
* Dockerization
* CI/CD with GitHub Actions
* Authentication & user sessions
* Vector-based semantic querying

---

## 👤 Author

**Om Rohit Channoji**
AI / Data Science Enthusiast

---

⭐ If you found this project useful, consider starring the repository!
