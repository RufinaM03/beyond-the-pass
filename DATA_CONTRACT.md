# Data contract (verified sources; annual cohort construction)

## Phase 4 HTTP presentation boundary

The API serves only the hash-verified `btp-exploratory-v1` release via read-only SQLite, unchanged Phase 3 inference and saved aggregate metrics. No acquisition, label/cohort changes or fitting. Actual exported schema has 200 unique index-inspection case IDs, current inputs/predictions and **aggregate** prior-history counts/duration, not individual advisory descriptions or a dated history timeline. Show that limitation explicitly. History is descriptive through each index; subsequent outcomes stay absent from serving data. Evaluation remains the separate saved 936-example cohort regardless of queue capacity. See `docs/API_CONTRACT.md` for implemented bounds, routes and failure states.

## Phase 3 exploratory model / serving contract

The preserved annual labels and Phase 2 cohorts are unchanged. Phase 3 authorizes a fixed **current-inspection-only** exploratory model, not recurrence prediction or production readiness. The primary temporal split keeps the same mature 2022-Q1 training / 2023-Q3 evaluation windows and 2023-07-01 freeze, without hash-role restriction: 902 / 936 examples. Secondary unseen-vehicle evaluation happens to equal primary (zero overlap); the original 705/183 reference remains intact. Every training outcome precedes freeze and every evaluated index follows it, using retrospective event-time proxies, not proven historical public-release availability.

Model inputs are exactly `vehicle_age_years`, `mileage`, `brake_advisory_count`, `advisory_count`. Numeric invalid/missing policies, training-only imputation/scaling, fixed regularized logistic specification, baseline/ranking ties, raw metrics, capped snapshot and integrity versions are in `docs/phase3_protocol.json`, `docs/PHASE3_REPORT.md` and `docs/API_CONTRACT.md`. All other 17-feature research-table fields remain available for audit, **not automatically predictors**. Recurrence/history is descriptive and its predictive value unvalidated. User output is an exploratory prioritization score, not a calibrated probability or high/medium/low safety category. Historical evaluation labels remain separate from prediction inputs and follow-up queue. Snapshot is explicitly a stale-capable historical demonstration as of 2024-12-31.

## Phase 2 contract (supersedes preliminary 1–550-day diagnostic)

The original Phase 1 comparison below remains reproducible, but its 1–550-day labels are NOT the Phase 2 annual-test target. Phase 2 uses class 4 and provisionally brakes. Index: `NT/P` with a class-qualified mapped brakes `A` item. Follow-up: the immediate next `NT` across classes, excluding non-NT retests/appeals without skipping any earlier NT. Require an inclusive **9–15 calendar-month** interval (`DateOffset` month arithmetic). Same-day ambiguities, class/identity changes, incomplete tests, contradictory result/item evidence and unknown pair mappings are excluded with all reasons retained. No follow-up is censored, never negative. `PRS` is not an index; next-test brakes `P` (rectified failure) counts positive alongside `F`. An otherwise consistent failure in another component counts negative for brakes; itemless `P` may be negative.

The newer June 2026 schema has a separate adapter in `pipeline/expansion.py`. Complete stored monthly CSV members are acquired through validated exact ranges; parent archives are not claimed downloaded or fully SHA256-verified. `docs/member_manifest.json` records member URL, parent ETag/size, byte range, CRC32, SHA256 and retrieval date. Standard CSV quoting coexists with occasional literal unbalanced quote characters in result free text. Parse result records one physical line at a time: strict CSV where quoted; literal comma fields are accepted only when the exact expected column count is unambiguous. Numeric/code item CSVs use bounded pandas C-reader chunks with literal quote handling, parser warnings treated as errors and no blank-line skipping. IDs, codes, dates, month coverage and completion ordering still must validate; ambiguous rows fail, none are skipped. The initial apparent before-test completion dates were a multiline parser artifact, not accepted timestamp anomalies. See the diagnosis and actual scan receipts.

Index-only allowlisted features: age; recorded mileage; nonnegative change from a prior unambiguous positive mileage reading and elapsed days/annualized change; rollback flag; current advisory counts; earlier recorded test/normal-test counts; prior normal class-4 brakes advisory/failure counts; recorded recurrence and its recency; observed history duration; prior-mileage availability; prior unknown-mapping count. Identifiers, postcode, future outcomes and future mileage are audit-only, never model inputs. Same-day conflicting prior readings do not provide a valid mileage delta. Feature counts deduplicate identical item keys; raw duplicate rows remain retained and reported. Missing values remain missing; no fitted preprocessing or training occurs.

Prior component history counts normal class-4 tests before the index date; retests remain in recorded-history/mileage observations but not normal-inspection recurrence counts. A zero prior-advisory count means none observed in acquired history, not a confirmed absence before 2022. Family recurrence does not prove ignored repair or failure of the same physical part. The guide documents mileage conversion for 2022, but exact later odometer-unit correction semantics are not independently established; recorded nonnegative deltas are not guaranteed true distance travelled.

