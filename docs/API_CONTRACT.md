# Phase 4 prediction / explanation contract

Phase 4 implements this contract in `backend/app.py` and `frontend/`. It uses unchanged `pipeline.serving.load_release`, `predict_case` and `open_snapshot`; preprocessing is not reconstructed in the API. No training, uploads or source access occurs at runtime.

## Trusted artifacts and versions

Repository-controlled `docs/serving_release.json` pins release `btp-exploratory-v1`, internal data version `dvsa-2022-2024-splitmix1000-v1`, and the external trusted manifest SHA256. Pass that expected digest to `load_release(directory, expected_manifest_sha256)`. It verifies every declared file/size and exact Python-minor/dependency versions before loading the locally generated joblib. Never deserialize uploaded or otherwise untrusted models. Hashes prove integrity against a trusted descriptor, not publisher authenticity or a signature. See [scikit-learn persistence security guidance](https://scikit-learn.org/stable/model_persistence.html).

The release contains bundle/preprocessing, feature schema, aggregate exploratory metrics, model card, frozen protocol/audit and one bounded SQLite snapshot. Dependencies are locked in `requirements-model.lock` (including the unchanged data lock). No runtime download, training, source refresh or network explanation call.

## Prediction request

Only these top-level keys are supported:

| Key | Required value / meaning |
| --- | --- |
| `vehicle_class` | 4 |
| `component_family` | `brakes` |
| `test_type` | `NT`, normal inspection |
| `test_result` | `P`, strict pass; PRS is unsupported as index |
| `features` | Object with only the four fields below |

| Feature | Validation / preprocessing |
| --- | --- |
| `vehicle_age_years` | Numeric or null; nonfinite/negative becomes missing. Age at index, not today. |
| `mileage` | Numeric or null; nonfinite/nonpositive becomes missing. Recorded source reading; older/later odometer-unit/revision limitations remain. |
| `brake_advisory_count` | Required finite positive integer; deduplicated current brakes-A item count. |
| `advisory_count` | Required finite positive integer, at least brakes count; current A advisories across families. |

JSON booleans/strings are not numeric features. Missing age or mileage is imputed using frozen training medians, with training-learned missing indicators and scaling. Both missing gives `insufficient_data`, no score. No arbitrary performance-derived cutoffs; finite values outside the training range are explicitly flagged as extrapolation. Unexpected fields—including IDs, postcode, recurrence and outcomes—are rejected, never silently used. Minor-M items are not A counts. No inferred repair status.

## Response and states

Always return `model_version`, `data_version`, `status`, nullable `exploratory_prioritization_score`, `recurrence_used_by_model=false`, `probability_reliability="unestablished"`.

- `scored`: 0–100 exploratory score; **not a calibrated failure percentage**, safety tier or inspection substitute. Return `imputed_features`, `outside_training_range`, and the warning. Do not add high/medium/low or safe/unsafe categories.
- `insufficient_data`: unknown required counts or both age/mileage unusable; score null, explicit reasons. Never turn insufficient data into zero risk.
- `unsupported_scope`: different class/family/test type/outcome; score null, explicit reasons.
- `invalid_input`: unknown fields, nonnumeric values or invalid/inconsistent counts; score null, explicit reasons.
- Artifact missing/checksum/version failure: fail startup or report service unavailable. Never silently substitute a different model or unverified bundle.

Implemented HTTP mapping: scored/insufficient 200, invalid/unsupported 422, unavailable artifacts 503. Unknown cases return 404. Malformed JSON returns 422; prediction request bodies over 16 KiB return 413. Response numeric scores retain full precision; the dashboard rounds only for display.

## Deterministic explanations

`explanation.intercept_log_odds + sum(explanation.terms[].log_odds_contribution)` reconstructs the model margin; sigmoid ×100 reconstructs the score. Terms are frozen coefficients times standardized/imputed current inputs (and learned missing indicators), relative to training-centered transformed values. They are associations, not causes, mechanical diagnoses or proof of identical-part failure. Keep all terms when presenting a mathematical decomposition; a shortened display must not claim omitted terms are zero. No GenAI feature is implemented.

Recurrence is a **separate descriptive panel**: earlier recorded normal brakes advisories/failures, number of observed prior tests and observed-history days. Its data carries `model_input=false`, `predictive_value="unvalidated"`, and `prior_absence_confirmed=false`. Absence of a record is not confirmed absence before 2022. A repeated family advisory does not establish ignored repair or the same physical part. Changing this panel must not change a score.

## Read-only serving snapshot and evaluation separation

`snapshot.sqlite3`: 200 cases, 532,480 bytes; three tables only:

- `metadata(key,value)`: versions, source-history start 2022-01-01, queue as-of 2024-12-31, explicit historical-demo status.
- `followup_queue(case_id,index_date,inputs_json,prediction_json)`: opaque local case ID, current-inspection inputs and deterministic score response. No vehicle/test IDs, postcode, next test, observed label or future outcome columns.
- `descriptive_history(case_id,history_json)`: FK to queue; descriptive history only, not model predictors.

Choose the latest uniquely dated inspection per vehicle, require it itself to be an eligible NT/P/brakes-A anchor, then take a fixed outcome-independent hash sample capped at 200. Do not filter on observed outcomes/censoring or select known failures. Input dates in this demonstration span 2022-01-12–2024-12-28: **some cases are stale**, not a current/live 2026 fleet queue. Always show index date, historical as-of banner and staleness context. Scores use age/mileage at the index. Future list pagination/order can rank stored exploratory score, with case ID as deterministic tie-break; insufficient cases must remain visibly unscored.

Open through `mode=ro&immutable=1` and `PRAGMA query_only=ON`; file is marked read-only and write attempts are tested. Historical evaluation labels/predictions live separately in ignored `artifacts/evaluations/btp-exploratory-v1/historical-evaluation.parquet`, not in this snapshot or prediction inputs. Aggregate metrics are a separate release JSON resource; never join row-level evaluation outcomes into the follow-up queue. The retrospective releases were not proven publicly available at the historical freeze.

## Implemented HTTP routes (API v1.0.0)

| Method / path | Contract |
| --- | --- |
| `GET /api/health` | Liveness, even if artifacts unavailable. |
| `GET /api/ready` | 200 only after trusted load, schema/version validation and exact agreement for every stored case prediction; otherwise 503. |
| `GET /api/versions` | Model/data/API versions, manifest digest, demo/evaluation counts, historical as-of and history start. 503 when unverified. |
| `GET /api/cases` | `{items,total,limit,offset,scope}`; date descending then case-ID ascending. Optional ISO `date_from`/`date_to`, inclusive and ordered. |
| `GET /api/cases/{case_id}` | Unique index-inspection case with index inputs, fresh frozen prediction, separate descriptive history, history boundary/resolution and as-of. No source vehicle ID or subsequent outcome. |
| `GET /api/cases/{case_id}/prediction` | Same Phase 3 prediction response. |
| `POST /api/predict` | Exact allowlisted Phase 3 payload above; no model upload, code, identifiers, history or outcomes accepted. |
| `GET /api/queue` | `{items,requested_capacity,selected,eligible,unscored,exceeds_available,limit,offset,scope,tie_break,as_of}`. Ranked summaries include rank, case ID, date, current features, status and unrounded score. |
| `GET /api/evaluation` | Unchanged verified `metrics.json`: full 936-example saved evaluation, never demo-subset metrics. |
| `GET /api/methodology` | Verified protocol, model card and feature schema. |
| `GET /api/openapi.json` | Local OpenAPI schema; no CDN-backed interactive docs or runtime external scripts. |

Lists default to `limit=20`, `offset=0`; limits 1–100, offsets 0–10,000. Queue `capacity` is an integer count 0–500 (default 40), capped to eligible scored cases. Zero gives an empty selection; insufficient cases are explicitly counted, excluded from ranking and accessible via cases. Overcapacity is explicit, not an error or invented population. Ranking uses score descending, case ID ascending, independent of outcomes. This is a demo tie-break, not a redefinition of the separately frozen evaluation tie-break. Requests changing demo capacity cannot modify evaluation artifacts; evaluation has only saved 10/20/30% operating points. SQLite uses parameterized queries, read-only immutable connections, query-only pragma and bounded pages.

## Compatible presentation clarification

Actual export inspection verified that history contains **aggregate prior counts and observed duration**, not dated prior inspection rows or individual item descriptions. The dashboard presents these available records as aggregate history through the index, and current advisories as counts. It explicitly states the missing detail rather than reconstructing a timeline, accessing staging data or altering the frozen snapshot. The original artifact hashes/versions remain unchanged. Case IDs identify index inspections, not vehicles, even though this bounded snapshot selected at most one eligible latest inspection per vehicle.

The production React build is served on `/`, `/queue`, `/cases/{16-hex-case-id}`, `/evaluation`, `/methodology`. Unknown `/api` routes, missing assets and unknown pages return 404, never SPA HTML. Missing build returns 503 on valid frontend routes. DVSA/OGL attribution, retrospective/stale-case scope, exploratory limitations and descriptive recurrence separation are visible in the UI. No container/cloud resources have been created.
