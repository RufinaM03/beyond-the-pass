# Environment report

Observed 2026-10-19, Asia/Calcutta. No credential contents inspected; no AWS account/authentication requests made.

## Phase 4 local readiness

Python 3.12.7 in `.venv`, Node 24.15.0 and npm 11.1.0 verified. Locked app dependencies added without changing frozen model/data dependencies; production Vite build and FastAPI serving verified. Initial recheck: D: 60.34 GiB free, RAM ~3.61 GiB available, Windows commit ~2.09 GiB available. Real artifact verification later peaked at ~176 MiB process working set with ~60.08 GiB disk free, ~3.34 GiB RAM and ~1.48 GiB commit headroom available at that check. Scripts keep process caches/temp files on D: and restore settings. Docker/AWS were not inspected or changed in this phase. Desktop browser-tool initialization failed on a missing kernel-assets path; pinned CLI Playwright with installed Chrome successfully verified the production dashboard. See `docs/PHASE4_REPORT.md` for actual checks and limits.

## Phase 0 observations (historical)

| Check | Actual result | Action |
| --- | --- | --- |
| Workspace | `D:\2026-27\PROJECTS\BEYOND_THE_PASS`, initially empty | Scaffold created; Git initialized; no commits or remote configured by this work. |
| OS | Windows 11 Home Single Language, 64-bit, 10.0.26200 | Use PowerShell and Docker Desktop Linux containers when engine is available. |
| Shell | PowerShell 7.6.5 | Available. |
| Python | `python`: 3.12.7 at `D:\Python\Python312\python.exe` | Target 3.12; later create environment with `py -3.12 -m venv .venv`. |
| Python launcher | 3.12, 3.13, 3.14 installed; default 3.14 | Avoid implicit `py` default for project commands. |
| pip | 24.2 for Python 3.12 | Available; no install or upgrade performed. |
| Node / npm | v24.15.0 / 11.1.0 | Available; validate chosen Vite/dependency versions and commit lockfile in frontend phase. |
| Git | 2.54.0.windows.1 | Available; repository initialized. Remote and CI context remain pending. |
| Docker CLI | 29.4.3, build 055a478 | Installed. |
| Docker engine | `docker info` failed: missing `dockerDesktopLinuxEngine` named pipe | Start/configure Docker Desktop Linux engine, then verify `docker info` before container phase. Daemon version/container capability unverified. |
| AWS CLI | 2.34.50, Python 3.14.4, Windows/11 | Installed; credentials, account, access, region, and permissions unverified. Do not paste credentials into chat. |
| Physical RAM | 15.69 GiB total, 1.68 GiB free | Close memory-heavy applications before chunk processing/builds; measure again. Set chunk sizes only after source profiling. |
| C: disk | 188.25 GiB total, 7.99 GiB free | Free space or configure Docker/cache storage on a drive with sufficient capacity before large images/downloads. |
| D: disk | 268.07 GiB total, 71.48 GiB free | Project storage available; verify source archive + extraction + Parquet + temporary output budget before downloading. |
| Domain / DNS | User reports no domain yet | Select a domain and DNS control before ACM/ALB HTTPS setup; no local blocker. |

## Immediate readiness

Phase 0 requires no installations. Python/Node/Git/AWS CLI are present. Docker engine availability is the main missing runtime prerequisite; free RAM and C: capacity constrain later work. No claim is made that the real dataset fits available disk. Dependencies, lockfiles, data tooling, cloud permissions, GitHub OIDC, and deployment resources remain unvalidated until their requested phases.

## Phase 1 recheck and allocation diagnosis

Phase 1 began with 2.84 GiB available RAM, D: 71.48 GiB free, and C: 8.07 GiB free. The Python 3.12 environment and pip cache are on D:. The reproduction wrapper sets D: TEMP/TMP/cache paths before even creating a new environment; initial manual environment creation preceded that TEMP setup, so ensurepip's transient scratch location was not audited. Package installation and data processing use process-local D: paths.

The small real-data pilot completed at 1.28 GiB peak working set. During the larger sample, allocation failed while RAM still appeared available: the OS reported 2.32 GiB free physical RAM but only 0.47 GiB free virtual/commit capacity (19.69 GiB total limit, existing 4 GiB C: pagefile). No pagefile or machine-wide setting was changed.

Controlled fresh-process observations: default BLAS threads plus system Arrow allocator used 428,474,368 bytes private commit; one BLAS thread with default Arrow allocator used 58,109,952 bytes. Working sets were both around 80 MiB. A separate clearly synthetic 100-row-group Parquet probe added about 2.4 MB private commit, insufficient to explain the overall allocation failure. This supports commit pressure amplified by unnecessary BLAS thread reservations, rather than blaming raw archive size or Parquet metadata alone.

Data workers now use one BLAS/OpenMP thread per process, measure available commit/private commit as well as RSS, and stop below 256 MiB RAM or commit headroom. See [NumPy global configuration](https://numpy.org/doc/stable/reference/global_state.html) for BLAS thread controls. The smallest manual adjustment if commit headroom remains insufficient is to close unneeded applications; no application is closed automatically, and system settings are not changed.

## Phase 1B / 2 capacity

Rechecked before expansion: RAM 3.44 GiB available, commit headroom 2.80 GiB, D: 69.13 GiB free. All 2024 monthly CSV members (8.501 GiB) were acquired sequentially; older ZIPs were reused. Six full scans completed in 2,382.69 seconds. Peak working sets: legacy results 1.30 GiB, newer result 209 MiB, item workers 159/165/189 MiB, cohort construction 624 MiB. The sorted numeric test-ID index used 1,003,048 bytes, below its 200,000-test cap; no population ID set or extracted archive copies.

Final measured snapshot: D: 60.57 GiB free, C: 10.55 GiB free, available RAM 3.23 GiB, commit headroom 1.16 GiB. Raw cache 12,380,615,779 bytes, expanded artifacts 70,726,871 bytes. Measurements include other applications and are not fixed bounds; recheck before processing. No system/pagefile changes, automatic app closure, Docker troubleshooting or additional package installation occurred. Source anomaly diagnosis and readiness findings: `PHASE2_REPORT.md`; detailed local capacity telemetry: `artifacts/reports/phase2-capacity.json`.

## Phase 3 bounded modelling

Rechecked available RAM 2.92 GiB, Windows commit headroom 1.56 GiB, D: 60.57 GiB free before work. Explicit Python 3.12 and D: temporary/pip cache paths retained. Six pinned modelling dependencies were added from official PyPI binary wheels; original nine data dependency versions are unchanged. All 15 packages match `requirements-model.lock` plus its included data lock and pass `pip check`.

Processed Parquet/SQLite only; no real raw-archive reads or data-year acquisition. Fresh model/export run peaked at 192,339,968 bytes working set and 218,963,968 bytes private commit; D: remained about 60.33 GiB free. CPU threading stayed bounded; no system settings or applications were changed. Full tests/verification: `scripts/data.ps1 -Command Test` / `Verify`. Use `SetupModel` for a fresh complete model/test environment; the original `Setup` remains data-only. Docker/AWS are still outside the phase.
