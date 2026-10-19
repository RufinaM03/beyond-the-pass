# Phase 5: packaging and credential-free CI

## Scope and status

Preserves the real `btp-exploratory-v1` release, cohort, four predictors, exact inference, saved evaluation and aggregate-only history. No real training, data acquisition, source rescans, Docker reset/deletion, AWS or deployment. Fixture fitting is exclusively four invented software-test rows, visibly synthetic, never performance evidence.

Private repository created with user authorization: [RufinaM03/beyond-the-pass](https://github.com/RufinaM03/beyond-the-pass). First actual [remote CI run succeeded](https://github.com/RufinaM03/beyond-the-pass/actions/runs/39277083888): all 56 Python tests, two frontend tests/build, fixture rejection, Linux fixture image and read-only smoke. Fixture image 637,664,535 bytes, start-to-ready 2.807 s, one memory observation 135.3 MiB / 512 MiB; stopped afterward. These are **synthetic CI observations, not real model performance or real-release container acceptance**. First run warned about legacy Node20 action runtimes; verified official v6 revisions and updated to native Node24 actions. Subsequent run and local real-image execution are recorded below when observed.

## Docker readiness observations

Initial `docker info` failed: missing `dockerDesktopLinuxEngine` named pipe; Desktop status said not running. C: **10.63 GiB** free, D: **60.08 GiB** free, available RAM ~3.63 GiB and Windows commit ~1.97 GiB. Settings JSON had no explicit data-folder override; observed existing `%LOCALAPPDATA%\Docker\wsl\disk\docker_data.vhdx`, **48,856,301,568 bytes (~45.5 GiB)**. That is the existing VHD file length, not Docker-reported used image space. Current configured storage requires confirmation in Desktop; engine unavailable means DockerRootDir/image usage cannot yet be verified. Project location on D: does not relocate that C:-resident VHD.

User opened Desktop; it reported “starting the docker engine”. Next `docker info` reached the pipe but returned 500 during startup, not readiness. No reset/prune, deletion, WSL shutdown, service change or relocation was attempted. Exact user action: start via `docker desktop start`, wait for Linux engine, confirm **Settings → Resources → Advanced → Disk image location**, then rerun `docker info`. If moving storage, use the supported Desktop UI and Apply & restart, with an explicit backup/space decision; never manually move/delete the VHD. [Official WSL storage guidance](https://docs.docker.com/desktop/features/wsl/), [Desktop CLI start](https://docs.docker.com/reference/cli/docker/desktop/start/).

Subsequently Desktop status **running**, `docker info` succeeds: Linux x86_64, `/var/lib/docker`, VM memory 8,163,373,056 bytes. The observed C: VHD was updated at engine start; retained its location without configuration changes. C: 11.21–11.30 GiB free / D: 59.97 GiB. Existing unrelated images/containers/24.87 GB volume/12.09 GB cache were not deleted or modified by this work. Windows commit temporarily fell to 0.76 GiB; requested unused-app closure, held local build, then measured 1.29 GiB headroom / 2.12 GiB RAM. Plan reserves up to ~3 GiB incremental build storage with a 5 GiB C: reserve, based on the observed ~638 MB fixture image plus transient layers/cache, not a guaranteed bound. Frontend completion is now a prerequisite for Python install, serializing the memory-heavy stages; Node heap limited to 256 MiB. Local resource checks continue before build.

## Reproducible release and fixture boundary

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

```text
python -m scripts.package_release stage --mode fixture --output data/package/ci-fixture --code-version <actual-git-sha>
python -m scripts.package_release validate --mode fixture --context data/package/ci-fixture
python -m scripts.package_release validate --mode release --context data/package/ci-fixture
```

The last command **must fail**. Build via the Dockerfile with `ARTIFACT_MODE=fixture`, `ARTIFACT_VERSION=fixture-ci-v1`, and `CODE_VERSION` equal to staged metadata. `scripts/container_check.py` starts one uniquely named loopback-only verification container, verifies API/frontend/assets/one exact artifact prediction/rank/bounds/errors/demo-vs-evaluation/history/read-only SQLite, records image ID/size/start-to-ready/stats, and stops/removes only its owned verification container in `finally`. Reports go to ignored `data/tmp/container-{release,fixture}.json`. A single memory/startup observation is not a production capacity guarantee.

## CI classification and security

`.github/workflows/ci.yml`: Ubuntu 24.04, Python 3.12, locked Node/npm, pip/npm caching, complete synthetic unit suite, frontend tests/build, fixture-only staging, enforced production rejection, Linux amd64 container build and smoke/cleanup. No real artifact availability assumption, DVSA request, AWS secret or deployment. PR/push-main/manual events, contents-read only, no persisted checkout credential, concurrency cancellation, 30-minute job timeout. Only official checkout/setup-python/setup-node actions; each direct `uses` pinned to an immutable SHA verified with `git ls-remote` on the official repository. Docker commands use the runner engine directly; no cloud/image push action.

**Retained real-only integration:** `scripts/check_app.py` / `scripts/app.ps1 -Command Integration`, `pipeline.verification` / data.ps1 Verify, real-release stage/production validation and real-image smoke. They require the separately delivered approved ignored release (full cohort/evaluation Parquet only for the deeper preserved Phase 3 verifier), so PR CI does not run them. Assertions remain intact; fixtures are not passed off as real integration results. Existing 51 Python tests preserved; five packaging tests added. No GitHub workflow success is claimed until an actual remote run succeeds.
