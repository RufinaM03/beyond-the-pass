# Phase 1 acquisition and reproduction

## Sources and licence

Official catalogue: https://open.data.dvsa.gov.uk/mot-anonymised/index.html (observed 2026-10-19; page states updated 22 June 2026). The pinned catalogue HTML is local at `data/sources/catalogue.html`. `docs/source_manifest.json` records every linked source URL, publisher metadata, observed byte size, ETag, retrieval status, and SHA-256 when a complete file has actually been downloaded. ETags are version validators, not assumed SHA-256/MD5 checksums. ZIP member sizes are central-directory claims until complete member reads validate CRCs.

The catalogue footer applies [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/), except where stated otherwise. The licence was retrieved separately; its checksum is in `docs/licence_manifest.json`, with the local HTML under `data/sources/`. Reuse permits adaptation and commercial use with source/licence acknowledgement; exclusions include personal data and third-party rights. Attribute future outputs to DVSA and include: “Contains public sector information licensed under the Open Government Licence v3.0.” Do not imply DVSA endorsement. No legal interpretation beyond the published terms is claimed.

The post-May-2018 guide is `mot-testing-data-user-guide-v5.1.odt`; original archived lookup tables are `lookup.zip`. Six current CSV dictionaries were also acquired for compatibility comparison. The guide's coverage statement ends in 2023 and is not evidence about the completeness of newer releases. The catalogue's displayed “29 February 2023” date for 2022 is invalid; preserve its text rather than inventing a corrected date.

## Release selection and capacity

Annual archives identified by exact catalogue URLs (see machine-readable manifest):

| Year/release | Results bytes | Items bytes | Decision |
| --- | ---: | ---: | --- |
| 2022 original annual | 1,164,809,596 | 435,454,025 | Selected pilot pair |
| 2023 original annual | 1,192,881,905 | 460,112,607 | Selected pilot pair |
| 2024 March 2025 publication | 1,531,265,132 | 680,168,954 | Inspect only; older alternative, equivalence unverified |
| 2024 June 2026 publication | 4,797,842,352 | 4,329,520,730 | Selected expansion candidate, paired release |
| 2025 June 2026 publication | 4,835,709,507 | 4,359,554,510 | Selected expansion candidate, paired release |

The 2022–2023 pair totals **3,253,258,133 bytes (3.030 GiB)** downloaded sequentially. Its actual member metadata identifies about 10.38 GiB of uncompressed CSV; those annual CSVs are never extracted to disk. Both results archives use Deflate64 (ZIP method 9); item archives use Deflate (8). The reader supports both with pinned `zipfile64`/`inflate64` packages. Ignore `__MACOSX` metadata members.

New 2024/2025 archives contain monthly CSVs stored without compression. Their larger ZIP sizes alone do not prove more records or incompatible identifiers. The old 2024 release also has monthly CSVs and different uncompressed member sizes, so do not assume the versions differ only in compression. The catalogue does not explain the revision extent. Do not combine both 2024 releases or mix an old results release with new items. Prefer the current June 2026 pair for expansion, subject to full record, linkage, and revision validation; compatibility of 2023 vehicle IDs with those years remains unverified.

The selected additional 2024–2025 files total **18,322,627,099 bytes (17.064 GiB)**. They remain pending full acquisition. Retaining all selected 2022–2025 archives would require 21,575,885,232 bytes (20.094 GiB), plus the environment, bounded sample, caches, and reserve. Generated output size cannot be known before profiling the chosen sample; do not estimate it from a guessed compression ratio. Recheck space and RAM immediately before expanding. There is no need to unpack all archives; retain at least 5 GiB free on D:.

Initial Phase 1 recheck: 2.84 GiB free RAM, D: 71.48 GiB free, C: 8.07 GiB free. All project environments, package caches, raw archives, scratch, and generated output use D:. Temporary environment variables are process-scoped; no machine-wide changes. Docker is not required or modified.

## Commands (PowerShell, project root)

```powershell
.\scripts\data.ps1 -Command Setup
.\scripts\data.ps1 -Command CheckSources
.\scripts\data.ps1 -Command FetchPilot
.\scripts\data.ps1 -Command Documentation
.\scripts\data.ps1 -Command Test
.\scripts\data.ps1 -Command Pilot
.\scripts\data.ps1 -Command Sample
```

