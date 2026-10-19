# Phase 5: packaging and credential-free CI

## CI resolution during Phase 6 preparation (2026-10-19)

The previously queued runs completed successfully: current committed HEAD `1fb3961094a78683f25d56d65b8afa302d04a2a1` at https://github.com/RufinaM03/beyond-the-pass/actions/runs/39282257023 and image runtime revision `f668daf9447f2f97175c7355a9388f47354b2b75` at https://github.com/RufinaM03/beyond-the-pass/actions/runs/39280918052. This resolves the historical queued-CI blocker, not authorization to deploy. New Phase 6 working-tree changes have local checks only. Existing image/artifacts and all Phase 5 evidence below are preserved. See `DEPLOYMENT_PLAN.md` for approval-gated infrastructure preparation.

## Resumption: real release verified (2026-10-19)

User closed apps/restarted PC and opened Docker. Initial preflight: Linux x86_64 engine ready, RAM 2.55 GiB / available commit 3.44 GiB, C: 14.76 GiB / D: 59.98 GiB free. Resumed without real training, data downloads, raw scans, feature expansion or AWS.

**Real-release image and acceptance:** `beyond-the-pass:phase5-real`, local Docker image ID `sha256:ef69b2d2b4ac3e75d32744b745318e88e85e921cdfcec01004f139406f6f801f`, reported size **899,190,202 bytes (~857.53 MiB)**. One measured start-to-ready **25.040 s** (includes container creation/API polling on this Windows Desktop host, 1 CPU cap); one Docker stats observation **166.2 MiB / 512 MiB**. Not peaks, production sizing guarantees or direct comparisons with the differently hosted fixture image. UID/GID10001, one Uvicorn worker, readonly root/SQLite, bounded disposable tmpfs, dropped capabilities and no-new-privileges checked. Health/readiness/version, production frontend/static assets/deep links/API-asset 404s, **all 200 real HTTP predictions**, deterministic ranking, zero/overcapacity, validation/unknown/insufficient states, 200-vs-936 scope, unchanged saved metrics and aggregate-only index history pass. SQLite writes denied. Verification container stopped/removed; none left running. Evidence: `data/tmp/container-release.json`, `phase5-real-smoke.log`, `phase5-build-real-final.log`.

### Numeric portability diagnosis, not a changed model

First resumed production build reached its strict prediction gate and failed. A clearly labelled diagnostic-only image ran the original trusted loader/inference across all 200 real cases: **199 bit-identical, one score differing by 3.552713678800501e-15 = 2 IEEE-754 ULPs**; every other field/type/schema/explanation term identical (`data/tmp/phase5-numeric-diagnostic.json`). This is machine-precision cross-platform numerical rounding, not a model/data/feature/metric change. No exact math-library operation is inferred beyond that measured difference.

The backend now permits only **two adjacent binary64 representable steps in the score field**, using ordered float bit distance. Everything else is compared exactly, including types and all explanation terms. Artifact checksums/sizes/dependency/schema/version checks still precede loading and remain exact, so this cannot accept a changed/corrupted snapshot or bundle. Neither original scores nor serialized artifacts were rounded/rewritten. Queue ranking remains on original stored scores; prediction returns the same full-precision Phase 3 inference. Same-platform exact assertions are preserved. New synthetic tests accept at most 2 ULPs in either direction and reject 3, any explanation/metadata/type/key change, NaN and invalid scores. Readiness reports rounding count/delta/policy; the final real Linux container independently reports exactly one such case. **59 Python tests + 2 frontend tests pass**; Windows real integration remains 200 bit-identical agreements. The unchanged deeper verifier passes serially (`data/tmp/phase5-final-preserved-verification.log`): 6,642 preserved labels, 902-row preprocessing, 936 predictions/metrics and all 200 snapshots/source hashes. Original manifest remains `56846f43cfc8e23f809d16b27d85b144a8d634f8fa42870d2e6f59df7531fa14`.

### Current context, operations and remaining CI follow-up

