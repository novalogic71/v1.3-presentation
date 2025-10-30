# Repository Guidelines

## Project Structure & Module Organization
- `fastapi_app/` – FastAPI backend (entry `main.py`), routes under `app/api/v1/`, config in `app/core/`.
- `web_ui/` – Flask server + browser UI (`index.html`, `app.js`, waveform/engine scripts).
- `sync_analyzer/` – Core sync analysis logic and CLI.
- Outputs: `ui_sync_reports/`, `repaired_sync_files/`.
- Scripts: `start_all.sh` (API+UI), `web_ui/start_ui.sh` (UI only), `tests/` for pytest suites.

## Build, Test, and Development Commands
- Create env: `python -m venv venv && source venv/bin/activate`
- Install deps: `pip install -r requirements.txt` (and `pip install -r fastapi_app/requirements.txt` if needed)
- Run API (dev): `uvicorn fastapi_app.main:app --reload --host 0.0.0.0 --port 8000`
- Run UI: `python web_ui/server.py` (opens at `http://localhost:3002`)
- All‑in‑one: `bash ./start_all.sh`
- Tests: `pytest -q` (fast fail: `pytest --maxfail=1 -q`)
- Format/Lint: `black .` and `flake8 fastapi_app app sync_analyzer web_ui`

## Coding Style & Naming Conventions
- Python: Black (88 cols), 4‑space indents, grouped imports, prefer type hints.
- JavaScript: 2–4 spaces per file, `const/let`, small focused functions.
- Naming: snake_case (Python), camelCase (JS vars/functions), PascalCase (JS classes), kebab‑case (DOM/CSS).

## Testing Guidelines
- Framework: `pytest` (+ `pytest-asyncio` for async).
- Location: tests mirror packages under `tests/`, files named `test_*.py`.
- Scope: cover new endpoints, critical utils, sync math; keep tests deterministic.
- Run locally before PR: `pytest -q`.

## Commit & Pull Request Guidelines
- Commits: concise, imperative subject (e.g., `api: add /files/proxy-audio`), optional short rationale for non‑trivial changes.
- PRs: include context, example curl/screenshots (API/UI), linked issues, and notes for breaking changes or manual steps (env vars, migrations).

## Security & Configuration Tips
- Restrict I/O to `MOUNT_PATH` (see `fastapi_app/app/core/config.py`, `web_ui/server.py`); validate user inputs.
- Ensure `ffmpeg/ffprobe` on PATH. Configure CORS via `ALLOWED_ORIGINS` when API and UI are separate.
- Performance/long files/GPU: `USE_GPU=true`; `LONG_FILE_THRESHOLD_SECONDS` (default 180); optional `LONG_FILE_GPU_BYPASS_MAX_SECONDS`.
- Local‑only AI: `HF_LOCAL_ONLY=1`; provide `AI_WAV2VEC2_MODEL_PATH` or `YAMNET_MODEL_PATH`; optional `AI_MODEL_CACHE_DIR`.

## Agent‑Specific Notes
- Keep changes minimal and focused; match existing style.
- Don’t fix unrelated issues. Update docs when behavior changes.
- Prefer fast file searches with `rg`; read files in ≤250‑line chunks.
