# Phase 1B / 2: real-data cohort and readiness

Completed 2026-10-19. No training, model metrics, serving snapshot or deployment. Brakes remains provisional. Protocol was declared before larger acquisition/counts in [PHASE2_PLAN.md](PHASE2_PLAN.md).

## Acquisition: complete versus pending

- Reused all four verified 2022–2023 ZIPs; none downloaded again. Added **24 complete June 2026 2024 CSV members: 9,127,357,646 bytes (8.501 GiB)**, sequentially on D:. Exact supported HTTP ranges, parent ETags, member CRC32/SHA256, sizes and retrieval dates are in `docs/member_manifest.json`.
- The enclosing 2024 ZIPs were **not** fully downloaded/checksummed; the original parent-source manifest is preserved. Member completeness is separate from parent ZIP status. The competing March 2025 pair was not mixed in.
- **2025 remains pending and was not needed** for the narrower mature 2023-Q3 holdout below. Its paired files would add 8.564 GiB. They would be needed for a mature 2024 prediction cohort, not retroactively substituted to improve the present holdout counts.
- Complete 2024 histories are needed to detect intervening normal tests and all possible 9–15-month outcomes. January-only diagnostics passed before the other eleven months were acquired. January: 247 linked 2023 IDs, zero checked attribute changes, 776 joined/mapped items.

All monthly headers, actual required identifiers, dates, outcomes, test/item codes and completion ordering were checked during full scans. Result free text contains nonstandard literal quotes: **56** exact-width literal-quote records and **202** standard quoted records among 42,637,055 result records. No ambiguous rows were skipped. Initial apparent timestamp anomalies came from multiline parser misalignment; they were not accepted as valid records. The independent physical January count agrees with the validated adapter. The faster numeric item reader independently reproduces January's **8,413,394** rows; blank/extra-field records fail tests.

## Sample, coverage and linkage

Fixed SplitMix64 `hash % 1000 == 0`, tenfold expansion, independent of outcomes. Every available test type is retained for selected vehicles; all result years precede item joins. Complete histories are limited to acquired 2022–2024 and the published source IDs, not pre-2022 life histories or recovery across ID changes.

| Source | Full rows scanned | Retained |
| --- | ---: | ---: |
| 2022 results | 41,632,878 | 41,307 |
| 2023 results | 42,216,721 | 41,813 |
| 2024 results | 42,637,055 | 42,261 |
| 2022 items | 86,352,508 | 86,073 |
| 2023 items | 89,302,632 | 87,444 |
| 2024 items | 91,827,424 | 90,347 |

**38,409 vehicles / 125,381 tests / 263,864 items**; full source scans total 126,486,654 result and 267,482,564 item records. Selected date ranges: 2022-01-03–2022-12-31; 2023-01-02–2023-12-30; 2024-01-02–2024-12-31. Source-result scans cover January 1–December 31 each year; selected dates are not population coverage claims.

- **29,969 vehicle IDs link 2023 to 2024**. Exact two-year checks find zero make changes, **18 model** and **87 first-use-date** changes. Including earlier 2022 records gives 21 model changes among those IDs. The 2022–2023 baseline already has three model changes among 29,671 linked IDs, but no first-use changes.
- First-use boundary changes are not just a one-day conversion: observed changes range from -11,567 to +365 days. Their cause is unestablished; do not call them confirmed corrections or silently normalize them. Raw attributes are retained; inconsistent immediate label pairs are excluded (16 overall, two assigned holdout examples). ID overlap supports linkage for the checked data, not infallible identity or exact cross-release equivalence.
- All retained items join through verified test IDs; zero source-year mismatches and duplicate test IDs. **618 duplicate item rows** remain in raw staging; feature counts use distinct item keys.
- **14 unmapped items are all class 5**, across RFR IDs 30006/30012/31194. They remain unknown, never guessed into class 4. No class-4 anchor/follow-up pair has an unknown mapping. Current dictionaries have verified unique class-qualified keys/ancestry.
- Nine F tests and one PRS test have no items across the retained sample. These are insufficient failure evidence, not valid negatives. One annual cohort pair is excluded for conflicting/missing failure items. Conversely, **49,221 P tests** legitimately have no recorded items; absence alone is not a broken join.
- All **8,274 original sample tests** remain, with zero field disagreements; every original item key/multiplicity remains. Thus the original 349-vehicle pilot and 3,584-vehicle sample are preserved subsets. SQLite integrity, receipt/Parquet counts, deterministic membership and SHA256 checks pass.

