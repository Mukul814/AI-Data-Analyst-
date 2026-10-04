# Datawise — AI Data Analyst

Datawise is a portfolio-grade analytics workspace for CSV and Excel files. Upload a dataset, inspect a deterministic profile, then ask plain-language questions and receive calculations and safe chart specifications.

## Features

- CSV and XLSX upload with size/type checks, local storage abstraction, and automatic profiling.
- Dashboard, project creation, dataset overview, preview table, analysis prompt suggestions, charts, and expandable calculation code.
- Deterministic Pandas analysis for row counts, missing values, aggregates, common statistics, correlations, monthly trends, IQR outlier screening, and a baseline forecast.
- Provider interface with no-key mock mode and optional Gemini explanations.
- PostgreSQL schema via SQLAlchemy 2 and Alembic, with conversations and results persisted.
- Short-lived analysis subprocess. It accepts data and a question, never model-generated Python or shell commands.

## Architecture

The React client uses Vite, TypeScript, Tailwind, TanStack Query, React Router, and Recharts. FastAPI validates API requests and delegates ingestion, profiling, analysis, storage, and AI explanation to separate modules. PostgreSQL stores projects, column profiles, conversations, and analysis metadata; uploaded file bytes stay in a local storage directory. The storage class is the extension point for object storage.

The analysis engine chooses from fixed, deterministic Pandas operations. The displayed Python is an explanation of the selected operation. No LLM code is executed. A child process gets a bounded JSON copy of the dataset, a question, a temporary working directory, a minimal environment, and a timeout. This local process boundary is not an OS container sandbox: production deployments that accept hostile users should run the worker in a separate container with CPU/memory quotas, read-only root filesystem, dropped capabilities, no network, and per-job storage. The worker does not receive provider or database credentials.

Gemini is called only after calculations, to explain the computed answer. The app sends the user question and computed result, not the uploaded raw table, credentials, or environment. Mock mode returns the deterministic answer directly.

## Local setup

Docker Compose is the recommended startup path:

```bash
cp .env.example .env
docker compose up --build
```

Open <http://localhost:5173>. The API and interactive OpenAPI docs are at <http://localhost:8000> and <http://localhost:8000/docs>. Upload `data/sales.csv` to try the sample data.

Docker must be installed and running. To run services without Docker, create a PostgreSQL database and set `DATABASE_URL`, then:

```bash
cd backend
python -m venv .venv
# Activate .venv, then:
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

The backend defaults to a local SQLite URL for quick development; Docker Compose overrides it with PostgreSQL. For SQLite, tables are initialized on startup and the default database path is `../data/analyst.db` relative to `backend/`. Set `STORAGE_PATH=../data/uploads` for a local run. PostgreSQL startup runs the Alembic migration first.

## Configuration

Copy `.env.example` to `.env`. Important values:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy URL; Compose sets PostgreSQL automatically. |
| `POSTGRES_PASSWORD` | Local Compose database password; replace before deployment. |
| `AI_PROVIDER` | `mock` or `gemini`; defaults to `mock`. |
| `GEMINI_API_KEY` | Optional Google AI Studio key, required only for Gemini. |
| `GEMINI_MODEL` | Gemini model identifier. |
| `STORAGE_PROVIDER` / `STORAGE_PATH` | Storage implementation and local upload directory. |
| `MAX_UPLOAD_MB` | Maximum accepted upload size. |
| `FRONTEND_URL` | Allowed browser origin for the API. |
| `ANALYSIS_TIMEOUT_SECONDS` | Worker process deadline. |
| `AI_REQUEST_TIMEOUT_SECONDS` | Maximum wait for an AI provider response. |

Mock mode requires no API key. To enable Gemini, obtain a key in [Google AI Studio](https://aistudio.google.com/app/apikey), set `AI_PROVIDER=gemini` and `GEMINI_API_KEY` in your untracked `.env`, then restart the backend. Never commit `.env` or put the key in a frontend variable.

## Database and migrations

ORM models are under `backend/app/models.py`. The initial migration is under `backend/migrations/versions`. Apply later migrations from `backend/` with `alembic upgrade head`.

## Tests and checks

```bash
cd backend
pip install -r requirements.txt
pytest
ruff check app tests
```

```bash
cd frontend
npm install
npm test
npm run build
```

## Production deployment

Build the backend and frontend images and deploy them with managed PostgreSQL. Supply secrets through the platform secret store, persist or externalize file storage, set the real frontend CORS origin, and terminate TLS at the platform ingress. The frontend API URL is controlled by `VITE_API_URL` at image build time. Add authentication/authorization, per-user quotas, malware scanning, durable object storage, and a separately constrained analysis worker before exposing uploads to untrusted tenants.

## Security and current scope

- Filenames are reduced to basenames; stored names are random UUIDs; path traversal is rejected.
- Accepted suffixes are CSV/XLSX and both formats must parse successfully. Size is capped before parsing. MIME is not trusted as the validation mechanism.
- The deterministic engine does not execute arbitrary generated code. The child process strips application secrets and times out; the process does not yet enforce a platform-independent memory/CPU quota.
- Authentication, user-level authorization, rate limiting, malware scanning, persistent object storage, and a dedicated container sandbox remain deployment work.
- Conversational records persist. The first version supports follow-up analysis through the same dataset/conversation id, but does not yet reconstruct arbitrary pronouns into a prior computed subset.
- The forecast is an intentionally simple linear-drift baseline and is labelled an estimate.