Predeclared windows, vehicle assignment and availability caveats: `docs/PHASE2_PLAN.md`. Training labels must strictly precede the model-freeze proxy, and train/holdout vehicles cannot overlap. Old records use end-of-test-day availability; newer labels use the maximum of end-of-test-day and result/item completion timestamps. Completion-field semantics/publication latency remain undocumented; this is retrospective event-time ordering, NOT proof that these later-published public archives were available at historical prediction dates. The model input tables contain ONLY the explicit feature allowlist; labels/identifiers/dates are separate audit tables.

## Question and cohort

For a class-4 normal test that passes with a component advisory, estimate whether a same-component failure is recorded at the vehicle's next normal test. Advisory presence is observable; whether it remained unresolved or was repaired between tests is not. Never present the label as proof of mechanical deterioration or an unperformed repair. Compare brakes and tyres before selecting a family; see `docs/QUALITY_REPORT.md` for actual evidence and the decision.

## Provenance and evidence levels

Official source: https://open.data.dvsa.gov.uk/mot-anonymised/index.html. The catalogue, post-May-2018 v5.1 ODT guide, original lookup ZIP, six current CSV dictionaries, and licence have been retrieved. The catalogue applies Open Government Licence v3.0, except where otherwise stated; preserve DVSA attribution and link to the licence. See `docs/ACQUISITION.md`, `docs/source_manifest.json`, and `docs/licence_manifest.json` for URLs, sizes, dates, release choices, and actual checksums.

2022–2023 annual archives are fully cached and checksum-pinned. Complete scans, row counts, and selected-vehicle checks are recorded per sample; only a completed acquisition may support history claims. All 24 June 2026 2024 CSV members are now fully cached, CRC/SHA256-verified and scanned through the explicit adapter; the parent ZIPs are not claimed downloaded. The competing March 2025 pair and the 2025 pair retain remote ZIP/header inspections only. Do not concatenate competing releases. Measured 2023–2024 linkage, attribute discrepancies, class-5 mapping unknowns and actual class-4 cohort exclusions are documented in `docs/PHASE2_REPORT.md`; linkage is supported, not guaranteed for every source identity.

The guide states that `vehicle_id` tracks a pseudonymous vehicle based on registration/VIN and `test_id` links result and item records. This is a documentation claim; measured cross-year overlap and attribute consistency are reported separately. It is not a guarantee that IDs cannot change when source vehicle details change.

## Actual schemas

Verified 2022–2023 headers are pipe-delimited with a header row. Dates observed in result records are ISO `YYYY-MM-DD`, despite the guide's suggested `DD-MM-YYYY` format. Use actual formats, not the guide's example DDL or suggested widths. IDs are parsed as signed 64-bit integers and must be nonnegative decimal integers; no floating-point ID joins.

Results, exact ordered columns:

```text
test_id|vehicle_id|test_date|test_class_id|test_type|test_result|test_mileage|postcode_area|make|model|colour|fuel_type|cylinder_capacity|first_use_date
```

Items, exact ordered columns:

```text
test_id|rfr_id|rfr_type_code|location_id|dangerous_mark
```

`test_id` is unique in retained results; duplicates fail insertion. Item rows are many-to-one with results, and multiple similar/identical items can occur. Report duplicate item rows; do not silently drop them. Component/test eligibility uses distinct tests, so duplicate items do not multiply prediction rows.

2024/2025 inspected headers are comma-delimited. Results add `completed_date`; items use `mot_test_rfr_location_type_id` in place of `location_id` and add `completed_date`. All 2024 members have now passed the separately validated adapter; 2025 full records remain unverified and unsupported by the targeted ingestion command. Do not use `completed_date` as a prediction feature. No annual-file schema is inferred from a filename.

Lookup ZIP members `item_detail.csv` and `item_group.csv` are pipe-delimited; the six current standalone dictionaries are comma-delimited. Detail keys are `(rfr_id, test_class_id)`; group keys are `(test_item_id, test_class_id)`. Validate key uniqueness and ancestor paths. Map families through exact hierarchy ancestor names: `Brakes` / `Motorcycle brakes`, or `Tyres`; do not classify every wheel/suspension item as a tyre defect. Unmapped items remain unknown. Class-4 cohort comparison avoids mixing vehicle inspection regimes.

The original detail dictionary has 21,069 keys; the current one has those keys plus 36, with no changed shared parent/section/category fields in the comparison performed. Use the pinned original lookup for the 2022–2023 pilot and report observed unknowns. Actual dictionary category values are `Pre-EU Directive`, `Major`, `Dangerous`, and `Minor`, rather than the guide's suggested abbreviations. Determine advisory/failure state from the annual A/F/P/M code, not category text alone. The annual `dangerous_mark` must not be treated as the post-2018 Dangerous category.

## Codes and sampling

