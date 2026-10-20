# Manual prediction: local implementation

## Final Docker acceptance

User freed memory; pre-build RAM6.29GiB/commit4.25GiB, C39.62GiB/D59.71GiB. Final build and smoke **pass**, preserving guards. Image `beyond-the-pass:manual-local-v2`, ID `sha256:dc6e5fa4d40ec2364c9503dd491d29d4512c21cfd6fa221a105b3bb0ca4f3888`, 899,256,247bytes, source digest `1552c00ab006d1112642039a2960e2ea4a3dbc53e0914c0392cdf3a331afa292`. All200 real HTTP prediction agreements, manual parity/context/eligibility, readiness, production assets, bounded deterministic queue, unchanged936 evaluation and read-only snapshot pass. Startup5.214s and memory166.4MiB/512MiB are observations, not capacity guarantees. Eight browser checks pass again on final production image at0.25CPU/512MiB/Haswell; screenshot visually inspected. Both owned verification containers stopped. Evidence: `artifacts/reports/manual-container-check-v2.json`, `artifacts/manual-browser/docker-v2/`; logs `data/tmp/manual-docker-build-v2.log`, `manual-docker-verify-v2.log`, `manual-browser-docker-v2.log`. Earlier blocking observations below are retained as incident history and superseded by this final acceptance. AWS routing/login and release authorization gates remain unchanged; no cloud update.

2026-10-20. No training, acquisition, archive scans, artifact changes or AWS writes. The public AWS demonstration still serves the original release; this addition is local/uncommitted.

## Implementation and evidence

- `/predict`: four actual frozen predictors, scope confirmation, optional context date, explicit miles, missingness and extrapolation warnings. Illustrative examples are labelled; no identifiers, storage, historical rank or observed-outcome claims.
- `/api/predict/manual`: strict bounded JSON, sanitized errors, no-store, frozen preprocessing/inference and actual signed logistic terms. `/api/prediction-info` exposes frozen ranges/medians/versions. Original historical endpoint, numerical comparison policy, aggregate-only history and trusted artifact hashes remain unchanged.
- Mileage provenance: cached official guide line 395 documents 2022 kilometre-to-mile correction; ingestion does not rescale. Later-release correction semantics remain independently unverified. See DATA_CONTRACT.md.
- Final source: **88 Python tests pass**, including existing assertions, strict schema/count consistency/nulls/calendar context/deep JSON/inference parity. Real approved artifacts: **200 historical/manual prediction agreements**, unchanged saved 936-example metrics and deterministic queue. Logs: `data/tmp/manual-python-tests-final.log`, `manual-real-integration.log`.
- **4 frontend tests pass**, production Vite build succeeds. Real-artifact production browser flows: **8 checks each** on local FastAPI and Docker, including scope, actual contributions, imputation/insufficient data, extrapolation, count consistency, responsive refresh and unchanged saved evaluation/queue. Evidence: `artifacts/manual-browser/local/`, `artifacts/manual-browser/docker/`. Synthetic isolated tests are not model-performance evidence.
- Docker first revision: Linux amd64, non-root/read-only, original real bundle. Image `beyond-the-pass:manual-local`, 899,256,182 bytes; readiness startup observation 8.738s, memory observation 150.3 MiB/512 MiB. These are single observations, not capacity guarantees. Separate browser ran at 0.25 CPU/512 MiB with the deployed Haswell kernel. Owned containers stopped. Report: `artifacts/reports/manual-container-check.json`.
- Final two-line JSON parser hardening and its regression assertion passed all Python/real integration checks. Final context `data/package/manual-local-v2`, source digest `1552c00ab006d1112642039a2960e2ea4a3dbc53e0914c0392cdf3a331afa292`; final rebuild initially blocked by 1.89 GiB Windows commit headroom (<2 GiB guard), not Docker failure. Do not misrepresent the preceding image as covering that final edit.

## Reproduction

Final resource recheck: Docker still reports Linux x86_64, but host commit headroom subsequently fell to **0.88 GiB** (RAM2.32GiB). No final build/smoke started below its guard. Latest frontend rerun: four tests and production build pass (`data/tmp/manual-frontend-tests-final.log`, `manual-frontend-build-final.log`). Docker verification of the final parser edit remains pending additional headroom; the first-revision results above remain explicitly separate.

From the project root with the existing Python 3.12 environment and approved ignored real release:

```powershell
$env:TEMP="$PWD\data\tmp"; $env:TMP=$env:TEMP
$env:OPENBLAS_NUM_THREADS='1'; $env:OMP_NUM_THREADS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m scripts.check_app
npm --prefix frontend test
.\scripts\app.ps1 -Command Build
.\scripts\app.ps1 -Command Serve
# In another terminal; production frontend served by FastAPI:
$env:BTP_BASE_URL='http://127.0.0.1:8000'; $env:BTP_VERIFY_TARGET='local'
node frontend/scripts/manual-browser-check.mjs
# Once the existing RAM/commit/disk guards pass:
.\scripts\container.ps1 -Command Build -Mode release -Context "$PWD\data\package\manual-local-v2" -Image beyond-the-pass:manual-local-v2 -StorageConfirmed
.\scripts\container.ps1 -Command Verify -Mode release -Context "$PWD\data\package\manual-local-v2" -Image beyond-the-pass:manual-local-v2
```

## Deployment review — not authorization to update AWS

2026-10-21 IST update request: AWS authentication now works. Fresh actual safe routing read-back confirms POST/no-cache/origin-policy/ALB forwarding above. New bounded proposal `MANUAL_DEPLOYMENT_PLAN.md` reuses the unchanged S3 artifact release without writing a new application archive: new application provenance is separately pinned ECR image/source digest/exact CI commit. This avoids additional S3/IAM grants without misrepresenting the old archive. Human confirmation requested; original hosting deadline unchanged. Earlier expired-session/new-prefix concerns below are historical and superseded only for this separately reviewed application-only path.

Only a new application image/task revision is proposed. No new service, topology, model, features, artifact versions or task sizing; no paid-service addition. Existing approved topology already supports POST: CloudFront default behavior allows POST, uses CachingDisabled and AllViewerExceptHostHeader, and ALB forwards the secret-header-gated rule without method restrictions. CloudFront forwards POST bodies and the managed origin policy forwards Content-Type; application manual responses are no-store. Official references: [managed origin policies](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-managed-origin-request-policies.html), [managed cache policies](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-managed-cache-policies.html). No other mutation/upload endpoints are enabled.

Previous actual Phase 6 read-back verifies that routing, but **fresh requested deployed inspection is pending expired AWS login**, not an IAM denial or evidence of application failure. Renew locally with `aws login --profile beyond-the-pass`; never share credentials/codes. Diagnostic projections must exclude CloudFront origin headers and ALB condition values. Do not deploy before fresh inspection.

Existing deployment guards pin old code/image and the approved plan. Updating requires reviewed new code/image pins, exact-commit green CI and release approval. Existing S3 publication permission is scoped to the original code-version prefix only; a new prefix requires an administrator-reviewed narrowly scoped grant or separately reviewed artifact-reuse publication design. Do not bypass guards, use old prefixes as false provenance, or grant self permissions. No new remote CI has been run for these local edits.

Original hosting deadline stays **2026-10-21 06:12:53 UTC /11:42:53 IST**. No extension or automatic teardown. Retain the existing manual teardown command in PROJECT_STATE.md. Approved HTTP CloudFront-to-ALB origin remains a temporary public-data limitation; do not enter personal/private fleet data. No AWS update performed.
