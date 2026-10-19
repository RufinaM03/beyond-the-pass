# Phase 3: bounded retrospective exploratory evaluation

Completed 2026-10-19 using processed data only. No additional years downloaded or raw archives rescanned. Original pipeline, 6,642 reconstructed labels, cohorts and Phase 2 split are preserved. No API, UI, Docker or AWS work.

## One split audit, before predictions

All labelled examples have exactly one reference disposition:

| Reference disposition | Count |
| --- | ---: |
| Selected training | 705 |
| Selected holdout | 183 |
| Outside the two reference index windows | 4,804 |
| Training-window examples reserved by holdout vehicle role | 197 |
| Holdout-window examples reserved by training vehicle role | 753 |
| **Total** | **6,642** |

The reference's small holdout mainly reflects its approximately 20% vehicle-role restriction, not invalid labels. One usable annual index per vehicle inside each quarter is structural: a second NT inside that quarter would be the first index's immediate next NT, below nine months; both cannot be labelled annual examples. No performance-based case deduplication.

Candidate dates were examined using maturity/counts only, with no model results:

| Freeze | Fully mature training indices end | Training examples / positives | Fully mature post-freeze evaluation examples / positives |
| --- | --- | ---: | ---: |
| 2023-07-01 | 2022-03-31 | 902 / 88 | 936 / 76 |
| 2023-08-01 | 2022-04-30 | 1,052 / 102 | 641 / 47 |
| 2023-09-01 | 2022-05-31 | 1,239 / 128 | 344 / 21 |
| 2024-01-01 | 2022-09-30 | 2,335 / 240 | 0 / 0 |

Evaluation ends at the latest fully 15-month-mature index date, **2023-09-30**, with outcomes observed through **2024-12-31**. A 2024 prediction cohort has no fully mature 15-month window in these data. Later freezes trade away evaluation months, rather than providing a larger mature holdout. Partial-maturity cases were not mined to inflate training/evaluation counts.

### Fixed primary choice

Keep freeze **2023-07-01 00:00 UTC**, training indices **2022-01-01–2022-03-31**, evaluation indices **2023-07-01–2023-09-30**, and individual immediate-next-NT 9–15-calendar-month labels. Training outcome envelope: 2022-10-01–2023-06-30; evaluation envelope: 2024-04-01–2024-12-30. Every actual training label proxy precedes the freeze; every evaluation index follows it. No source-release-at-the-time claim: these are retrospective event/completion timestamps, not reconstructed public-data availability.

Use all eligible vehicles rather than the artificial role restriction: **902 training examples/vehicles (88 positive, 814 negative)** and **936 evaluation examples/vehicles (76 positive, 860 negative)**. Total 1,838 selected, with 4,804 labelled cases outside the windows, accounting for all 6,642. The original 705/183 split is a preserved reference, not silently overwritten.

Intended use is temporal follow-up prioritization, potentially on a previously observed fleet, using only information available at each index. IDs are never predictors. Separately report unseen-vehicle generalization as evaluation vehicles absent from training. In this particular window **all 936 evaluation vehicles are unseen** (zero overlap), so secondary metrics equal primary metrics. This is the same evidence, not independent confirmation, and does not measure performance on previously seen vehicles. No forced hash-role separation is needed.

Audit/protocol were pinned before predictions in `docs/phase3_protocol.json` and ignored `artifacts/evaluations/btp-exploratory-v1/split-audit.json`; reference accounting is also persisted as Parquet. Audit re-runs are protected, not repeatedly redesigned after scores.

## Current features, not recurrence prediction

| Recorded history | Training | Evaluation |
| --- | ---: | ---: |
| Any prior test | 18 | 887 |
| Prior normal brakes advisory | 14 | 296 |
| At least 365 days observed history | 0 | 445 |
| Median history days | 0 | 364 |
| Missing mileage change | 885 | 75 |

Training's first-quarter 2022 indices are left-truncated by the dataset boundary. Sparse recurrence is not evidence that advisories were absent. The model therefore uses **age, mileage, current brakes-A count and current total-A count only**. History/recurrence/mileage changes, identifiers, postcode and future outcomes are excluded. Recurrence remains a descriptive panel; **its predictive value is unvalidated**.

Invalid/nonfinite age or nonpositive mileage becomes missing; frozen training medians plus missing indicators handle it. Both age/mileage missing gives an insufficient-data state for serving. Counts must be known positive integers with total ≥ brakes. Unsupported classes/families/types/outcomes are explicitly rejected. Range extrapolation is flagged, not recast as certainty or hidden behind invented thresholds.

## Fixed specification and honest results

Training-only median imputation → standard scaling → L2 logistic regression, C=1, lbfgs, tolerance 1e-4, max_iter=1000, no class weighting, seed 2026. No hyperparameter search, threshold tuning, calibration, tree ensemble or production-winner selection. There is no independently mature chronological development partition; this is a fixed exploratory specification. Constant probability is **training prevalence 88/902 = 0.097561**, not holdout prevalence. Ranking baseline is descending current brakes-A count; it is not a probability forecast.

Follow-up capacities **10%, 20%, 30%** were fixed before predictions; select `ceil(capacity × n)`. Ties use SHA256 of a fixed salt plus test ID, independent of outcomes; IDs are audit tie-breakers, not predictors. AP treats score ties as groups, so the constant AP equals evaluation prevalence.

