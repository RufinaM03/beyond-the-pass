# Phase 4: verified local API and dashboard

Completed 2026-10-19. One agent; no retraining, source downloads, raw-archive scans, cohort changes, Docker or AWS work. Existing pipeline code, data/model locks, release versions and frozen artifact hashes preserved.

## Actual artifacts inspected

Verified `btp-exploratory-v1/feature-schema.json` and SQLite table definitions plus representative actual input/prediction/history records. Three tables: metadata, followup_queue and descriptive_history. **200 cases**, all scored; unique opaque 16-hex case ID is an index inspection, not a vehicle ID. Case dates remain 2022-01-12–2024-12-28, historical as of 2024-12-31. Four current features only. History is aggregate prior counts/duration, not a dated timeline or individual item text. This export limitation is documented in the API and UI; no artifacts were expanded or regenerated to disguise it.

Model/manifest trust anchor remains `56846f43cfc8e23f809d16b27d85b144a8d634f8fa42870d2e6f59df7531fa14`. `pipeline.verification` rechecked 6,642 preserved labels, 902-row training-only preprocessing, exact 936 saved predictions/aggregate metrics, 200 snapshot predictions, read-only enforcement and original implementation hashes. No fit operation was used (synthetic isolated training fixtures remain test-only).

## Implemented boundary

- FastAPI health/readiness/versions, bounded case pagination/date filtering/detail/prediction, ranked capacity queue, saved evaluation and methodology. Production React build served on the same origin; API/missing assets do not fall through to SPA HTML.
- Trusted checksums and exact dependency/Python versions before deserialization. Explicit feature-schema/version checks and exact stored-prediction agreement for all 200 cases before readiness. No uploads or user-supplied code; no inference reimplementation.
- SQLite `mode=ro&immutable=1`, `query_only=ON`, short-lived per-request connections, parameterized queries. Limit 1–100; offset 0–10,000; capacity 0–500; validated ISO date range; prediction body bounded to 16 KiB. Unknown case 404, invalid/unsupported 422, insufficient 200 with null score, unavailable release 503.
- Score descending/case ID ascending; no labels/history in ranking. Full-precision score and exact logistic terms preserved; display rounds only. Descriptive recurrence, input imputation/extrapolation, left-truncated history, historical/stale scope and non-safety limitations are visible.
- Overview, follow-up capacity/pagination, case detail/current advisories/aggregate history/all explanation terms, saved evaluation/baselines/fixed capacity bars, methodology/timeline/artifact identity/model card. Navy/teal/amber, responsive tables, labeled controls, keyboard focus and loading/empty/error/insufficient states.

## Evidence, not placeholder metrics

Demo **200 historical cases** and evaluation **936 examples / 76 positive / 860 negative** stay separate. Evaluation displays saved constant/count/logistic comparisons and only saved 10/20/30% points. Precision/recall/prevalence derive from observed counts. At 30% logistic selects 281: **35 positives / 246 negatives**, recall 35/76 = 46.1%, precision 35/281 = 12.5%. No interpolation, cohort recomputation or invented safety bands. Actual primary vehicle overlap is zero; unseen subset is not independent confirmation. Recurrence's predictive value remains unvalidated.

## Checks actually performed

