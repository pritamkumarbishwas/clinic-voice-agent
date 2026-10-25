# Clinic Voice Agent (Student Edition)

Real-time Hindi/Hinglish phone receptionist for a small clinic. A caller talks
to a LiveKit agent, the agent checks doctor availability, books or reschedules
appointments, and every call is stored for analysis and latency benchmarking.

This is a student edition: single clinic, no multi-tenant auth, manual
benchmark calls.

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
                             calls / call_turns / slots /
                             appointments / benchmark_runs
```

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
# LIVEKIT_*, SARVAM_API_KEY, MONGODB_URI
.\.venv\Scripts\python.exe scripts\seed_data.py
```

Frontend:

```powershell
cd frontend
npm install
# create frontend/.env from .env.example
```

`frontend/.env` only needs `VITE_API_URL` (default `http://localhost:8000`).
The browser gets the LiveKit URL and token from the backend token endpoint, so
LiveKit secrets stay on the server.

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

Open `http://localhost:5173`, start a call, and speak Hindi, Hinglish, or
English. The agent supports barge-in: start speaking while it talks and it
stops.

## Environment variables

See `backend/.env.example` for the full list. The important groups are:

- LiveKit: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`,
  `LIVEKIT_AGENT_NAME`
- Sarvam: `SARVAM_API_KEY`
- MongoDB: `MONGODB_URI`, `MONGODB_DATABASE`
- Clinic: `CLINIC_TIMEZONE` (default `Asia/Kolkata`)
- STT: `STT_LANGUAGE`, `STT_STREAM_TYPE`, `STT_MODE`, `STT_ENDPOINTING`
- LLM: `LLM_MODEL` (default `sarvam-105b`)
- TTS: `TTS_LANGUAGE`, `TTS_MODEL`, `TTS_SPEAKER`, `TTS_PACE`,
  `TTS_MIN_BUFFER_SIZE`, `TTS_MAX_CHUNK_LENGTH`
- Turn taking: `MIN_ENDPOINTING_DELAY`, `MAX_ENDPOINTING_DELAY`,
  `INTERRUPTION_MIN_DURATION`, `PREEMPTIVE_TTS`
- Analysis: `ANALYSIS_MODEL`, `ANALYSIS_MAX_ATTEMPTS`,
  `ANALYSIS_POLL_SECONDS`, `ANALYSIS_TIMEOUT_SECONDS`,
  `ANALYSIS_WORKER_ENABLED`, `ANALYSIS_TRANSCRIPT_CHARS`

Do not commit `.env` files. The root `.gitignore` ignores them and keeps
`.env.example`.

## Data model

- `calls`: one document per call with `run_id`, transcript, summary, analysis
  fields, booking outcome, `tool_calls`, `barge_in_count`, `speech_count`
- `call_turns`: one document per transcript turn with stage latencies
  (`endpoint_latency_ms`, `stt_latency_ms`, `llm_latency_ms`,
  `tts_latency_ms`, `end_to_audio_ms`, `playback_latency_ms`)
- `benchmark_runs`: one document per benchmark run with call counts and status
- `slots` / `appointments` / `doctors`: clinic booking state

## API

- `GET /api/health`
- `GET /api/generate-token?run_id=baseline-1` - LiveKit token and dispatch
  metadata. The run id is copied into every call and turn.
- `GET /api/calls?page=1&page_size=20&run_id=baseline-1`
- `GET /api/calls/{call_id}`
- `POST /api/calls/{call_id}/analyze` - requeue a failed or pending analysis
- `GET /api/analytics/runs`
- `GET /api/analytics/latency?run_id=baseline-1`

## Benchmark (20 calls)

Use a fixed test run so results are comparable.

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\benchmark.py start --label baseline
```

Copy the printed `run_id` into the **Test run label** field on the Live call
page, then complete the 20 calls in `benchmark-script.md`.

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
success rate, barge-in count, and the slowest calls. A fresh database has no
benchmark numbers; they must be collected with real calls.

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

- No authentication or multi-clinic tenancy.
- The benchmark script is manual; results depend on network and caller speech.
- LLM summaries can fail; the rule-based fallback keeps the pipeline usable.
- LiveKit credentials and a real phone/audio environment are required for
  end-to-end voice validation.
