# Deployment guide

The repository includes `backend/Dockerfile` and
`.github/workflows/ci.yml`. Deploy the same runtime pieces on any platform that
supports them:

- a static frontend built from `frontend/`
- the FastAPI service in `backend/`
- the LiveKit agent worker in `backend/app/agent/worker.py` (run through the
  `backend/agent.py` compatibility entry point)
- a dedicated post-call analysis worker, or one API replica with
  `ANALYSIS_WORKER_ENABLED=true`
- MongoDB Atlas or another replica-set MongoDB
- LiveKit Cloud and Sarvam credentials

The API and agent worker both connect to MongoDB and LiveKit directly. The agent
does not serve HTTP. The browser should reach the API through the same origin,
using a reverse proxy for `/api/*`, so the admin session cookie stays
same-origin.

## 1. Rotate local secrets first

The repository may have been used with real local credentials. Before deploying,
rotate:

- LiveKit API key/secret
- Sarvam API key
- MongoDB database user password
- Any old JWT secret

Never commit `backend/.env` or `frontend/.env`.

Generate a production JWT secret:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

## 2. MongoDB Atlas

1. Create an Atlas cluster. A paid tier is recommended because booking uses
   transactions; a free shared cluster may not support them.
2. Create a database user with read/write access to `clinic_voice_ai`.
3. Add the API and agent worker egress IPs to the Atlas IP access list, or use a
   VPC/private endpoint. `0.0.0.0/0` is acceptable only for a temporary demo.
4. Copy the SRV connection string. It must include
   `retryWrites=true&w=majority`.
5. Seed the clinic:
   - set `MONGODB_URI` locally and run
     `backend/.venv/Scripts/python.exe scripts/seed_clinic.py`
   - optionally run `scripts/seed_data.py` for demo doctors and slots
6. Create the admin account:
   `backend/.venv/Scripts/python.exe scripts/create_admin.py --email admin@example.com`
   and enter the password when prompted.

Indexes are created automatically at API/agent startup by
`app/db/indexes.py`. If the unique doctor-slot index cannot be created because
duplicate slots already exist, run the idempotent migration:

```powershell
backend/.venv/Scripts/python.exe scripts/ops/migrate_slot_indexes.py
backend/.venv/Scripts/python.exe scripts/ops/migrate_slot_indexes.py --apply
```

The first command is a dry run. `--apply` deletes duplicate slots, keeps a
booked slot when one exists, and creates `uniq_doctor_slot`.

Startup also replaces the legacy all-status unique appointment slot index with
a confirmed-only index. This lets a cancelled slot be rebooked while still
preventing two confirmed appointments from sharing the same slot. The MongoDB
user therefore needs `createIndex` and `dropIndex` permissions; if the legacy
index cannot be dropped, startup logs a warning and cancelled slots may remain
blocked until it is removed.

## 3. API service

1. Install `backend/requirements.txt` in a Python environment.
2. Run the API from `backend/`:

   ```powershell
   uvicorn main:app --host 0.0.0.0 --port 8000 --no-proxy-headers
   ```

   Behind a trusted reverse proxy, use
   `--proxy-headers --forwarded-allow-ips=<proxy-ip>` instead and set
   `TRUST_PROXY_HEADERS=true`.

3. Health check paths: `/api/health/live` (liveness), `/api/health` and
   `/api/ready` (MongoDB readiness).
