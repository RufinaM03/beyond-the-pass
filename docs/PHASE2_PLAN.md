# Phase 1B / 2 predeclared acquisition and cohort plan

Declared 2026-10-19 before larger transfers or expanded cohort counts. No training.

## Minimum defensible expansion

The catalogue still lists competing March 2025 / June 2026 2024 pairs; use only the June 2026 pair, never concatenate them. Its monthly members are stored (method 0). The existing range reader plus an exact member range permits complete monthly CSV acquisition with CRC32 and local SHA256, without fetching the enclosing ZIP. Each member is one sequential streamed request; interrupted members restart. No bespoke fragmented downloader or sparse ZIP reconstruction.

First acquire the complete January result/item members: 820,826,735 bytes (0.764 GiB). Verify actual newer schemas, source codes, class-qualified current dictionaries, sampled test/item linkage and 2023 vehicle-ID continuity. Stop on a failed gate. Then acquire the other eleven paired months, only if that gate passes: total 2024 CSV bytes 9,127,357,646 (8.501 GiB), excluding small directory/header requests. Parent archive bytes/ETags remain pinned; parent ZIP downloads/checksums remain pending, with complete member provenance recorded separately.

2025 is not necessary for the narrower holdout below. All 2024 months are needed to retain complete annual sampled histories and avoid skipping an earlier normal inspection. Acquiring only convenient outcome months would miss intervening normal tests and late outcomes. The full 2024/2025 plan remains an optional later expansion, not an automatic transfer. No March 2025 alternative is acquired.

## Sample size, once

Use existing SplitMix64 `hash % 1000 == 0` across all acquired years, ten times the completed modulus-10000 sample and nested with both existing pilots. This is an outcome-independent census of selected vehicles within 2022–2024. Existing archives are reused, never downloaded again. Result scans precede all item scans. About ten times the existing 2022–2023 cohort is a projection for planning, not a measured count; labels/positives must be measured after construction. No future-failure oversampling.

Retain every test type and item for sampled vehicles. Run one bounded worker at a time, 25,000-row chunks, D: scratch/cache, one BLAS thread, capacity gates and 200,000 sampled-test numeric-index cap. If exceeded, stop for a disk-backed join rather than enlarge the cap. Existing measured result-worker working sets were 1.3 GiB; rechecked resources were 3.44 GiB available RAM, 2.80 GiB commit headroom and 69.13 GiB D: free. Output growth and peaks will be measured; no hard RSS claim.

## Annual cohort and exact retrospective timeline

- Class 4, provisional brakes; index NT/P with mapped A. Immediate next NT across all classes, never skip an earlier NT. Retests PV/PL/RT and appeals are not NT follow-ups.
- Inclusive 9–15 **calendar months**, not a day-count surrogate. Exclude class changes, same-day ambiguities, conflicting identity/item evidence, unknown mappings and incomplete next outcomes. Missing follow-up remains censored. Retain all attrition reasons.
- Same-family F or rectified-P item at an otherwise consistent completed NT P/F/PRS is positive. PRS is failure at presentation, not clean pass; PRS is not an index. A different-component failure is negative only with consistent, mapped item evidence. Itemless P may be negative; F/PRS without matching failure evidence is not.
- Training index window: **2022-01-01–2022-03-31**. Outcome envelope: **2022-10-01–2023-06-30**, individually constrained to 9–15 months. Model freeze: **2023-07-01 00:00 UTC**; each training outcome availability proxy must strictly precede it.
- Holdout index window: **2023-07-01–2023-09-30**. Outcome envelope: **2024-04-01–2024-12-30**, individually constrained to 9–15 months. End observation: **2024-12-31**. This is a three-month, season-shifted holdout, NOT full-year evaluation. Freeze precedes every evaluated prediction.
- Fixed vehicle assignment, independent of outcomes: `(hash // 1000) % 5 == 0` for holdout (approximately 20%); all others train. Report attrition before/after this split. Never use a holdout vehicle's earlier training example. Other windows remain unused, not repurposed for tuning after looking at labels.

Older archives have no completion/publication field; use end-of-test-day as a conservative event-date proxy. Newer records use the maximum of end-of-day, result and item completion timestamps. `completed_date` format and order are record-verified; authoritative semantics/revision latency are not documented in the retrieved guide. These retrospective files were published later than the proposed historical freeze: do NOT claim actual public-data availability at that time, a deployed backtest or exact revision-as-of reconstruction. Preserve this readiness limitation.

## History / readiness gate

Features are explicitly allowlisted, index-only and identifier/postcode-free. Mileage deltas require prior valid readings and nondecreasing mileage; rollback is flagged, not a negative travel distance. Historical component counts refer to recorded normal inspections; recurrence means an earlier recorded family advisory, never proof of ignored repair or the same physical part. No observed prior advisory is not a confirmed absence before 2022.

Training is left-truncated at 2022 and has at most a quarter-year observed history; holdout can have over a year. Measure recurrence and history coverage in BOTH partitions. This acquisition may establish an annual label cohort without supporting a recurrence model. There is no independently mature chronological tuning partition in the stated window; no model selection or model-readiness claim follows automatically. More pre-2022 authoritative history and/or later outcomes may be required.

## Reproduction (D: project, Python 3.12 environment)

```powershell
.\.venv\Scripts\python.exe -u -m pipeline.expansion fetch --months 1
.\.venv\Scripts\python.exe -u -m pipeline.expansion gate
# Only after a passing gate:
.\.venv\Scripts\python.exe -u -m pipeline.expansion fetch --months 2 3 4 5 6 7 8 9 10 11 12
.\.venv\Scripts\python.exe -u -m pipeline.expansion ingest --name expanded2022-2024 --modulus 1000
.\.venv\Scripts\python.exe -u -m pipeline.cohort --name expanded2022-2024
.\scripts\data.ps1 -Command Test
```

Full records and trace IDs stay in ignored local artifacts. Aggregate reports and manifests are reviewable. No training, Docker, AWS or frontend work.

Equivalent environment-scoped wrapper commands: `scripts/data.ps1 -Command FetchJanuary`, `ValidateJanuary`, `Fetch2024`, `Expand`, `Cohort`, `Test`. All use the verified project Python 3.12 environment and D: temporary/cache paths. An existing expansion is protected; only incomplete acquisitions can use the explicit `pipeline.expansion resume` command.
