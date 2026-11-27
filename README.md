# Intel AI PC Arena

A touch-friendly 150-second laptop discovery game for the CMRIT × Intel Hackathon. The prototype is a web app with an optional FastAPI API and localhost hardware companion. It runs in sample mode without a runner.

## Project analysis and architecture

The project uses React, Vite, TypeScript, Framer Motion and Lucide icons in `frontend/`; FastAPI, Pydantic and SQLite in `backend/`; and an isolated localhost companion in `local-runner/`. See [architecture overview](docs/architecture/overview.md), [benchmark status](docs/benchmark-protocol/status.md), and [deployment database decision](docs/deployment-database.md).

## Run the frontend

```powershell
npm install
npm run dev
```

Open http://localhost:5173. The API is optional for the sample experience; when available, the UI uses it for sessions, preferences, mission receipts, recommendations, and handoff. Sample profile and fixture data is explicitly identified in the interface.

## Run the API (optional)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Run the API and frontend in separate terminals. Vite proxies `/api` to this server. The API uses local SQLite at `backend/arena.db` (override with `ARENA_DB_PATH`) or PostgreSQL when `DATABASE_URL` is configured. Vercel `/tmp` SQLite is ephemeral and unsuitable for durable shopper or associate state. See the [database deployment assessment](docs/deployment-database.md). To let the API call a local runner, set `LOCAL_RUNNER_URL=http://127.0.0.1:8765`; the current runner does not verify inference, so results remain `DEMO / NOT VERIFIED`.

## Run the local runner (optional)

```powershell
pip install -r local-runner/requirements.txt
uvicorn app:app --app-dir local-runner --port 8765
```

OpenVINO is optional. The runner reports available device identifiers when installed but does not claim execution: a known compatible model, fixed benchmark contract and validated telemetry are not included. Until those are configured, relay results stay `NOT VERIFIED`.

## Evidence and limitations

Bundled comparison fixtures are labelled `SAMPLE DATA`; they are not measurements. Retail catalogue prices are source snapshots, not live quotes or inventory. No historical verified benchmark database is bundled, so the interface reports missing comparable live data. The demo timer uses one session start-time anchor and persists customer state in browser storage; backend state is local SQLite unless a durable production database is configured.

## Development checks

```powershell
npm.cmd run build
python -m pytest backend/tests -q
node --test frontend/tests/session-persistence.test.mjs
npm.cmd run build
```

PostgreSQL support is implemented but has not been exercised against a live database in this workspace. No production database URL, Vercel project link, or deployment credentials were available during validation.
