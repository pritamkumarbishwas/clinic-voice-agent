# Deployment guide

This repository does not include provider-specific CI/CD, Docker, or hosting
configuration. Deploy the same runtime pieces on any platform that supports them:

- a static frontend built from `frontend/`
- the FastAPI service in `backend/`
- the LiveKit agent worker in `backend/agent.py`
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

Indexes are created automatically at API/agent startup by `app/database.py`.

## 3. API service

1. Install `backend/requirements.txt` in a Python environment.
2. Run the API from `backend/`:

   ```powershell
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

3. Health check paths: `/api/health` and `/api/ready`.
4. Set the shared environment variables for both the API and agent worker:
   - `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
   - `LIVEKIT_AGENT_NAME=clinic-receptionist`
   - `SARVAM_API_KEY`
   - `MONGODB_URI`, `MONGODB_DATABASE=clinic_voice_ai`
   - `CLINIC_TIMEZONE=Asia/Kolkata`
   - `JWT_SECRET` (32+ characters)
   - `JWT_ALGORITHM=HS256`, `JWT_EXPIRE_MINUTES=480`
   - `AUTH_COOKIE_NAME=clinic_access_token`
   - `COOKIE_SECURE=true`, `COOKIE_SAMESITE=lax`
   - `LOG_LEVEL=INFO`, `RATE_LIMIT_ENABLED=true`
   - `TRUST_PROXY_HEADERS=true` when behind a trusted reverse proxy
   - optional `SENTRY_DSN`, `SENTRY_ENVIRONMENT=production`
5. API-only variables:
   - `ANALYSIS_WORKER_ENABLED=true`
   - `CORS_ORIGINS` only if the browser calls the API cross-origin

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

1. `GET /api/health` and `GET /api/ready` return healthy.
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

- API and agent worker health: check `/api/health` and worker logs separately.
- Sentry: set `SENTRY_DSN` for API exceptions.
- Request tracing: every API response has `X-Request-ID`.
- Rate limits: login is limited to 5/minute per IP; token generation to
  20/minute per IP.
- Requeue a stuck analysis: `POST /api/calls/{call_id}/analyze` from the call
  log UI.
- Backups: enable Atlas continuous backups before real patient use.

## 8. Tests

CI is not configured in the repository. Run the documented checks before
deploying:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
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
  port must match).
- **Agent cannot load clinic details**: run `scripts/seed_clinic.py` or save the
  profile in `/admin/clinic`.
- **Booking fails**: verify the MongoDB cluster supports transactions and that
  the connection string uses a replica set.
- **Frontend `/api` 404**: confirm the static host proxies `/api/*` to the API
  service.
