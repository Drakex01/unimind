# UniMind Deployment and Operations Runbook

## 1. Local Development Setup

### Prerequisites
- Python 3.12 (via `py -3.12`)
- Node.js 18+ and npm
- Docker and Docker Compose (for containerized stack)

### Quickstart (Local Native)
1. **Clone repository and setup Python environment**:
   ```bash
   cd unimind
   py -3.12 -m venv .venv
   .\.venv\Scripts\pip install -r requirements.txt
   ```
2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Add your GEMINI_API_KEY in .env if testing real cloud models
   ```
3. **Run API Server**:
   ```bash
   .\.venv\Scripts\uvicorn apps.api.src.main:app --host 0.0.0.0 --port 8000 --reload
   ```
4. **Run Web Frontend**:
   ```bash
   cd apps/web
   npm install
   npm run dev
   ```
   Open `http://localhost:5173`.

5. **Run Automated Test Suite**:
   ```bash
   .\.venv\Scripts\pytest -v
   ```

---

## 2. Containerized Deployment (Docker Compose)

To spin up the complete production-like stack (PostgreSQL, Qdrant, Redis, API, and Nginx Web Frontend):

```bash
docker-compose up --build -d
```

### Health Probes
- API Liveness: `curl http://localhost:8000/health/live`
- API Readiness: `curl http://localhost:8000/health/ready`
- Web Frontend: `http://localhost:3000`

### Graceful Teardown
```bash
docker-compose down
```
