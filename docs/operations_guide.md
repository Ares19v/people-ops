# Operations, Deployment & Troubleshooting Guide

## 1. Environment Configuration

All credentials and runtime settings are configured via `.env`. See `.env.example` for all supported options.

### Key Production Variables
```bash
ENVIRONMENT=production
DATABASE_URL=postgresql+asyncpg://hr_user:<SECRET>@postgres:5432/hr_db
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<SECRET>
S3_ENDPOINT_URL=http://minio:9000
S3_ACCESS_KEY=<SECRET>
S3_SECRET_KEY=<SECRET>
SECRET_KEY=<CRYPTOGRAPHIC_SECRET_KEY>
MOCK_SSO_ENABLED=false
MOCK_LLM_ENABLED=false
VERTEX_PROJECT_ID=<GCP_PROJECT_ID>
VERTEX_LOCATION=us-central1
GEMINI_MODEL=gemini-1.5-pro
LANGCHAIN_API_KEY=<LANGSMITH_KEY>
```

---

## 2. Docker Compose Lifecycle

### Start Services
```bash
docker compose up --build -d
```

### Check Logs
```bash
docker compose logs -f backend
docker compose logs -f frontend
```

### Stop Services
```bash
docker compose down -v
```

---

## 3. Database Migrations & Seeding

The application automatically verifies and builds tables on startup using SQLAlchemy's async metadata engine.

To manually re-seed initial accounts, projects, and balances:
```bash
cd backend
.venv/Scripts/python data/seed_data.py
```

---

## 4. Troubleshooting & FAQs

### Issue 1: NeMo Guardrails dependency compatibility
- **Symptom**: `ImportError: cannot import name 'RailsConfig' from 'nemoguardrails'`.
- **Solution**: Ensure Python 3.11 is used. Version `nemoguardrails==0.24.1` has pre-compiled wheels for Python 3.11.

### Issue 2: PostgreSQL connection refused
- **Symptom**: `ConnectionRefusedError: [WinError 1225]`.
- **Solution**: Ensure Docker is running and `docker compose ps` shows `hr_postgres` in healthy state. For local test runner without docker, the test suite automatically falls back to an isolated SQLite test database.

### Issue 3: CORS errors in frontend
- **Symptom**: `Access to fetch has been blocked by CORS policy`.
- **Solution**: Confirm that `BACKEND_CORS_ORIGINS` in `.env` includes your client origin (e.g. `http://localhost:3000` or `http://localhost:5173`).