4. Set the shared environment variables for both the API and agent worker:
   - `APP_ENV=production`
   - `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
   - `LIVEKIT_AGENT_NAME=clinic-receptionist`
   - `SARVAM_API_KEY`
   - `MONGODB_URI`, `MONGODB_DATABASE=clinic_voice_ai`
   - `DATABASE_TIMEOUT_MS=5000`
   - `CLINIC_TIMEZONE=Asia/Kolkata`
   - `JWT_SECRET` (32+ characters)
   - `JWT_ALGORITHM=HS256`, `JWT_EXPIRE_MINUTES=480`
   - `AUTH_COOKIE_NAME=clinic_access_token`
   - `COOKIE_SECURE=true`, `COOKIE_SAMESITE=lax`
   - `LOG_LEVEL=INFO`, `RATE_LIMIT_ENABLED=true`
   - `TRUSTED_HOSTS` with explicit API hostnames
   - `TRUST_PROXY_HEADERS=true` only behind a trusted reverse proxy; also run
     Uvicorn with `--proxy-headers --forwarded-allow-ips=<proxy-ip>`
   - optional `SENTRY_DSN`, `SENTRY_ENVIRONMENT=production`
   - optional RAG settings: `OPENAI_API_KEY`, `RAG_ENABLED`,
     `OPENAI_EMBEDDING_MODEL`, `RAG_TOP_K`, `RAG_MIN_SCORE`,
     `RAG_CHUNK_CHARS`, `RAG_CHUNK_OVERLAP`, `RAG_TIMEOUT_SECONDS`,
     `RAG_MAX_UPLOAD_BYTES`, `RAG_MAX_PDF_PAGES`, `RAG_MAX_DOCUMENTS`
5. API-only variables:
   - `ANALYSIS_WORKER_ENABLED=false` when running a dedicated worker
   - `CORS_ORIGINS` with the exact production frontend origin; never use `*`
     because credentialed requests are enabled

For a same-origin reverse proxy, `COOKIE_SAMESITE=lax` is sufficient. If the
frontend calls the API directly from another site, use
`COOKIE_SAMESITE=none` and `COOKIE_SECURE=true`, and add the frontend origin to
`CORS_ORIGINS`.

## 4. Agent worker

1. Use the same Python environment and shared environment variables as the API.
2. Set `ANALYSIS_WORKER_ENABLED=false` so only the API processes post-call
   analysis.
3. Run the worker from `backend/`:

   ```powershell
   python agent.py start
   ```

4. Confirm the worker registers with LiveKit in its logs.
5. Run one dedicated analysis worker when `ANALYSIS_WORKER_ENABLED=false`:

   ```powershell
   python -m app.workers.analysis_worker
   ```

The agent loads the clinic profile from MongoDB on each call and injects it
into the receptionist prompt. The prompt version is stored in
`calls.agent_config.prompt`. If the profile is missing, the agent uses safe
defaults and says staff will confirm missing details.

## 5. Frontend

1. Install dependencies and build from `frontend/`:

   ```powershell
   npm ci
   npm run build
   ```

2. Serve `dist/` from a static host.
3. Proxy `/api/*` to the API service on the same origin.
4. Leave `VITE_API_URL` empty for the same-origin proxy. Set it only when the
   browser must call the API directly.

The patient call page is public at `/`. Staff sign in at `/admin/login`.

## 6. Post-deployment smoke test

1. `GET /api/health/live`, `GET /api/health`, and `GET /api/ready` return
   healthy.
2. Open `/` and start a call. Allow microphone access and speak one Hinglish
   sentence.
3. Ask "clinic ka address kya hai?" and confirm the answer matches the clinic
   profile.
4. Book a test appointment and confirm it appears under `/admin/appointments`.
5. Sign in as admin:
   - `/admin/live` shows the benchmark card.
   - `/admin/calls` loads the test call.
   - `/admin/latency` loads without errors.
   - `/admin/clinic` saves a change and the next call uses the new detail.
6. Confirm the admin cookie is `HttpOnly` and `Secure` in browser dev tools.
7. Confirm a public visit to `/admin/live` redirects to `/admin/login`.

## 7. Monitoring and operations

- API and agent worker health: check `/api/health/live`, `/api/health`, and
  worker logs separately.
- Sentry: set `SENTRY_DSN` for API exceptions.
- Request tracing: every API response has `X-Request-ID`.
- Rate limits: login is limited to 5/minute per IP; token generation to
  20/minute per IP. Limits are in-process, so use one API replica or add a
  Redis-backed limiter before horizontal scaling.
- Requeue a stuck analysis: `POST /api/calls/{call_id}/analyze` from the call
  log UI.
- Backups: enable Atlas continuous backups before real patient use.

## 8. Docker and CI

Build the API/agent image from `backend/`:

```powershell
docker build -t clinic-voice-agent .
docker run --env-file .env -p 8000:8000 clinic-voice-agent
```

The image starts Uvicorn with `--no-proxy-headers` so callers cannot spoof
`X-Forwarded-For`. Behind a trusted reverse proxy, override the command with
`--proxy-headers --forwarded-allow-ips=<proxy-ip>` and set
`TRUST_PROXY_HEADERS=true` so rate-limit keys use the real client IP.

Override the command for the agent worker or analysis worker:

```powershell
docker run --env-file .env clinic-voice-agent python agent.py start
docker run --env-file .env clinic-voice-agent python -m app.workers.analysis_worker
```

`.github/workflows/ci.yml` runs backend compile/tests/ruff, a Docker build,
and frontend test/lint/build on pushes to `main` and pull requests. Run the
same backend checks locally before deploying:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check app agent.py main.py tests scripts
```

```powershell
cd frontend
npm run lint
npm test
npm run build
```

## Troubleshooting

- **API fails at startup with "Invalid configuration"**: read the listed env
  names. `JWT_SECRET` is required and must be at least 32 characters.
- **Admin login succeeds but `/api/auth/me` returns 401**: check
  `COOKIE_SECURE`/`COOKIE_SAMESITE` and make sure the browser is using the same
  origin as the `/api` proxy.
- **CORS error**: add the exact frontend origin to `CORS_ORIGINS` (scheme and
  port must match). A wildcard is rejected because credentialed requests are
  enabled.
- **Agent cannot load clinic details**: run `scripts/seed_clinic.py` or save the
  profile in `/admin/clinic`.
- **Booking fails**: verify the MongoDB cluster supports transactions and that
  the connection string uses a replica set.
- **Frontend `/api` 404**: confirm the static host proxies `/api/*` to the API
  service.
