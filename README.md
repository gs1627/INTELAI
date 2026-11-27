# Intel AI PC Arena

A touch-friendly 150-second laptop discovery game for the CMRIT × Intel Hackathon. The prototype is a web app with an optional FastAPI API and localhost hardware companion. It runs in sample mode without a runner.

## Project analysis and architecture

The supplied workspace was empty (no app, framework, assets, or concept report PDF). The project uses React, Vite, TypeScript, Framer Motion and Lucide icons in `frontend/`; FastAPI, Pydantic and SQLAlchemy in `backend/`; and an isolated localhost companion in `local-runner/`. See [architecture overview](docs/architecture/overview.md) and [benchmark status](docs/benchmark-protocol/status.md).

## Run the frontend

```powershell
npm install
npm run dev
```

Open http://localhost:5173. The complete game works without either Python service. Its blind pick, five personas, foreground checklist, proof receipt, reality reveal, same-brand recommendations and comparison view are interactive.

## Run the API (optional)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

The API defaults to a local SQLite `arena.db`. Configure `ARENA_DATABASE_URL`, `ARENA_CORS_ORIGINS`, and `ARENA_ADMIN_TOKEN` through environment variables for deployment. Never expose the local runner to the public internet.

## Run the local runner (optional)

```powershell
pip install -r local-runner/requirements.txt
uvicorn app:app --app-dir local-runner --port 8765
```

OpenVINO is optional. The runner reports available device identifiers when installed but does not claim execution: a known compatible model, fixed benchmark contract and validated telemetry are not included. Until those are configured, relay results stay `NOT VERIFIED`.

## Evidence and limitations

All bundled laptop and comparison fixtures are labelled `SAMPLE DATA`; fixture values are invented UI examples, not measurements. No historical verified benchmark database is bundled, so the interface reports missing comparable live data. The prototype does not implement admin catalogue editing, inventory integration, a compatible AI model, cloud hosting, a verified NPU execution path, or a production kiosk reset policy. The demo timer runs for up to 150 seconds but stage navigation remains customer-controlled and can move directly to later stages.

## Development checks

```powershell
npm run build
python -m pytest backend/tests
```