Use **`data/package/phase5-real-portable`**: 29 files / **711,115 bytes**, source digest `febb635ed5a9efbaf5ae1418dc16a1e9da098fba4214cb4f98b8fedd79f307aa`, packaged runtime revision `f668daf9447f2f97175c7355a9388f47354b2b75`. Original contexts remain historical; do not use the old strict `phase5-real-linux` as current instructions. Operator-script/document updates do not change the runtime sources recorded in this image.

An offline/cache-only experiment failed closed because `--network=none` changed BuildKit RUN cache keys; removed that temporary option. No dependency substitutions. Confirmed zero running containers before a Desktop restart (not factory reset) to release temporary VM memory. Restart CLI reported unexpected termination, but subsequent engine info succeeded and RAM/commit recovered to 3.74/3.13 GiB. Normal cached build then succeeded. No reset, manual prune, deletion of existing images/volumes, storage relocation or system-setting command was issued. The diagnostic image remains explicitly labelled `diagnostic-not-release`, not deployable evidence. Final observed C:/D: free space 39.23/59.94 GiB; RAM/commit 3.18/1.64 GiB. No attribution is made for unrelated free-space changes.

Cold-build host preflight stays 2 GiB RAM/commit. **Smoke-only** host preflight is 1 GiB: hard 512 MiB container cap plus measured ~177 MiB host verifier and reserve. It never installs dependencies/builds an image. Disk reserves remain 5 GiB; no data/model/test-validity guard is bypassed. Resource observations are not universal capacity limits.

```powershell
.\scripts\container.ps1 -Command Validate -Mode release -Context data/package/phase5-real-portable
.\scripts\container.ps1 -Command Build -Mode release -Context data/package/phase5-real-portable -Image beyond-the-pass:phase5-real -StorageConfirmed
.\scripts\container.ps1 -Command Verify -Mode release -Context data/package/phase5-real-portable -Image beyond-the-pass:phase5-real
docker run --rm --name btp-local --read-only --tmpfs /tmp/btp:rw,noexec,nosuid,size=64m,mode=1777 --memory 512m --cpus 1 --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 -p 127.0.0.1:8000:8000 beyond-the-pass:phase5-real
```

Open `http://127.0.0.1:8000`; readiness `/api/ready`, versions `/api/versions`. Foreground run stops with Ctrl+C, or `docker stop --time 25 btp-local`. Verification has already stopped its own container; these commands start a new one. Keep local-only binding; no public deployment/authentication claim.

