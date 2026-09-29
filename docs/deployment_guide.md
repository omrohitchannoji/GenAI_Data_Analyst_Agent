# Deployment & Operations Guide
**Project:** Stateful Agentic AI Data Analyst  
**Document:** docs/deployment_guide.md  
**Version:** 1.0  

---

## 1. Local Development & Docker Compose

### 1.1 Local Run (Without Docker)
1. **Backend:**
   ```powershell
   cd backend
   .\venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
2. **Frontend:**
   ```powershell
   cd frontend
   streamlit run app.py
   ```

### 1.2 Local Container Smoke Test (Docker Compose)
1. Ensure `.env` exists in the repository root or `backend/` with `GROQ_API_KEY`.
2. Build and start services:
   ```bash
   docker compose up --build -d
   ```
3. Check container health:
   ```bash
   docker compose ps
   ```
4. Access applications:
   - **Streamlit UI:** `http://localhost:8501`
   - **FastAPI OpenAPI Docs:** `http://localhost:8000/docs`
5. Stop services:
   ```bash
   docker compose down
   ```

---

## 2. AWS EC2 Single-Host Deployment

### 2.1 EC2 Sizing & Infrastructure
- **Instance Type:** `t3.medium` (2 vCPU, 4 GiB RAM) minimum; recommended `t3.large`.
- **Operating System:** Ubuntu 22.04 LTS or Amazon Linux 2023.
- **Storage:** 20 GiB gp3 EBS volume.
- **Security Group (Inbound Rules):**
  - `SSH (22)`: Restricted to your administrative IP.
  - `HTTP (80) / HTTPS (443)`: Allowed for Nginx SSL termination.
  - `Custom (8501)`: Restricted or reverse-proxied via Nginx.

### 2.2 EC2 Host Setup
```bash
# 1. Update packages and install Docker
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin git curl

# 2. Allow non-root docker execution
sudo usermod -aG docker $USER
newgrp docker

# 3. Clone repository
git clone https://github.com/omrohitchannoji/GenAI_Data_Analyst_Agent.git
cd GenAI_Data_Analyst_Agent

# 4. Configure environment
echo "GROQ_API_KEY=your_groq_api_key_here" > backend/.env
echo "GROQ_MODEL=openai/gpt-oss-120b" >> backend/.env

# 5. Start with persistent storage
docker compose up -d --build
```

---

## 3. Persistence, Backup & Restore Procedures

### 3.1 Persistent Storage Volumes
The application mounts four SQLite database files from the host filesystem:
1. `uploaded_data.db`: Ingested analytical datasets.
2. `agent_checkpoints.db`: LangGraph conversational checkpoints.
3. `dataset_registry.db`: Multi-tenant ownership and metadata registry.
4. `business_glossary.db`: Approved enterprise business metrics.

### 3.2 Backup Procedure
Run an atomic SQLite backup without stopping the running container:
```bash
mkdir -p ./backups/$(date +%F)
sqlite3 backend/uploaded_data.db ".backup './backups/$(date +%F)/uploaded_data.db'"
sqlite3 backend/agent_checkpoints.db ".backup './backups/$(date +%F)/agent_checkpoints.db'"
sqlite3 backend/dataset_registry.db ".backup './backups/$(date +%F)/dataset_registry.db'"
sqlite3 backend/business_glossary.db ".backup './backups/$(date +%F)/business_glossary.db'"
```

### 3.3 Restore Procedure
To restore state from a backup:
```bash
# Stop containers
docker compose stop

# Replace databases
cp ./backups/2026-09-29/uploaded_data.db backend/uploaded_data.db
cp ./backups/2026-09-29/agent_checkpoints.db backend/agent_checkpoints.db

# Restart containers
docker compose start
```

---

## 4. Rollback Procedure
If a deployment fails:
1. Revert to the previous stable git commit:
   ```bash
   git checkout <previous_stable_commit_hash>
   ```
2. Rebuild and restart containers:
   ```bash
   docker compose down
   docker compose up -d --build
   ```
3. Run evaluation smoke test:
   ```bash
   docker compose exec backend python eval/eval_suite.py
   ```
