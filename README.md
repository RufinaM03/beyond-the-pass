# Beyond the Pass

Explore prioritization of passed inspections with brake advisories for follow-up checks. The target is recorded brake failure at the next qualifying routine inspection, not accidents, breakdowns or present roadworthiness. Intervening repairs and unresolved status are not observed in the source data.

## Current status

AWS demonstration: [open the dashboard](https://d1qxms20novn1p.cloudfront.net). **On 21 October the user superseded the old manual cleanup deadline and requested leaving the service running while deploying Try Prediction and implementing CD. There is no automatic expiration or teardown.** Approved CloudFront viewer HTTPS → HTTP ALB → one ECS Fargate task. Ongoing hosting remains billable (approximately $1.57/day under documented assumptions, not a cap). Resource/cost details: [deployment report](docs/PHASE6_REPORT.md); current rollout/CD evidence: [CD report](docs/CD_IMPLEMENTATION_REPORT.md).

**Minimum hosting window:** user requests at least two weeks from22October2026IST, through at least **5November2026 00:01:05IST**. This is not an automatic deletion deadline; later stop/delete needs explicit instruction. Approximately$22before tax for14days using the existing low-traffic estimate; actual costs may vary. No new services or budget-alert changes.

**Try Prediction is live**, alongside the preserved historical queue and evaluation. [Verified deployment39649274769](https://github.com/RufinaM03/beyond-the-pass/actions/runs/39649274769) uses exact CI-passed6578185, an immutable Linux amd64 image, and a Task/Service-only CloudFormation update. Eight manual-prediction and nine historical queue/case/evaluation browser checks pass against the public HTTPS endpoint. Current CD evidence and rollback commands: [CD report](docs/CD_IMPLEMENTATION_REPORT.md), [operations](docs/CONTINUOUS_DEPLOYMENT.md).

**Automatic CD is enabled and verified:** successful main [CI39650491631](https://github.com/RufinaM03/beyond-the-pass/actions/runs/39650491631) automatically triggered [successful OIDC deployment39650767514](https://github.com/RufinaM03/beyond-the-pass/actions/runs/39650767514). No AWS credentials or real datasets are needed for PR CI; no static AWS keys are stored in GitHub. Same-SHA replay reuses the immutable image and verifies health without a redundant rollout.

Latest ordinary-main-push release **65bbbea** also passes [exact CI39652560796](https://github.com/RufinaM03/beyond-the-pass/actions/runs/39652560796) → [automatic rolling deployment39652855104](https://github.com/RufinaM03/beyond-the-pass/actions/runs/39652855104), final stack UPDATE_COMPLETE/task:6/healthy public inference. Docker build validation now uses the same approved Haswell kernel as serving, without relaxing numerical agreement. Latest CI106Python/4frontend/2synthetic crypto checks pass; real artifacts remain unchanged.

**200 historical demo cases** remain separate from the **936-example saved evaluation (76 positive, 860 negative)**. Real-container/public prediction agreement, deterministic ranking and unchanged saved evaluation pass. **106 Python unit tests / 4 frontend tests / 2 synthetic crypto tests** and [release CI](https://github.com/RufinaM03/beyond-the-pass/actions/runs/39652560796) pass; CI also runs separate offline infrastructure and synthetic fixture-container checks without AWS credentials or DVSA downloads. Original model/cohort/metrics/versions unchanged; **recurrence prediction and calibration remain unvalidated**. No retraining, acquisition or source rescans. See [API contract](docs/API_CONTRACT.md) and [packaging](docs/PHASE5_REPORT.md).

Read [PROJECT_STATE.md](PROJECT_STATE.md) first when resuming, then [DATA_CONTRACT.md](DATA_CONTRACT.md) and [DECISIONS.md](DECISIONS.md). See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the proposed ECS design and [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) for prerequisites and remediation.

## Local startup

### Try a prediction (local and AWS)

Open [the live prediction page](https://d1qxms20novn1p.cloudfront.net/predict), or [the local page](http://127.0.0.1:8000/predict) after startup. Enter age at inspection, recorded **miles**, brake advisory count and total advisory count, and confirm the Class 4 / passed normal inspection scope. Optional inspection date only shows the nominal 9–15-calendar-month observation window. Missing age/mileage remain missing, not zero. Results show actual model contributions/imputation and extrapolation warnings; they are not calibrated failure percentages or safety assessments. No submission storage, personal details, queue rank or saved-evaluation changes. Illustrative inputs are explicitly not historical records. Details/checks: [manual prediction report](docs/MANUAL_PREDICTION_REPORT.md).

```powershell
$env:BTP_BASE_URL='http://127.0.0.1:8000'; $env:BTP_VERIFY_TARGET='local'
node frontend/scripts/manual-browser-check.mjs
```

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
