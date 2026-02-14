# IntelliMix

IntelliMix is an AI-powered media processing platform for:
- AI music parody/mashup generation
- Multi-clip YouTube audio trimming and merging
- High-quality YouTube video/audio download

This version is production-focused with secure authentication and per-user generation history.

## What Is Now Production-Ready

- JWT-based authentication (`register`, `login`, `refresh`, `logout`, `me`)
- Password hashing (no plaintext passwords)
- Database-backed user and generation history persistence
- User-scoped history APIs (`list`, `view`, `delete`)
- User-scoped file access (`/files/:jobId/:filename`) requiring valid token
- Environment-based secrets and runtime config
- Protected frontend routes for all generation features
- Dedicated History UI for end users

## Updated Architecture

- `frontend`:
  - React + TypeScript + Vite
  - Auth context + protected routes
  - Tool pages wired to authenticated API
  - History page backed by API data
- `backend`:
  - Flask API (`/api/v1/*`)
  - SQLAlchemy models (`users`, `generation_jobs`, `token_blocklist`)
  - JWT access/refresh tokens
  - Existing AI/audio/video processing workflows retained

## Environment Setup

### Backend (`backend/.env`)
Copy from `backend/.env.example` and set values:

```env
FLASK_SECRET_KEY=replace-with-strong-random-string
JWT_SECRET_KEY=replace-with-strong-random-string
DATABASE_URL=sqlite:///intellimix.db
FRONTEND_ORIGIN=http://localhost:5173
GOOGLE_API_KEY=replace-with-gemini-key
GEMINI_MODEL_NAME=gemini-3-flash-preview
GEMINI_MAX_RETRIES=2
GEMINI_RETRY_BASE_SECONDS=2
LYRICS_FETCH_TIMEOUT_SECONDS=2.5
AI_REQUIRE_LLM_TIMESTAMPED_PLAN=false
TIMESTAMPED_LYRICS_API_URL=https://lrclib.net/api
TIMESTAMPED_LYRICS_TIMEOUT_SECONDS=6
AI_TIMESTAMPED_MIN_LINES_PER_SEGMENT=2
AI_TIMESTAMPED_LYRICS_MAX_LINES_PER_TRACK=120
JWT_ACCESS_TOKEN_MINUTES=30
JWT_REFRESH_TOKEN_DAYS=30
MAX_UPLOAD_SIZE_MB=50
STORAGE_ROOT=storage
PORT=5000
```

### Frontend (`frontend/.env`)
Copy from `frontend/.env.example`:

```env
VITE_API_URL=http://127.0.0.1:5000
```

## Local Development

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
python app.py
```

API will run at `http://127.0.0.1:5000`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend will run at `http://localhost:5173`.

## Docker Deployment

The repository now includes:
- `backend/Dockerfile`
- `frontend/Dockerfile`
- `frontend/nginx.conf` (SPA hosting + `/api` and `/files` reverse proxy)
- `docker-compose.yml` (frontend + backend + postgres)

### 1. Create Docker env file

Copy `.env.docker.example` to `.env.docker` and set secrets:

```bash
cp .env.docker.example .env.docker
```

Required at minimum:
- `POSTGRES_PASSWORD`
- `FLASK_SECRET_KEY`
- `JWT_SECRET_KEY`
- `GOOGLE_API_KEY`

Optional:
- `GEMINI_MODEL_NAME` (default: `gemini-3-flash-preview`)
- `GEMINI_MAX_RETRIES` (default: `2`)
- `GEMINI_RETRY_BASE_SECONDS` (default: `2`)
- Single intelligent remix pipeline is used by default (no runtime mixing-mode switch).
- `LYRICS_FETCH_TIMEOUT_SECONDS` (default: `2.5`)
- `AI_REQUIRE_LLM_TIMESTAMPED_PLAN` (default: `false`)
- `TIMESTAMPED_LYRICS_API_URL` (default: `https://lrclib.net/api`)
- `TIMESTAMPED_LYRICS_TIMEOUT_SECONDS` (default: `6`)
- `AI_TIMESTAMPED_MIN_LINES_PER_SEGMENT` (default: `2`)
- `AI_TIMESTAMPED_LYRICS_MAX_LINES_PER_TRACK` (default: `120`)

### 2. Start full stack

```bash
docker compose --env-file .env.docker up --build
```

### 3. Access services

- Frontend: `http://localhost:8080`
- Backend API (direct): `http://localhost:5000`

### 4. Stop stack

```bash
docker compose --env-file .env.docker down
```

Persisted volumes:
- `postgres-data`
- `backend-storage`

## Docker Dev (Hot Reload)

Use the dedicated dev compose file for live updates:
- `docker-compose.dev.yml`
- `backend/Dockerfile.dev` (Flask debug server with reload)
- `frontend/Dockerfile.dev` (Vite dev server with HMR)

Start dev stack:

```bash
docker compose -f docker-compose.dev.yml --env-file .env.docker up --build
```

Dev URLs:
- Frontend (HMR): `http://localhost:5173`
- Backend API: `http://localhost:5001`

Stop dev stack:

```bash
docker compose -f docker-compose.dev.yml --env-file .env.docker down
```

## Key API Routes

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `GET /api/v1/history`
- `GET /api/v1/history/:jobId`
- `DELETE /api/v1/history/:jobId`
- `POST /api/v1/generate-ai`
- `POST /api/v1/process-array`
- `POST /api/v1/process-csv`
- `POST /api/v1/download-video`
- `POST /api/v1/download-audio`
- `GET /files/:jobId/:filename`

## Testing

Backend tests (auth + history behavior):

```bash
cd backend
pytest -q
```

## Production Notes

- Replace SQLite with managed Postgres via `DATABASE_URL`
- Use HTTPS in production and secure secret management
- Move generated media from local disk to object storage (S3/GCS) for horizontal scaling
- Add worker queues for long-running jobs (Celery/RQ)
- Add rate limiting and audit logging at gateway layer