`Setup` creates `.venv` using the verified `D:\Python\Python312\python.exe` only if absent, asserts Python 3.12, and installs `requirements-data.lock`. It does not reinstall during ordinary commands. `Discover` is only for first pinning and refuses to overwrite an existing manifest. `Inspect` performs bounded HTTP ranges to inspect ZIP directories and header prefixes. `CheckSources` compares catalogue content/links and source HEAD validators; exit 2 indicates review is needed. It writes a report under ignored `artifacts/reports/` and never replaces pinned data or trains a model.

`FetchPilot` explicitly selects dictionaries, the post-2018 guide, and four 2022–2023 archives. A per-file byte bound and disk reserve apply. Transfers have socket timeouts and bounded retries; `.part` files remain separate until complete. Resume requires advertised byte ranges, a pinned strong ETag, matching partial metadata, and an exact HTTP 206 Content-Range response. If validation fails, stop for review. A verified cached file is reused; modified cached content is rejected. Checksums authenticate locally observed content, not an independently publisher-signed digest.

`Pilot` scans 2023 at 1/100,000 and reports within-year item linkage/memory; `Sample` expands to both complete acquired years at 1/10,000. Existing sample directories are protected from overwrite. To recover an incomplete scan after diagnosing its failure, use `.\.venv\Scripts\python.exe -u -m pipeline.pilot resume --name sample2022-2023`. Resume verifies completed-stage source hashes and SQLite/Parquet counts, reuses those stages, and reprocesses only incomplete stages; invalid partial Parquet files are preserved under `failed/`. It never promotes an incomplete year to a complete history. For a different explicit name or chunk size, invoke the module directly, for example:

```powershell
$env:TEMP = "$PWD/data/tmp"
$env:TMP = $env:TEMP
$env:SQLITE_TMPDIR = $env:TEMP
.\.venv\Scripts\python.exe -u -m pipeline.pilot ingest --years 2022 2023 --modulus 10000 --chunk-rows 25000 --name reviewed-sample
.\.venv\Scripts\python.exe -u -m pipeline.pilot report --name reviewed-sample
```

Sampling applies the fixed SplitMix64 integer transform to numeric `vehicle_id`, then selects `hash % modulus == 0`. This is stable across years, order, and chunks, and independent of outcomes. No first-N row sampling. The 1/100,000 sample is nested in 1/10,000. Every available result row in each fully scanned acquired year is retained for selected vehicles, including retests and incomplete tests. This is not a claim about pre-2022 or undownloaded 2024–2025 histories.

Results are streamed in 25,000-row pandas chunks into Parquet and an indexed local SQLite staging database. Sequential archive worker processes bound allocator retention between scans; the parent preserves a single combined test index in SQLite. All result years finish before any item-year scan, so item joins are not restricted to matching annual filenames. The sorted numeric join index is capped at 200,000 tests (at most 1.6 MB); larger expansion must implement disk-backed staging joins rather than growing Python sets. SQLite scratch is on D:. Parser errors, unknown schemas/codes, invalid identifiers/dates, duplicate test IDs, or low capacity stop the run. Partial sample directories remain explicitly incomplete for diagnosis; never report them as complete histories.

Workers use one BLAS/OpenMP thread per process and periodically collect expired pandas wrapper cycles. The memory probe in `artifacts/reports/parser-memory-diagnosis.json` reclaimed about 35 MB after ten chunks without changing any values or selection rules. Capacity gates check both physical RAM and Windows commit headroom (256 MiB minimum), because free physical RAM alone did not prevent an observed allocation failure. See `docs/ENVIRONMENT.md` for the diagnosis and measured import overhead; no system settings were changed.

## Evidence boundaries

For Phase 1B/2 use `PHASE2_PLAN.md` for targeted 2024 member commands and the fixed tenfold expansion. `docs/member_manifest.json` supplements rather than replaces the original parent-source manifest. Complete stored member range downloads validate the parent ETag, exact 206 Content-Range, byte length, CRC32 and SHA256. Partial member transfers restart with bounded retries; there is no unvalidated member resume. Existing verified members are reused. Full ZIPs and 2025 are not automatically acquired. Recovery after a diagnosed incomplete expansion: `.\.venv\Scripts\python.exe -u -m pipeline.expansion resume --name expanded2022-2024`; completed-stage provenance/counts are verified and reused. Never use the legacy sampler's resume command on the newer expansion schema.

See `docs/QUALITY_REPORT.md` and local `data/processed/<sample>/quality.json` for completed checks and actual counts. No training occurs. Source documentation, remote ZIP metadata/header inspection, full archive retrieval/checksum validation, and actual record scans are separate evidence levels in the manifest/report. A remote header prefix is not a completed annual download or a complete annual schema validation.
