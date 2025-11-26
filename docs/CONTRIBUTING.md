# Repository Guidelines

Concise contributor guide for the Professional Audio Sync Analyzer. Use this to set up, develop, and submit changes consistently.

## Project Structure & Module Organization
- `fastapi_app/`: FastAPI backend (entry `main.py`), routes under `app/api/v1`, config in `app/core`.
- `web_ui/`: Flask server + frontend (`index.html`, `app.js`, `waveform-visualizer.js`, `core-audio-engine.js`).
- `sync_analyzer/`: Core analysis CLI and utilities.
- Outputs: `ui_sync_reports/`, `repaired_sync_files/`.
- Scripts: `start_all.sh` (API+UI), `web_ui/start_ui.sh` (UI only).

## Build, Test, and Development Commands
- Env + deps: `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt` (and `pip install -r fastapi_app/requirements.txt` if needed).
- Run API (dev): `uvicorn fastapi_app.main:app --reload --host 0.0.0.0 --port 8000`.
- Run UI: `python web_ui/server.py` (http://localhost:3002).
- All-in-one: `bash ./start_all.sh`.
- Lint/format: `black .` and `flake8 fastapi_app app sync_analyzer web_ui`.
- Tests: `pytest -q` (or `pytest --maxfail=1 -q`).

## Coding Style & Naming Conventions
- Python: Black (88 cols), 4-space indent, grouped imports; Flake8 clean; prefer type hints.
- JavaScript: 2–4 spaces per file convention, `const/let`, small functions; `camelCase` (vars/functions), `PascalCase` (classes).
- Paths/IDs: snake_case (Python), kebab-case (DOM data keys, CSS classes).

## Testing Guidelines
- Framework: pytest (+ pytest-asyncio for async).
- Location: `tests/` mirroring packages; files `test_*.py`.
- Coverage focus: new endpoints, critical utils, sync math. Run tests locally before PR.

## Commit & Pull Request Guidelines
- Commits: concise, imperative subject (e.g., `api: add /files/proxy-audio`); include brief rationale if non-trivial.
- PRs: description with context, curl/screenshots for API/UI, linked issues, note breaking changes and manual steps (env vars, migrations).

## Security & Configuration Tips
- Restrict file I/O to `MOUNT_PATH` (see `fastapi_app/app/core/config.py`, `web_ui/server.py`). Validate inputs.
- Ensure `ffmpeg/ffprobe` on PATH for proxying/analysis. Configure CORS (`ALLOWED_ORIGINS`) when hosting UI and API separately.