## Annual brakes cohort and attrition

Funnel: 125,381 retained tests → 118,434 class 4 → 98,211 normal NT → 69,963 strict P passes → **11,865 brakes-A advisory anchors**. Immediate next NT only; never skip an early/incomplete/class-changed routine test. Inclusive 9–15 calendar months, not 270–450 days or the old Phase 1 1–550-day diagnostic.

This is a conditional recorded-next-annual-test outcome, not unconditional mechanical-failure risk or proof of failure within a fixed survival horizon. Observed-follow-up selection and censoring remain limitations.

| Mutually exclusive primary disposition | Examples |
| --- | ---: |
| Labelled | 6,642 |
| Missing follow-up (primary reason) | 4,593 |
| Next NT outside 9–15 months | 531 |
| Same-day ambiguity | 56 |
| Incomplete next NT | 23 |
| Conflicting vehicle attributes | 16 |
| Class change | 3 |
| Conflicting/missing failure items | 1 |

Overall categories: **6,642 labelled / 4,603 censored / 620 excluded**. Overlapping flags differ from the primary table: missing follow-up 4,603 (4,171 administratively immature); out-of-window 557; incomplete 41; same-day 56; index unavailable before follow-up 14 (overlapping ambiguity). No censored/excluded record is a negative.

Labelled total: **694 positive / 5,948 negative**. Same-family item F or rectified-P is positive; PRS is failure at presentation, not a clean-pass index. There are 678 F-item positives and 16 rectified-P positives. Other-component failures can be brakes-negative only with otherwise complete/consistent evidence. Intervening repairs and physical part identity are unobserved.

## Predeclared retrospective evaluation timeline

| Partition | Index dates | Per-example outcome interval / overall envelope | Availability gate |
| --- | --- | --- | --- |
| Train | 2022-01-01–2022-03-31 | Index +9 to +15 calendar months; 2022-10-01–2023-06-30 | Strictly before **2023-07-01 00:00 UTC** freeze |
| Holdout | 2023-07-01–2023-09-30 | Index +9 to +15 calendar months; 2024-04-01–2024-12-30 | Observed by 2024-12-31 end-of-day |

Fixed outcome-independent vehicle role: `(hash // 1000) % 5 == 0` holdout; otherwise training. The approximately 80/20 split is defined for the modulus-1000 sample. Other index windows stay unused, not post-hoc tuning data.

| Actual count | Train | Holdout |
| --- | ---: | ---: |
| Advisory anchors in index window | 1,044 | 1,081 |
| Labelled before vehicle-role restriction | 902 | 936 |
| Anchors assigned matching vehicle role | 819 | 205 |
| Assigned censored / excluded | 52 / 62 | 13 / 9 |
| Final examples / distinct vehicles | **705 / 705** | **183 / 183** |
| Positive / negative | **67 / 638** | **13 / 170** |
| Rectified-P positives (included) | 3 | 1 |

Assigned training exclusions: 55 out-of-window, six ambiguous, one incomplete. Assigned holdout exclusions: seven out-of-window, two conflicting attributes. **Zero vehicle overlap**. Latest actual training-label proxy: 2023-06-19 end-of-day; earliest evaluated prediction proxy: 2023-07-03 end-of-day. Holdout-label proxies span 2024-04-17–2024-11-06. All 6,642 labelled pairs independently pass SQL immediate-next-NT checks, calendar bounds and brakes F/P label reconstruction.

These are **retrospective event-time** partitions. Old data has no completion/publication field; end-of-day is a conservative event-date proxy. New labels use the maximum of end-of-day and result/item completion timestamps. Authoritative completion/revision semantics remain undocumented, and these public files were released after the historical freeze. Do not claim actual historical public-data availability or an as-of-revision deployment backtest. No training or performance evaluation occurred.

## Features and readiness

Seventeen numeric allowlisted inputs cover index age/mileage/advisories, valid historical mileage changes, recorded component history/recurrence and observed history length. No identifiers, postcode, targets or future measurements enter feature files. Feature/audit row alignment, numeric schemas, file/code hashes and temporal guards pass. No imputation or fitting has occurred. See [DATA_CONTRACT.md](../DATA_CONTRACT.md) for exact semantics.