| Method | Average precision | Evaluation prevalence | Brier score |
| --- | ---: | ---: | ---: |
| Constant training prevalence | 0.081197 | 76/936 = 0.081197 | 0.07487149 |
| Current brakes-A count ranking | 0.083101 | 0.081197 | Not defined: no probability forecast |
| Fixed logistic regression | 0.113897 | 0.081197 | 0.07473054 |

| Method | Capacity / selected | Positives found | Precision | Recall |
| --- | --- | --- | ---: | ---: |
| Constant | 10% / 94 | 7/94; 7/76 positives | 0.074468 | 0.092105 |
| Constant | 20% / 188 | 17/188; 17/76 | 0.090426 | 0.223684 |
| Constant | 30% / 281 | 24/281; 24/76 | 0.085409 | 0.315789 |
| Count ranking | 10% / 94 | 8/94; 8/76 | 0.085106 | 0.105263 |
| Count ranking | 20% / 188 | 16/188; 16/76 | 0.085106 | 0.210526 |
| Count ranking | 30% / 281 | 23/281; 23/76 | 0.081851 | 0.302632 |
| Logistic | 10% / 94 | 10/94; 10/76 | 0.106383 | 0.131579 |
| Logistic | 20% / 188 | 21/188; 21/76 | 0.111702 | 0.276316 |
| Logistic | 30% / 281 | 35/281; 35/76 | 0.124555 | 0.460526 |

Logistic-minus-constant Brier difference is only **-0.00014095**. Report all methods; no production winner, statistical-significance, calibration or safety-category claim follows. The serving logistic specification was chosen before these comparisons. User-facing output is an **exploratory prioritization score**, not a reliable failure percentage. Only 76 positives, a season-shifted quarter, conditional observed-follow-up selection/censoring and source revisions limit generalization. No uncertainty intervals/bootstrap were calculated.

## Exported and checked

Ignored release directory: `artifacts/releases/btp-exploratory-v1/`:

- `bundle.joblib`: 1,529 bytes, fitted preprocessing + fixed model, feature order/ranges and versions; trusted local loading only.
- `feature-schema.json`, `metrics.json` (raw counts/exploratory flags), `model-card.md`, frozen `protocol.json` / `split-audit.json`.
- `snapshot.sqlite3`: **200 cases, 532,480 bytes**, file marked read-only, query-only immutable connection and write-attempt checks. Current inputs/predictions and descriptive history are separate tables. No row-level evaluation outcomes, source vehicle/test IDs or postcode are included.
- `release-manifest.json`: every artifact hash/size, dependencies, code hashes and source-cohort hash. Repository-controlled expected digest is in `docs/serving_release.json`.

Evaluation outcomes/probabilities are separate in `artifacts/evaluations/btp-exploratory-v1/historical-evaluation.parquet`. The serving snapshot uses each vehicle's latest uniquely dated eligible inspection, then an outcome-independent capped hash sample. Index dates span 2022-01-12–2024-12-28, explicitly a historical demonstration as of 2024-12-31, **not a live/current queue**. All 200 score successfully; insufficient/unsupported states are covered by synthetic tests. See [API_CONTRACT.md](API_CONTRACT.md) for the prediction/explanation and recurrence-panel boundaries.

Exact load-round-trip predictions and all 936 historical predictions/metrics are reconstructed without refitting. Imputer medians/scaler means/sample count independently match **902 training rows only**. All 200 stored scores/explanations reconstruct; snapshot writes fail. Original 6,642 labels/Phase 2 artifact hashes remain unchanged. The 40 tests include all original 30, temporal-guard rejection and pre-deserialization corruption checks. Full dependency lock consistency and compilation are checked; no additional source transfer or raw scan occurred. Fresh model-run peak working set was about 183 MiB, private commit 209 MiB; D: remained about 60.33 GiB free.

## Reproduction and next phase

Explicit project Python 3.12, D: cache/temp via wrapper:

```powershell
.\scripts\data.ps1 -Command SetupModel
# Only on a fresh artifact directory, with preserved processed inputs:
.\scripts\data.ps1 -Command Audit
.\scripts\data.ps1 -Command Model
# Existing release: no audit, fitting, raw reads or overwrite required:
.\scripts\data.ps1 -Command Verify
.\scripts\data.ps1 -Command Test
```

Audit and release directories are protected from overwrite. Restore the exact processed-data snapshot/locks/protocol for independent reproduction; original data/acquisition remains untouched. SHA256-pinned descriptor and dependency checks precede joblib deserialization; do not load untrusted bundles or treat hashes as signatures. See [official persistence guidance](https://scikit-learn.org/stable/model_persistence.html).

**One future-validation recommendation, not an expansion loop:** pre-2022 authoritative history would address comparable recurrence/mileage-history coverage (with older unit validation), but not prove calibration; 2025 outcomes would mature a predeclared 2024 evaluation and reduce dependence on a single 2023 quarter; a larger outcome-independent sample would improve event-count precision but not cure left truncation, follow-up selection or source timing; actual archived-release/revision metadata or prospective logging is needed for real as-of availability. Predeclare that validation once before new scores, preserve vehicle grouping if estimating uncertainty, and acquire nothing now.

**Exact next step: Phase 4 API and dashboard.** Consume the fixed trusted bundle, bounded read-only snapshot and aggregate metrics; expose versions/insufficient states, exploratory caveats and separate descriptive recurrence. No AWS/Docker/provisioning or data refresh is part of Phase 3.
