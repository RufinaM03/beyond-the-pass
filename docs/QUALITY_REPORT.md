# Phase 1 quality and capacity

Historical Phase 1 report, preserved for reproducibility. The completed targeted expansion, strict 9–15-month annual cohort, partition counts, real traces and readiness blockers are in [PHASE2_REPORT.md](PHASE2_REPORT.md). Do not substitute the preliminary 1–550-day comparison below for the new target.

Completed 2026-10-19. Verified real linked 2022–2023 sample; no training or model metrics.

## Complete acquisition and scans

Four annual archives total **3,253,258,133 bytes (3.030 GiB)**, fully downloaded and SHA-256 pinned. CSV members were streamed to completion with CRC, schema, identifier, date and code checks; no annual extraction. The guide, lookup ZIP, six current dictionaries and OGL v3 were acquired. Provenance: `docs/source_manifest.json`, `docs/licence_manifest.json`, `docs/ACQUISITION.md`.

| Source | Actual rows scanned | Retained rows |
| --- | ---: | ---: |
| 2022 results | 41,632,878 | 4,127 |
| 2023 results | 42,216,721 | 4,147 |
| 2022 items | 86,352,508 | 8,455 |
| 2023 items | 89,302,632 | 8,538 |

Both result sources cover January 1–December 31. Fixed 1/10,000 vehicle sampling retains **3,584 vehicles, 8,274 tests and 16,993 items**, selected dates 2022-01-03–2023-12-30. All 431 initial 1/100,000 pilot tests are present. Complete histories are claimed only within fully scanned acquired years.

## Linkage and mapping

- **2,979 vehicle IDs span both years**, with no make, model or first-use-date changes among linked IDs. This supports source-ID continuity, not recovery across registration/VIN-driven ID changes.
- Zero duplicate retained test IDs; **43 duplicate item rows** preserved/reported. Labels count distinct tests.
- All **16,993 retained items join and map** using test ID and class-qualified RFR keys. Zero unknown keys or retained item/result source-year mismatches. SQLite quick-check and Parquet/SQLite/receipt counts pass.
- All **1,522 failed and 388 PRS tests have items**. Of 6,326 passes, 3,369 have no recorded items, consistent with legitimate itemless passes. Incomplete outcomes are excluded from labels.

Coverage is sample-scoped: source items are filtered against sampled test IDs. Population-wide orphan coverage is not claimed; missing items on passes do not automatically imply broken joins. Source integrity cannot establish every mechanically present defect.

Original dictionaries have 21,069 unique detail keys and 4,136 valid group keys. Current dictionaries add 36 detail keys without changing shared parent/section/category fields. A/F/P/M item codes determine advisory/failure state, not category text alone. Evidence: `artifacts/reports/dictionary-comparison.json`, `source_check.json`, `release-prefixes.json`.

## Component comparison: class 4

Strict normal-test passes with mapped A advisories; next normal test, completed outcome, unambiguous date and gap 1–550 days. Positive means same-family F/P item; repairs between tests are unobserved.

| Actual cohort count | Brakes | Tyres |
| --- | ---: | ---: |
| Eligible advisory tests | 743 | 956 |
| Advisory item rows | 1,243 | 1,632 |
| Observed next normal tests | 339 | 458 |
| Usable follow-ups | 334 | 453 |
| Positive F or rectified-P outcomes | 43 | 35 |
| Positive F-item outcomes only | 42 | 33 |
| No next test: censored, never negative | 404 | 498 |

Exclusion flags can overlap: same-day ambiguity 1/1, incomplete next outcome 1/0, gaps outside 1–550 days 5/4. No pair has unknown mapping, class changes, missing failure items or inconsistent result/item evidence. Median gap is 364 days for both families; 7/18 usable gaps are under 180 days.

**Recommend brakes**: more observed positives and complete observed mapping support the original preference. Tyres has more usable pairs; this is not evidence of predictive or statistical superiority. Expand the observation window before training.

## Chronological evaluation

Usable 2022-anchor pairs: brakes 323, tyres 441; 2023-anchor pairs: only 11/12. At a 2023-01-01 prediction boundary, just 9/16 training labels were observed beforehand; 314/425 cross-boundary pairs cannot be used for that training cutoff. These small same-year cohorts do not justify a credible annual train/validation/test evaluation.

Full 2024–2025 acquisition is **pending**: 18,322,627,099 additional bytes (17.064 GiB). Both competing 2024 releases and 2025 have ZIP/header inspections. Bounded January record prefixes confirm actual codes/date representations; zero overlap between alternative 2024 prefixes is inconclusive. Prefer paired June 2026 releases only after newer-schema, completion-date and lineage checks. `docs/EXPANSION_PLAN.md` defines a feasible retrospective 2022→2023 training / 2024→2025 evaluation candidate, with vehicle-disjoint and availability gates.

## Capacity and recovery

Initial 2023 pilot: 349 vehicles / 431 tests / 771 items; 689.95 seconds and 1.28 GiB peak working set. Larger processing exposed Windows commit pressure despite free RAM. Diagnosis, one-thread controls and a 35 MB parser-cycle reclamation probe are in `docs/ENVIRONMENT.md`. The failed stage stayed incomplete; completed 2022 work was reused and failed Parquet retained under `failed/`.

Completed result-worker peaks before periodic collection: **1.27/1.30 GiB**. Optimized item-worker peaks: **125/126 MiB working set**, **111/112 MiB private commit**. These are observations, not hard RSS bounds; first-result-worker private commit was not measured. Wall time including failed work/diagnosis/recovery: 2,588.23 seconds, not a steady-state benchmark.

Raw archives: 3.030 GiB. Expanded artifacts: 16,799,344 bytes including failed evidence. Environment/cache: 223,389,562 / 53,596,581 bytes. Final snapshot: D: 69.13 GiB free, RAM 1.91 GiB available, commit headroom 0.92 GiB. Recheck before further work; no system/pagefile settings changed.

Evidence: `data/processed/sample2022-2023/` (acquisition/quality JSON, SQLite, Parquet, scan receipts) and `artifacts/reports/` (detailed quality and final-capacity reports). Generated data stays outside Git. Test fixtures are explicitly synthetic.