| Historical coverage in final partitions | Train | Holdout |
| --- | ---: | ---: |
| Any earlier recorded test | 13 | 175 |
| Prior normal brakes advisory / recurrence | 10 | 59 |
| Recurrence-positive / recurrence-negative outcomes | 1 / 9 | 4 / 55 |
| At least 365 days observed history | 0 | 85 |
| Median observed history, days | 0 | 364 |
| Missing valid mileage delta | 693 | 12 |
| Missing current mileage | 2 | 1 |

**Not ready for training a credible recurrence model.** Training history is heavily left-truncated: ten recurrence examples with one positive, versus 59 in holdout. Those training recurrences come from short-interval first-quarter records, not an observed earlier annual cycle. Missing earlier records are not confirmed advisory absence; mileage-change coverage also differs sharply between partitions. The holdout has only 13 positives; it covers one season-shifted quarter, not a year. No independently mature chronological tuning partition exists under this protocol. Unknown first-use revisions and exact availability also need review. Keep the fixed split; do not enlarge/select cases by known future failure or change dates to improve counts.

Next decisions: validate authoritative pre-2022 history (including the guide's older mileage-unit caveat); clarify source revisions/availability; predeclare any larger sample or broader holdout and its disk-backed-join/capacity plan. The present 125,381-test index fits the 200,000 cap; simply reducing the modulus further would require that join change. No automatic rescans or 2025 transfers.

## Traceable real examples (not synthetic)

| Outcome | Index NT/P with brakes A | Immediate next NT | Evidence |
| --- | --- | --- | --- |
| Positive | Test **659670975**, vehicle 158053327, 2022-01-05 | **187925805**, 2023-01-24, F | Index RFR 30335 A; next brakes RFR 30478 F. Same family, not proof of the same part. |
| Negative | **42263459**, vehicle 1274414948, 2022-01-03 | **1969085237**, 2023-01-14, P | Index brakes RFR 30333 A; next has only other/tyres advisories, no brakes failure. |
| Censored | **585085235**, vehicle 559694224, 2022-01-04 | None recorded through acquired 2024 | Brakes RFR 30478 A; label remains null, not negative. |

Each has zero earlier observed history at the index, not a confirmed absence before 2022. Full test/item traces are in ignored `data/processed/expanded2022-2024/real-example-traces.json`, traceable by test ID in staging SQLite and source receipts. Open-data provenance/attribution: [acquisition documentation](ACQUISITION.md).

## Capacity, checks and reproduction

Six sequential full scans took **2,382.69 seconds**. Observed worker peak working sets: legacy results 1.30 GiB maximum; newer results 209 MiB; item workers 159/165/189 MiB. Cohort construction peaked at **624 MiB** (private commit about 600 MiB). These are measurements, not hard memory bounds. Sampled numeric item-join index: **1,003,048 bytes**; no population-size ID set.

Final measured raw cache: 12,380,615,779 bytes; expanded artifacts: 70,726,871 bytes. D: about 60.57 GiB free, RAM 3.23 GiB available, commit headroom 1.16 GiB; recheck before further processing. All data/cache/scratch stays on D:, no system changes. Original dependencies and scaffold remain intact.

Commands: `scripts/data.ps1 -Command FetchJanuary`, `ValidateJanuary`, `Fetch2024`, `Expand`, `Cohort`, `Test`; full commands/recovery in [PHASE2_PLAN.md](PHASE2_PLAN.md). Existing verified caches are reused; existing complete expansion directories are protected. Detailed local evidence: `acquisition.json`, six scan receipts, `cohort-report.json`, `brakes-cohort.parquet`, feature/audit Parquet files and `feature-manifest.json` under `data/processed/expanded2022-2024/`; independent checks in `artifacts/reports/phase2-*.json`. Raw/generated data remains outside Git.

Final acceptance checks: **30 tests pass** (original 12 preserved), dependency/lock consistency and compilation pass; all 6,642 labelled pairs independently reconstructed; feature/code hashes and numeric allowlist pass; 33 reviewable files have valid document links/clean whitespace and no exposed generated data. Source-change detection reports no changes and never replaces data or trains.