- Existing 40 tests preserved; 11 synthetic API tests added: **51 Python tests pass**. Frontend **2 count/formatting tests pass**. `pip check`: no broken requirements. npm installation audit: zero vulnerabilities reported (not a comprehensive security audit).
- Real approved-artifact integration: **200 exact HTTP/direct/stored prediction agreements**, complete explanation reconstruction, deterministic ranking/pagination, index history boundary, immutable evaluation and SPA/API/asset routing. No row-level outcome source is joined by the API.
- Production `npm run build` succeeds: about 249 kB JS / 12 kB CSS uncompressed, with lockfile. Served by Uvicorn at `http://127.0.0.1:8000`, not Vite dev mode.
- Installed Chrome via pinned `playwright-core`: overview → capacity 40→25 → pagination → overcapacity 500 capped to 200 → real case → aggregate history and all explanation terms → full 936-example evaluation → saved 30% point. Deep-link refresh, 390px no page-level horizontal overflow and zero-capacity empty state checked. A separate **synthetic browser-only 503** checked retry/error display. Nine flow checks pass; zero unexpected browser errors. Screenshots visually inspected for overview, evaluation and mobile queue.
- Local browser evidence: `artifacts/phase4-browser/checks.json`, `overview.png`, `queue.png`, `case.png`, `evaluation.png`, `mobile-queue.png`. Synthetic test log: `data/tmp/phase4-tests.log`. Real release recheck: `data/tmp/phase4-release-verification.log` and existing ignored `artifacts/evaluations/btp-exploratory-v1/release-verification.json`.

## Reproduce on this machine

From `D:\2026-27\PROJECTS\BEYOND_THE_PASS`:

```powershell
.\scripts\app.ps1 -Command Setup       # only if dependencies absent/changed; npm ci
.\scripts\app.ps1 -Command Build
.\scripts\app.ps1 -Command Test
.\scripts\app.ps1 -Command Integration
.\scripts\data.ps1 -Command Verify     # preserved real artifact/cohort checks, no fitting
.\scripts\app.ps1 -Command Serve       # keep this terminal running; Ctrl+C to stop
# In a second terminal:
.\scripts\app.ps1 -Command BrowserTest
```

Dashboard `http://127.0.0.1:8000`; readiness `/api/ready`; versions `/api/versions`; queue `/api/queue?capacity=40`; saved evaluation `/api/evaluation`; OpenAPI `/api/openapi.json`. Interactive CDN-backed Swagger/Redoc are disabled to keep runtime UI offline and compatible with the self-only content security policy. No authentication is implemented: bind to loopback for local work, do not publicly expose this research demo before deployment/security review. Readiness concerns trusted artifacts; missing frontend build gives 503 on page routes. `.env` is not auto-loaded. Use `-Port` for Serve and set process `BTP_BASE_URL` for browser checks on another port. Browser executable override `CHROME_PATH` must point to an existing installed Chrome-compatible browser; no browser download is required.

## Resource and tooling observations / remaining issues

Before implementation: D: 60.34 GiB free, available RAM about 3.61 GiB and commit headroom about 2.09 GiB. Subsequent artifact verification: peak process working set **184,692,736 bytes (~176 MiB)**, peak private commit 179,122,176 bytes; D: 64,513,675,264 bytes free, RAM 3,589,476,352 bytes and commit headroom 1,592,410,112 bytes at that check. These are process-specific observations, not a browser/build total-memory guarantee. Python 3.12.7, Node 24.15.0, npm 11.1.0. All new caches/scratch/Node/browser temporary profiles/generated output stayed on D:; scripts restore process settings, not system-wide settings.

Desktop CUA and node-repl both failed before initialization with the same `failed to write kernel assets ... path specified` error; this was a tooling initialization/path failure, not the application. Used CLI Playwright with already installed Chrome, without downloading a browser. First browser run exposed a missing favicon request; added an inline SVG favicon and reran successfully. First npm prefix attempt resolved the wrong package directory; used explicit frontend working directory. Build warning from an empty CSS import was removed. No failed checks were weakened.

Nonblocking: Starlette emits a TestClient/httpx deprecation notice; the pinned HTTPX transport works and all tests pass. Adopt a replacement test transport in a later dependency update, not by changing frozen model dependencies here. Aggregate-only history is the approved export's limit, not a missing database join. Calibration, recurrence prediction and production readiness remain unestablished. Ignored approved artifacts must be delivered explicitly for a clean checkout; future image packaging is not yet implemented. No Docker troubleshooting, AWS resources, deployment claims, CI/CD or GenAI. Next: user-authorized container/release phase; cloud provisioning still requires a concrete approved cost plan and domain/HTTPS decision.
