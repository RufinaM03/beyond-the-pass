# Beyond the Pass

Explore prioritization of passed inspections with brake advisories for follow-up checks. The target is recorded brake failure at the next qualifying routine inspection, not accidents, breakdowns or present roadworthiness. Intervening repairs and unresolved status are not observed in the source data.

## Current status

Phase 4 complete locally: FastAPI serves a production React/Vite dashboard backed by the unchanged trusted model and **200-case historical demonstration**. The separate saved evaluation remains **936 examples (76 positive, 860 negative)**, trained on 902 examples; the original 705/183 reference is unchanged. **Recurrence prediction remains unvalidated**, probabilities are not established as reliable, and no production winner is declared. See [Phase 4 checks/startup](docs/PHASE4_REPORT.md), [the exploratory report](docs/PHASE3_REPORT.md) and [API/explanation contract](docs/API_CONTRACT.md). No retraining, data downloads or raw rescans occurred. No container, CI/CD workflow or cloud deployment exists; no AWS resources have been created.

Read [PROJECT_STATE.md](PROJECT_STATE.md) first when resuming, then [DATA_CONTRACT.md](DATA_CONTRACT.md) and [DECISIONS.md](DECISIONS.md). See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the proposed ECS design and [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) for prerequisites and remediation.

## Local startup

Phase 5 packaging/CI implementation and Docker readiness are tracked in [the packaging report](docs/PHASE5_REPORT.md). Use `scripts/container.ps1` to stage, validate, build and smoke a bounded release; never build directly from raw data directories. Real and synthetic fixture artifacts are explicitly separated. Docker/cloud execution status must be read from the checkpoint, not inferred from the Dockerfile or workflow.

From `D:\2026-27\PROJECTS\BEYOND_THE_PASS` in PowerShell, using the existing D:-resident Python **3.12** virtual environment and approved ignored artifacts:

```powershell
.\scripts\app.ps1 -Command Setup    # first installation only; pinned Python + npm ci
.\scripts\app.ps1 -Command Build
.\scripts\app.ps1 -Command Serve
```

Open [the dashboard](http://127.0.0.1:8000), [readiness](http://127.0.0.1:8000/api/ready) or [OpenAPI schema](http://127.0.0.1:8000/api/openapi.json). Stop with Ctrl+C. No Vite development server is required. Scripts set temporary/cache/SQLite/Node paths on D: per process and restore the environment afterward. Missing or mismatched trusted artifacts cause 503 readiness, never a substitute model. Generated artifacts are not in Git; a clean checkout needs the explicitly approved release matching `docs/serving_release.json` before real integration checks can pass. Do not fetch untrusted bundles or run training to make startup pass.

```powershell
.\scripts\app.ps1 -Command Test          # synthetic isolated fixtures + frontend count formatting
.\scripts\app.ps1 -Command Integration   # approved real 200-case release, no fitting
.\scripts\app.ps1 -Command BrowserTest   # separate terminal, production server already running
```

Browser checks use `playwright-core` with installed Chrome, not a downloaded browser. Optional process variables `CHROME_PATH` and `BTP_BASE_URL` override executable/URL; `.env` is not auto-loaded. Browser-only simulated 503 is clearly identified, not an evaluation source.

## Layout

- `pipeline/`: local chunked ingestion, validation, Parquet processing, and training.
- `backend/`: FastAPI endpoints and built frontend serving.
- `frontend/`: React/Vite dashboard.
- `tests/`: automated checks, with clearly identified synthetic fixtures where needed.
- `infra/`: standard CloudFormation templates after plan approval.
- `data/`: ignored raw and processed datasets.
- `artifacts/`: ignored models, evaluation output, and bounded SQLite snapshot.

The pipeline, exploratory model, trusted inference, backend and dashboard are implemented. Infrastructure remains deferred. `requirements-app.lock` includes unchanged model/data locks; `frontend/package-lock.json` pins frontend and browser-check dependencies. Existing acquisition/training commands are retained for provenance, **not application startup**. Serving never fits, refreshes or downloads data. The demo contains index-only current inputs and aggregate prior history, not dated inspection rows or individual advisory text. It is explicitly historical as of 2024-12-31, not a current fleet or present-roadworthiness assessment.

## Data workflow

See [acquisition commands and source decisions](docs/ACQUISITION.md). `scripts/data.ps1` configures caches and temporary paths on D: per process. `CheckSources` detects catalogue/file changes without replacing data or training. Raw archives, generated Parquet/SQLite, and detailed quality reports remain ignored by Git. Counts and limitations belong in [the quality report](docs/QUALITY_REPORT.md), with detailed local evidence linked from `PROJECT_STATE.md`.

## Scope and safeguards

Training runs locally. The eventual release is one image containing FastAPI, the built React application, a trusted model, and a small read-only SQLite demonstration snapshot. Cloud infrastructure requires an approved concrete plan and cost estimate before provisioning. No domain is owned yet; certificate and DNS setup remain a deployment decision, without blocking local development.