Earlier native Node24 [CI run succeeded](https://github.com/RufinaM03/beyond-the-pass/actions/runs/39277821612). The [new portability-code run](https://github.com/RufinaM03/beyond-the-pass/actions/runs/39280918052) remains queued without an assigned runner. [Official GitHub Status](https://www.githubstatus.com/) reports Actions degraded performance / “Incident with Actions and Pages”. Thus the latest revision's **remote rerun is pending**, not fabricated as green; local real-container acceptance and prior remote CI success are independently evidenced. Do not weaken tests or change runners/billing simply to mask the queue. No monitoring automation or Phase 6 AWS work created.

## Earlier observations (historical; superseded where noted)

## Latest remote CI evidence

Verified native Node24-action [run 39277821612](https://github.com/RufinaM03/beyond-the-pass/actions/runs/39277821612) **succeeded** at commit `290790c`: complete 56-test Python suite, two frontend tests/build, synthetic staging, production rejection, amd64 fixture image and all smoke checks. No legacy Node20 warning remains. Fixture image **637,664,535 bytes**, start-to-ready **2.850 s**, one memory observation **135.2 MiB / 512 MiB**; verification container stopped. Evidence `data/tmp/phase5-remote-ci-v6.log` and `remote-container-fixture-v6.json`. No real artifact or secret was uploaded. These remain synthetic software checks, not real model performance or real-release container verification.

## Scope and status

Preserves the real `btp-exploratory-v1` release, cohort, four predictors, exact inference, saved evaluation and aggregate-only history. No real training, data acquisition, source rescans, Docker reset/deletion, AWS or deployment. Fixture fitting is exclusively four invented software-test rows, visibly synthetic, never performance evidence.

Private repository created with user authorization: [RufinaM03/beyond-the-pass](https://github.com/RufinaM03/beyond-the-pass). First actual [remote CI run succeeded](https://github.com/RufinaM03/beyond-the-pass/actions/runs/39277083888): all 56 Python tests, two frontend tests/build, fixture rejection, Linux fixture image and read-only smoke. Fixture image 637,664,535 bytes, start-to-ready 2.807 s, one memory observation 135.3 MiB / 512 MiB; stopped afterward. These are **synthetic CI observations, not real model performance or real-release container acceptance**. First run warned about legacy Node20 action runtimes; verified official v6 revisions and updated to native Node24 actions. Subsequent run and local real-image execution are recorded below when observed.

## Docker readiness observations

Initial `docker info` failed: missing `dockerDesktopLinuxEngine` named pipe; Desktop status said not running. C: **10.63 GiB** free, D: **60.08 GiB** free, available RAM ~3.63 GiB and Windows commit ~1.97 GiB. Settings JSON had no explicit data-folder override; observed existing `%LOCALAPPDATA%\Docker\wsl\disk\docker_data.vhdx`, **48,856,301,568 bytes (~45.5 GiB)**. That is the existing VHD file length, not Docker-reported used image space. Current configured storage requires confirmation in Desktop; engine unavailable means DockerRootDir/image usage cannot yet be verified. Project location on D: does not relocate that C:-resident VHD.

User opened Desktop; it reported “starting the docker engine”. Next `docker info` reached the pipe but returned 500 during startup, not readiness. No reset/prune, deletion, WSL shutdown, service change or relocation was attempted. Exact user action: start via `docker desktop start`, wait for Linux engine, confirm **Settings → Resources → Advanced → Disk image location**, then rerun `docker info`. If moving storage, use the supported Desktop UI and Apply & restart, with an explicit backup/space decision; never manually move/delete the VHD. [Official WSL storage guidance](https://docs.docker.com/desktop/features/wsl/), [Desktop CLI start](https://docs.docker.com/reference/cli/docker/desktop/start/).

Subsequently Desktop status **running**, `docker info` succeeds: Linux x86_64, `/var/lib/docker`, VM memory 8,163,373,056 bytes. The observed C: VHD was updated at engine start; retained its location without configuration changes. C: 11.21–11.30 GiB free / D: 59.97 GiB. Existing unrelated images/containers/24.87 GB volume/12.09 GB cache were not deleted or modified by this work. Windows commit temporarily fell to 0.76 GiB; requested unused-app closure, held local build, then measured 1.29 GiB headroom / 2.12 GiB RAM. Plan reserves up to ~3 GiB incremental build storage with a 5 GiB C: reserve, based on the observed ~638 MB fixture image plus transient layers/cache, not a guaranteed bound. Frontend completion is now a prerequisite for Python install, serializing the memory-heavy stages; Node heap limited to 256 MiB. Local resource checks continue before build.

### Actual local build resource blocker

Fresh real context `data/package/phase5-real-linux` is validated, 709,257 bytes, code revision `290790c` (full revision in its package manifest). Local build `beyond-the-pass:phase5-real` successfully resolved/pulled official pinned Linux bases and built the production frontend, then reached binary Python installation. Despite serial stages, Windows available commit fell **1.29 → 0.44 → 0.30 GiB**; a subsequent shell could not create its pipeline. Cancelled this owned build rather than modify system settings or risk OOM. No real-release image size, container memory or startup timing is available; do not substitute successful CI fixture numbers. Build log `data/tmp/phase5-build-real.log`. Existing images/volumes/containers were not deleted. A concurrent deeper preserved-release verification attempt stopped at the unchanged 256 MiB commit guard before verifying; do not claim it succeeded in Phase 5. Earlier exact real HTTP/staging checks succeeded.

Resume after closing unused applications and obtaining **at least 2 GiB available Windows commit and RAM**, with 5 GiB disk reserve on C:/D:. `container.ps1` now enforces this preflight for Build/Verify to prevent another under-resourced attempt. These are conservative operator gates based on the observed failure, not guaranteed capacity sizing. No model/test/data-validity checks were weakened. Retry the existing validated context (no restaging/retraining/download of data), then run real smoke; run the deeper preserved verifier separately, not concurrently with a memory-heavy build. Docker engine itself is now healthy; the outstanding blocker is host commit capacity, not a Docker daemon error.

## Reproducible release and fixture boundary

After the build cancellation, ran the deeper real verifier **serially and successfully**: unchanged 6,642 labels, training-only preprocessing on 902 rows, all 936 saved predictions/metrics and 200 snapshot predictions, immutable SQLite and original source/manifest hashes. Peak working set 184,979,456 bytes; evidence `data/tmp/phase5-preserved-release-verification.log`. This supersedes the earlier concurrent capacity-blocked attempt for verification only, not real-image acceptance. Docker preflight was exercised and correctly blocked local Verify at low available commit before starting a container (`data/tmp/phase5-resource-preflight.log`).

`scripts/package_release.py stage --mode release` invokes the existing `Release`/`load_release` path, verifies original manifest/files/dependency versions, all 200 frozen predictions, feature schema and frozen pipeline source hashes. Copies **only** serving code, lockfiles, frontend sources and the seven declared release files + manifest + relocated descriptor. No source archives, full cohort, evaluation row table, credentials, node_modules or venv. Builds use this small explicit context under ignored `data/package/`, not the workspace root. Context manifest checks every file's SHA256/size and rejects extras/tampering. Existing stage directories are not overwritten.

Original manifest digest remains `56846f43cfc8e23f809d16b27d85b144a8d634f8fa42870d2e6f59df7531fa14`. `tools/trusted-release.json` is the repository-controlled public trust descriptor, not a credential. Packaged descriptor uses `directory_base=descriptor` and `directory=.` for portable paths; original release files and their hashes are unchanged.

`--mode fixture` explicitly creates `fixture-ci-v1` / `synthetic-ci-only`: four invented rows, a compatible tiny fitted test bundle, four-case SQLite and synthetic test metrics/card. Production validation **rejects** fixture markers/identity, even if `BTP_ALLOW_FIXTURE=1`; relabeling a fixture cannot match the pinned real manifest. Runtime rejects fixtures unless explicitly opted in. API versions and dashboard show unmistakable fixture identification; real 200/936 labels do not describe a fixture. Production validation is `validate --mode release`; never substitute fixture results for a real-release acceptance claim.

Initial verified staging: `data/package/phase5-real` **29 files / 709,252 bytes**; fixture `data/package/phase5-fixture` **29 files / 200,803 bytes**. These are context sizes, not image sizes. Source digest/image revision metadata are in each `package-manifest.json`. Later source edits require a new context directory; no silent overwrite or bundle regeneration.

## Container design

- Multi-stage React lockfile build + Python 3.12 Linux serving runtime. Official Node 24.15.0 and Python 3.12-slim-bookworm base **index digests** pinned from registry metadata; builds explicitly `linux/amd64`, matching intended ECS `X86_64`. No ARM/emulation assumption.
- Unchanged locked serving dependencies installed as binary wheels. A local PyPI dry-run resolved the complete app lock for CPython 3.12 Linux x86_64; evidence `data/tmp/linux-dependencies.json` / `.log`. This verifies wheel resolution, not an executed Linux/container install.
- One Uvicorn worker, exec-form command, UID/GID 10001, SIGTERM/graceful timeout, stdout/stderr, no uploads or cloud credentials. Code/release tree non-writable. Verification adds read-only root, dropped capabilities, no-new-privileges, PID/memory/CPU bounds and disposable `/tmp/btp` tmpfs. SQLite retains immutable/query-only access.
- `BTP_RELEASE_DESCRIPTOR` and `BTP_FRONTEND_DIR` configure portable runtime paths; `BTP_ALLOW_FIXTURE` defaults off; code/artifact/mode labels must match staged metadata. `/api/health` is liveness; `/api/ready` verifies trusted loading and 200 predictions (four in explicit fixture mode). Docker health check uses readiness.

## Exact commands

From `D:\2026-27\PROJECTS\BEYOND_THE_PASS`, existing Python 3.12 environment:

```powershell
.\scripts\app.ps1 -Command Test
.\scripts\container.ps1 -Command Validate -Mode release -Context data/package/phase5-real
# To stage a new, non-existing context after source changes:
.\scripts\container.ps1 -Command Stage -Mode release -Context data/package/release-v1
.\scripts\container.ps1 -Command Build -Mode release -Context data/package/release-v1 -Image beyond-the-pass:release-v1 -StorageConfirmed
.\scripts\container.ps1 -Command Verify -Mode release -Context data/package/release-v1 -Image beyond-the-pass:release-v1
```

`-StorageConfirmed` is an explicit operator acknowledgement, not an automatic storage change. Verify engine/storage/free RAM/disk before supplying it. Stage/Validate work without Docker. Scripts configure process temp paths on D: and restore them. Equivalent cross-platform CLI:

To resume the already staged real build after freeing memory (no new staging needed):

```powershell
.\scripts\container.ps1 -Command Build -Mode release -Context data/package/phase5-real-linux -Image beyond-the-pass:phase5-real -StorageConfirmed
.\scripts\container.ps1 -Command Verify -Mode release -Context data/package/phase5-real-linux -Image beyond-the-pass:phase5-real
.\scripts\data.ps1 -Command Verify
```

Run these **sequentially**, after at least 2 GiB free RAM/commit. The final command is the preserved local deeper release/cohort verification, not a fixture check. Raw data is neither read nor acquired by these commands. The container uses the code revision recorded when staging; if application/Dockerfile sources change, choose a new context and validate it instead.

```text
python -m scripts.package_release stage --mode fixture --output data/package/ci-fixture --code-version <actual-git-sha>
python -m scripts.package_release validate --mode fixture --context data/package/ci-fixture
python -m scripts.package_release validate --mode release --context data/package/ci-fixture
```

The last command **must fail**. Build via the Dockerfile with `ARTIFACT_MODE=fixture`, `ARTIFACT_VERSION=fixture-ci-v1`, and `CODE_VERSION` equal to staged metadata. `scripts/container_check.py` starts one uniquely named loopback-only verification container, verifies API/frontend/assets/one exact artifact prediction/rank/bounds/errors/demo-vs-evaluation/history/read-only SQLite, records image ID/size/start-to-ready/stats, and stops/removes only its owned verification container in `finally`. Reports go to ignored `data/tmp/container-{release,fixture}.json`. A single memory/startup observation is not a production capacity guarantee.

## CI classification and security

`.github/workflows/ci.yml`: Ubuntu 24.04, Python 3.12, locked Node/npm, pip/npm caching, complete synthetic unit suite, frontend tests/build, fixture-only staging, enforced production rejection, Linux amd64 container build and smoke/cleanup. No real artifact availability assumption, DVSA request, AWS secret or deployment. PR/push-main/manual events, contents-read only, no persisted checkout credential, concurrency cancellation, 30-minute job timeout. Only official checkout/setup-python/setup-node actions; each direct `uses` pinned to an immutable SHA verified with `git ls-remote` on the official repository. Docker commands use the runner engine directly; no cloud/image push action.

**Retained real-only integration:** `scripts/check_app.py` / `scripts/app.ps1 -Command Integration`, `pipeline.verification` / data.ps1 Verify, real-release stage/production validation and real-image smoke. They require the separately delivered approved ignored release (full cohort/evaluation Parquet only for the deeper preserved Phase 3 verifier), so PR CI does not run them. Assertions remain intact; fixtures are not passed off as real integration results. Existing 51 Python tests preserved; five packaging tests added. No GitHub workflow success is claimed until an actual remote run succeeds.
