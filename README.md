# Clinic Voice Agent

Real-time Hindi/Hinglish phone receptionist for a small clinic. A caller talks
to a LiveKit agent, the agent answers clinic FAQs, checks doctor availability,
books or reschedules appointments, and every call is stored for analysis and
latency benchmarking.

The project has two surfaces:

- **Public patient call page** at `/` - no login, starts a voice session.
- **Protected admin dashboard** under `/admin/*` - JWT cookie login, call log,
  appointments, clinic profile/FAQ editor, and latency dashboards.

## Architecture

```
Browser (React + LiveKit)          LiveKit Cloud               Sarvam
        |                               |                        |
        |-- join room + run_id -------->|                        |
        |                               |-- agent dispatch       |
        |                               |    (run_id metadata)   |
        |                        Python agent ------------------>| STT / LLM / TTS
        |                               |                        |
        |<---------- audio -------------|                        |
                                      |
                                   FastAPI
                                      |
                                   MongoDB Atlas
                             users / clinic / calls / call_turns /
                             slots / appointments / benchmark_runs
```

During a call, the agent keeps the LiveKit chat context across turns. If the
LLM errors or exceeds `LLM_TIMEOUT_SECONDS`, it logs the failure and speaks a
short Hinglish fallback instead of leaving the caller in silence. TTS streams
over Sarvam's WebSocket API and falls back to Sarvam's HTTP API if streaming
fails. TTS errors are logged and counted; repeated failures do not immediately
end the call.

Flow after a call ends:

1. `agent.py` writes the finished call and finalizes the transcript.
2. The analysis worker claims the call and asks Sarvam LLM for a short summary,
   sentiment, intent, follow-up, and compliance flags.
3. If the LLM call fails or is invalid, a deterministic rule-based analyzer is
   used. Analysis status is stored as `pending`, `running`, `completed`, or
   `failed` (with retry count and error).
4. Latency metrics from LiveKit are stored on `call_turns` and aggregated by
   `/api/analytics/latency`.

## Prerequisites

- Python 3.11+ (the repo has been run with 3.14 on Windows)
- Node.js 20+
- LiveKit Cloud project
- Sarvam API key
- MongoDB Atlas replica set (transactions are required for booking)

## Setup

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
# create backend/.env from .env.example and fill in
# LIVEKIT_*, SARVAM_API_KEY, MONGODB_URI, and JWT_SECRET
.\.venv\Scripts\python.exe scripts\seed_data.py
.\.venv\Scripts\python.exe scripts\seed_clinic.py
.\.venv\Scripts\python.exe scripts\create_admin.py --email admin@example.com
```

Frontend:

```powershell
cd frontend
npm install
# create frontend/.env from .env.example
```

`frontend/.env` can leave `VITE_API_URL` empty to use the Vite `/api` proxy.
If set, it must point at the API, e.g. `http://localhost:8000`.

## Run

Open three terminals from the repo root.

```powershell
# 1. API (also starts the post-call analysis worker)
cd backend
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

```powershell
# 2. LiveKit agent
cd backend
.\.venv\Scripts\python.exe agent.py dev
```

```powershell
# 3. Frontend
cd frontend
npm run dev
```

Open `http://localhost:5173` for the public patient page.
Open `http://localhost:5173/admin/login` and use the admin account created
above.

The agent supports barge-in: start speaking while it talks and it stops. Clinic
details are loaded from the `clinic` collection on each call, so changes in
`/admin/clinic` apply to the next conversation.

## Environment variables

See `backend/.env.example` for the full list. The important groups are:

