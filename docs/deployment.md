# Deployment guide

Target setup:

- Frontend: Vercel
- API + analysis worker: Render
- LiveKit agent worker: Render background worker
- Database: MongoDB Atlas
- Voice: LiveKit Cloud + Sarvam

The browser talks to Vercel. Vercel rewrites `/api/*` to the Render API so the
admin session cookie stays on the same origin. The LiveKit agent connects to
LiveKit Cloud and MongoDB directly; it does not serve HTTP.

## 1. Rotate local secrets first

The repository has been used with real local credentials. Before deploying,
rotate:

- LiveKit API key/secret
- Sarvam API key
- MongoDB database user password
- Any old JWT secret

Never commit `backend/.env`, `frontend/.env`, or real keys in `render.yaml`.

Generate a production JWT secret:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

## 2. MongoDB Atlas

1. Create an Atlas cluster (a paid tier is recommended because booking uses
   transactions; a free shared cluster may not support them).
2. Create a database user with read/write access to `clinic_voice_ai`.
3. Add Render egress IPs to the Atlas IP access list, or use a VPC/private
   endpoint. `0.0.0.0/0` is acceptable only for a temporary demo.
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
`app/database.py`.

## 3. Render API service

1. Create a new Blueprint from this repository, or create the services manually
   from `render.yaml`.
2. The API service uses `backend/Dockerfile` and exposes port `8000`.
3. Health check path: `/api/health`.
4. Set the shared environment variables (Render env var group
   `clinic-voice-shared`):
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
   - `TRUST_PROXY_HEADERS=true` (Render/Vercel forward client IPs)
   - optional `SENTRY_DSN`, `SENTRY_ENVIRONMENT=production`
5. API-only variables:
   - `ANALYSIS_WORKER_ENABLED=true`
   - `CORS_ORIGINS=https://your-clinic.vercel.app`
6. Deploy and confirm `https://YOUR-RENDER-API.onrender.com/api/health`
   returns `{"status":"healthy","database":"ok"}`.

`COOKIE_SAMESITE=lax` works because Vercel proxies `/api` on the same origin.
If you call the Render API directly from a different site, use
`COOKIE_SAMESITE=none` and `COOKIE_SECURE=true` instead.

## 4. Render agent worker

1. Add a Render background worker using `backend/Dockerfile.agent`.
2. Use the same shared env var group as the API.
3. Set `ANALYSIS_WORKER_ENABLED=false` so only the API processes post-call
   analysis.
4. The worker command is `python agent.py start`.
5. Check Render logs for `registered worker` / LiveKit connection messages.

The agent loads the clinic profile from MongoDB on each call and injects it
into the receptionist prompt. If the profile is missing, it uses safe defaults
and the agent says staff will confirm missing details.

## 5. Vercel frontend

1. Import the repository into Vercel.
2. Root directory: `frontend`.
3. Framework preset: Vite.
4. Build command: `npm run build`; output directory: `dist`.
5. Do not set `VITE_API_URL` for the Vercel build. An empty value makes the
   browser call `/api/*` on the Vercel domain, which is what the rewrite needs.
6. Edit `frontend/vercel.json` and replace
   `https://YOUR-RENDER-API.onrender.com` with the real Render API URL.
7. Deploy. Open the Vercel URL; the patient call page is public at `/`.
8. Sign in at `/admin/login`.

If you prefer a cross-origin API instead of the rewrite, set
`VITE_API_URL=https://YOUR-RENDER-API.onrender.com` in Vercel, add the Vercel
origin to `CORS_ORIGINS`, and switch the cookie to `SameSite=None; Secure`.

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

- Render health check: `/api/health` (database ping included).
- Render logs: API and agent worker separately.
- Sentry: set `SENTRY_DSN` for API exceptions.
- Request tracing: every API response has `X-Request-ID`.
- Rate limits: login is limited to 5/minute per IP; token generation to
  20/minute per IP.
- Requeue a stuck analysis: `POST /api/calls/{call_id}/analyze` from the call
  log UI.
- Backups: enable Atlas continuous backups before real patient use.

## 8. Docker Compose (optional local production-like test)

```powershell
docker compose up --build
```

Then open `http://localhost:8080`. The compose stack starts a single-node Mongo
replica set, API, analysis worker, agent, and nginx frontend. It still needs
real LiveKit and Sarvam credentials in `backend/.env`.

## 9. CI

`.github/workflows/ci.yml` runs backend tests and frontend lint/build on pushes
and pull requests. It does not need cloud credentials.

## Troubleshooting

- **API fails at startup with "Invalid configuration"**: read the listed env
  names. `JWT_SECRET` is required and must be at least 32 characters.
- **Admin login succeeds but `/api/auth/me` returns 401**: check
  `COOKIE_SECURE`/`COOKIE_SAMESITE` and make sure the browser is using the
  Vercel URL, not the Render API URL directly.
- **CORS error**: add the exact frontend origin to `CORS_ORIGINS` (scheme and
  port must match).
- **Agent cannot load clinic details**: run `scripts/seed_clinic.py` or save the
  profile in `/admin/clinic`.
- **Booking fails**: verify the Atlas cluster supports transactions and that
  the connection string uses a replica set.
- **Vercel `/api` 404**: update the rewrite destination in
  `frontend/vercel.json`.