- Normal/routine test: `test_type=NT`. Dictionaries also define `RT`, `PV`, `PL`, `EI`, `ES`; retain all available test types in history, but retests and appeals are not follow-up normal tests.
- Outcomes: `P` pass; `F` fail; `PRS` pass after rectification at station; `ABA`, `ABR`, `ABRVE` incomplete/aborted variants; `R` refused. Membership is verified against the published dictionaries; actual observed code counts are in scan reports.
- Item types: `A` advisory; `F` failure; `P` rectified failure; `M` minor defect. Minor defects are not advisories. Advisory cohorts require a strict `P` result and `A` item, excluding PRS anchors.
- Sampling uses fixed unsigned 64-bit SplitMix64 of numeric vehicle ID, selecting `hash % modulus == 0`. Keep this exact algorithm/version and modulus in acquisition metadata. It is order/chunk/year independent and outcome independent. The 1/100,000 pilot nests in 1/10,000 expansion.
- Retain every available test for selected vehicles within fully scanned acquired years, then filter items through the verified sampled test IDs across all acquired years. Do not claim complete pre-2022 or undownloaded 2024–2025 histories.

## Phase 1 diagnostic labels and leakage controls (historical)

- Anchor on a class-4 `NT/P` test with a mapped family `A` item. Use only information available at that test as future predictors.
- Order all `NT` tests per vehicle by actual test date. The immediate next `NT` is the follow-up; do not skip an incomplete test or a class change to find a later convenient result. Exclude ambiguous same-day anchor/follow-up normal tests because time-of-day order is unavailable.
- Usable follow-up: class 4, completed `P/F/PRS`, and gap 1–550 days. The fixed 550-day bound allows delayed annual tests but defines a specific recorded-next-test outcome, not a fixed-horizon survival estimate. Report missing follow-up and out-of-bound observations separately; exclusions can overlap.
- Positive: mapped same-family `F` or `P` item at the next normal test (failure as presented, including rectification at station). Also report `F`-only counts to distinguish unrepaired failures. A `PRS` result is not a clean pass at presentation.
- Negative: observed, otherwise usable follow-up with no same-family failure. Itemless `P` tests can be legitimate negatives. Exclude incomplete outcomes, class changes, unknown mappings in either test, contradictory pass/failure-item combinations, and failed/PRS tests without failure evidence; never convert those into clean negatives.
- No observed next test is censored/unknown, never negative. Archive cutoff and selected-vehicle date coverage are reported explicitly. The 2023-only pilot cannot identify next-year follow-ups.
- Fail ingestion on malformed required IDs/dates, unexpected schema/codes, duplicate retained test IDs, parser errors, or low capacity. Component mapping misses and pair exclusions are counted, not silently forced into a family.
- For evaluation require every training outcome date to precede the evaluated prediction dates, with vehicles disjoint across partitions. Never train on a 2022 anchor's 2023 outcome and then claim a prediction made before that outcome was observed. Fit preprocessing and any threshold selection using only eligible earlier data. No training has occurred.

The older files contain test dates but no separate completion/publication timestamp. Date-cut diagnostics therefore demonstrate retrospective event-date ordering, not a reconstruction of every historical data revision or exact real-time availability. Validate newer `completed_date` semantics and use outcome availability conservatively in later evaluation; never silently treat it as an anchor predictor.

## Processing and outputs
### Manual prediction mileage clarification

The cached official post-2018 guide (`data/sources/user-guide.txt`, line 395) states that 2022 kilometre readings were multiplied by 0.6213711922 to report miles. The frozen model trains on 2022 records; `pipeline/cohort.py::valid_mileage` retains positive source readings without further unit conversion. Manual input therefore uses **miles**, never another conversion. Exact correction semantics in later evaluation/demo releases remain independently unverified. This clarification does not alter source data, frozen features, model, metrics or snapshot. Missing age/mileage use only the existing frozen model handling; counts cannot be missing, and recurrence is not an input.


Read sources in bounded 25,000-row pandas chunks and write sampled Parquet plus an indexed SQLite staging database on D:. Use sequential isolated archive workers, one BLAS/OpenMP thread, and periodic collection of expired pandas wrapper cycles to bound retention. A numeric sampled-test join index is capped at 200,000 tests (1.6 MB); larger samples require a disk-backed join. Recheck RAM/disk/Windows commit headroom before stages and during chunks; keep a 5 GiB disk reserve and stop below 256 MiB available RAM or commit headroom. These are stop thresholds, not a claim that chunk size imposes a hard RSS cap. Resume requires matching completed-stage provenance/counts and preserves failed output separately.

Keep raw archives, generated datasets, models, and snapshots out of Git. Synthetic records are restricted to clearly labelled tests and never support evaluation claims. Source/checksum manifests and concise aggregate reports are reviewable source artifacts; detailed reports remain under ignored `artifacts/reports/` and `data/processed/`.

Phase 1 / 1B / 2 produce acquisition, cohort and feature evidence only, not a model, performance metrics, or serving snapshot. Future training must evaluate a baseline and modest candidate on real held-out data after readiness review. A future serving snapshot needs its own documented cap, sanitisation, schema/version, and read-only enforcement; the local staging database is not that demonstration release.