- LiveKit: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`,
  `LIVEKIT_AGENT_NAME`
- Sarvam: `SARVAM_API_KEY`
- MongoDB: `MONGODB_URI`, `MONGODB_DATABASE`
- Auth: `JWT_SECRET` (32+ chars), `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`,
  `AUTH_COOKIE_NAME`, `COOKIE_SECURE`, `COOKIE_SAMESITE`
- Clinic: `CLINIC_TIMEZONE` (default `Asia/Kolkata`), `CORS_ORIGINS`
- STT: `STT_LANGUAGE`, `STT_STREAM_TYPE`, `STT_MODE`, `STT_ENDPOINTING`,
  `STT_TRANSCRIPTION_TIMEOUT` (`STT_ENDPOINTING` must stay `vad`; the agent
  uses Sarvam's server VAD and sends the active doctor roster as a terminology
  hint. Keyterm lists are not exposed by the current Sarvam plugin.)
- LLM: `LLM_MODEL` (default `sarvam-105b`), `LLM_TIMEOUT_SECONDS`
  (default `12.0`; on timeout the agent speaks a short Hinglish fallback),
  `LLM_MAX_TOKENS` (default `200`; caps long spoken replies)
- TTS: `TTS_LANGUAGE`, `TTS_MODEL`, `TTS_SPEAKER`, `TTS_PACE`,
  `TTS_SAMPLE_RATE` (default `24000`), `TTS_TIMEOUT_SECONDS` (default `8.0`),
  `TTS_MIN_BUFFER_SIZE`, `TTS_MAX_CHUNK_LENGTH`
- Session: `SESSION_MAX_UNRECOVERABLE_ERRORS` (default `10`; keeps the call
  alive through repeated provider failures before LiveKit closes it)
- VAD: `VAD_MIN_SPEECH_DURATION`, `VAD_MIN_SILENCE_DURATION`,
  `VAD_PREFIX_PADDING_DURATION`, `VAD_ACTIVATION_THRESHOLD`,
  `VAD_DEACTIVATION_THRESHOLD`
- Turn taking: `MIN_ENDPOINTING_DELAY`, `MAX_ENDPOINTING_DELAY`,
  `INTERRUPTION_MIN_DURATION`, `PREEMPTIVE_TTS`
- Analysis: `ANALYSIS_MODEL`, `ANALYSIS_MAX_ATTEMPTS`,
  `ANALYSIS_POLL_SECONDS`, `ANALYSIS_TIMEOUT_SECONDS`,
  `ANALYSIS_WORKER_ENABLED`, `ANALYSIS_TRANSCRIPT_CHARS`
- Operations: `LOG_LEVEL`, `SENTRY_DSN`, `SENTRY_ENVIRONMENT`,
  `RATE_LIMIT_ENABLED`, `TRUST_PROXY_HEADERS`

`Settings.validate()` checks required values and fails fast with a readable
list of invalid names at API and agent startup.

Do not commit `.env` files. The root `.gitignore` ignores them and keeps
`.env.example`.

## Data model

- `users`: admin accounts with Argon2 password hashes and roles
- `clinic`: single clinic profile/FAQ used by the agent prompt
- `calls`: one document per call with `run_id`, transcript, summary, analysis
  fields, booking outcome, `tool_calls`, `barge_in_count`, `speech_count`,
  `stt_error_count`, `stt_timeout_count`, `empty_transcript_count`,
  `llm_error_count`, `tts_error_count`
- `call_turns`: one document per transcript turn with stage latencies
  (`endpoint_latency_ms`, `stt_latency_ms`, `llm_latency_ms`,
  `tts_latency_ms`, `end_to_audio_ms`, `playback_latency_ms`)
- `benchmark_runs`: one document per benchmark run with call counts and status
- `slots` / `appointments` / `doctors`: clinic booking state

## API

Public:

- `GET /api/health`
- `GET /api/ready`
- `GET /api/generate-token` - LiveKit token. With `?run_id=baseline-1`, an
  admin session is required and the run id is copied into every call/turn.
- `POST /api/auth/login`
- `POST /api/auth/logout`

Admin (JWT cookie):

- `GET /api/auth/me`
- `GET /api/calls?page=1&page_size=20&run_id=baseline-1`
- `GET /api/calls/{call_id}`
- `POST /api/calls/{call_id}/analyze` - requeue a failed or pending analysis
- `GET /api/appointments?status=confirmed&doctor=Dr.%20Sharma&date=2026-11-02`
- `GET /api/doctors`
- `GET /api/clinic`
- `PUT /api/clinic`
- `GET /api/analytics/runs`
- `GET /api/analytics/latency?run_id=baseline-1`

## Frontend routes

- `/` - public patient call page
- `/admin/login` - admin sign in
- `/admin/live` - admin call page with benchmark run label
- `/admin/appointments` - patient bookings
- `/admin/calls` - call log and transcripts
- `/admin/clinic` - clinic profile and FAQ editor
- `/admin/latency` - benchmark latency dashboard

## Benchmark (20 calls)

Use a fixed test run so results are comparable.

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\benchmark.py start --label baseline
```

Copy the printed `run_id` into the **Test run label** field on the admin Live
call page, then complete the 20 calls in `benchmark-script.md`.

Check progress:

```powershell
.\.venv\Scripts\python.exe scripts\benchmark.py status --run-id <run_id>
```

Generate the report:

```powershell
.\.venv\Scripts\python.exe scripts\report_latency.py --run-id <run_id> --format both --output reports\<run_id>
```

Mark the run finished:

```powershell
.\.venv\Scripts\python.exe scripts\benchmark.py finish --run-id <run_id> --notes "baseline"
```

The report contains p50/p95/p99, min, max, sample counts per stage, booking
success rate, barge-in count, and the slowest calls. It also reports STT
provider errors, no-transcript timeouts, empty final transcripts, and the share
of calls affected by an STT failure. A fresh database has no benchmark numbers;
they must be collected with real calls.

Word error rate is not calculated automatically because calls are not recorded.
Accuracy is reviewed in the benchmark script using the named-phrase cases, while
runtime failures and transcription latency are measured automatically.

## Deployment

See [`docs/deployment.md`](docs/deployment.md) for Vercel + Render + MongoDB
Atlas + LiveKit Cloud. The repository includes:

- `backend/Dockerfile` and `backend/Dockerfile.agent`
- `frontend/Dockerfile` and `frontend/nginx.conf`
- `docker-compose.yml` for a local production-like stack
- `render.yaml` for Render Blueprint deployment
- `frontend/vercel.json` for the same-origin `/api` rewrite
- `.github/workflows/ci.yml`

## Tests and checks

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

```powershell
cd frontend
npm run lint
npm run build
```

## Known limitations

- Single clinic, not multi-tenant.
- No telephony or external CRM integration; MongoDB calls are the CRM.
- The benchmark script is manual; results depend on network and caller speech.
- LLM summaries can fail; the rule-based fallback keeps the pipeline usable.
- TTS fallback uses the same Sarvam provider over HTTP; a full Sarvam outage
  still affects both transports.
- LiveKit credentials and a real phone/audio environment are required for
  end-to-end voice validation.
- Public callers can start a session without login, so production deployments
  should keep token rate limits enabled and monitor usage.
