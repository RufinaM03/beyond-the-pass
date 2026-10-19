"""Fixed exploratory baselines/model and bounded serving artifacts; no source scans."""

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import shutil
import sqlite3
import stat
import sys
import warnings
from contextlib import closing

from pipeline.evaluation import AUDIT, DATA, PROTOCOL, counts, load_cohort, partitions
from pipeline.pilot import capacity_gate, resource_snapshot
from pipeline.serving import MODEL_FEATURES, clean_features, load_release, open_snapshot, predict_case
from pipeline.sources import ROOT, checksum, now, save_json
import joblib
import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits


VERSION = "btp-exploratory-v1"
RELEASE = ROOT / "artifacts/releases" / VERSION
EVALUATION = AUDIT.parent
PACKAGES = ["numpy", "pandas", "pyarrow", "python-dateutil", "pytz", "six", "tzdata", "inflate64",
            "zipfile64", "scikit-learn", "scipy", "joblib", "narwhals", "threadpoolctl", "cloudpickle"]


def tie_key(identifier):
    return hashlib.sha256(f"btp-capacity-v1:{int(identifier)}".encode()).hexdigest()


def evaluate(frame, scores, probabilities, capacities):
    if len(frame) == 0:
        return {"status": "no_examples", **counts(frame)}
    labels = frame.label.to_numpy(dtype=int)
    scores = np.asarray(scores, dtype=float)
    if len(scores) != len(frame) or not np.isfinite(scores).all():
        raise ValueError("Invalid prediction array")
    ranking = sorted(range(len(frame)), key=lambda index: (-scores[index], tie_key(frame.iloc[index].test_id)))
    capacity_metrics = []
    positive = int(labels.sum())
    for fraction in capacities:
        selected = max(1, math.ceil(len(frame) * fraction))
        found = int(labels[ranking[:selected]].sum())
        capacity_metrics.append({"capacity_fraction": fraction, "selected": selected, "true_positives": found,
                                 "false_positives": selected - found, "all_positives": positive,
                                 "precision": found / selected, "recall": found / positive if positive else None})
    return {"status": "exploratory", **counts(frame), "holdout_prevalence": positive / len(frame),
            "average_precision": float(average_precision_score(labels, scores)) if positive else None,
            "brier_score": float(brier_score_loss(labels, probabilities)) if probabilities is not None else None,
            "brier_note": None if probabilities is not None else "Count ranking is not a probability forecast; Brier not defined",
            "capacities": capacity_metrics}


def fixed_pipeline(protocol):
    settings = {key: value for key, value in protocol["logistic"].items() if key != "regularization"}
    return Pipeline([("impute", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
                     ("scale", StandardScaler()), ("logistic", LogisticRegression(l1_ratio=0.0, **settings))])


def make_snapshot(directory, cohort, bundle, limit):
    with closing(sqlite3.connect(f"{(DATA / 'sample.sqlite3').as_uri()}?mode=ro", uri=True)) as source:
        latest = pd.read_sql_query("SELECT min(t.test_id) AS test_id FROM tests t JOIN (SELECT vehicle_id,max(test_date) AS last_date FROM tests GROUP BY vehicle_id) m ON t.vehicle_id=m.vehicle_id AND t.test_date=m.last_date GROUP BY t.vehicle_id HAVING count(*)=1", source)
    queue = cohort[cohort.test_id.isin(latest.test_id)].copy()
    queue["selection_key"] = queue.test_id.map(tie_key)
    queue = queue.sort_values("selection_key").head(limit)
    path = directory / "snapshot.sqlite3"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        connection.execute("CREATE TABLE followup_queue(case_id TEXT PRIMARY KEY,index_date TEXT NOT NULL,inputs_json TEXT NOT NULL,prediction_json TEXT NOT NULL)")
        connection.execute("CREATE TABLE descriptive_history(case_id TEXT PRIMARY KEY REFERENCES followup_queue(case_id),history_json TEXT NOT NULL)")
        metadata = {"model_version": bundle["version"], "data_version": bundle["data_version"],
                    "as_of": "2024-12-31", "status": "historical demonstration, not live queue",
                    "recurrence": "Descriptive only, not a model input; no prior record is not confirmed absence",
                    "history_starts": "2022-01-01", "evaluation_outcomes": "Not included in this database"}
        connection.executemany("INSERT INTO metadata VALUES(?,?)", metadata.items())
        for row in queue.to_dict("records"):
            case_id = hashlib.sha256(f"btp-case-v1:{row['test_id']}".encode()).hexdigest()[:16]
            features = {column: float(row[column]) if pd.notna(row[column]) else None for column in MODEL_FEATURES}
            payload = {"vehicle_class": 4, "component_family": "brakes", "test_type": "NT", "test_result": "P", "features": features}
            prediction = predict_case(bundle, payload)
            history = {column: int(row[column]) for column in ["prior_recorded_tests", "prior_brake_advisory_tests", "prior_brake_failure_tests", "observed_history_days"]}
            history.update(model_input=False, predictive_value="unvalidated", prior_absence_confirmed=False,
                           limitation="Left-truncated recorded family history, not evidence of ignored repairs or same-part failure")
            connection.execute("INSERT INTO followup_queue VALUES(?,?,?,?)", (case_id, row["index_date"], json.dumps(payload), json.dumps(prediction)))
            connection.execute("INSERT INTO descriptive_history VALUES(?,?)", (case_id, json.dumps(history)))
        connection.commit()
        if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Serving snapshot integrity failure")
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("History join failure")
    if len(queue) == 0 or len(queue) > limit or path.stat().st_size > 10 * 1024 ** 2:
        raise ValueError("Snapshot outside bounded size")
    path.chmod(stat.S_IREAD)
    with closing(open_snapshot(path)) as connection:
        try:
            connection.execute("DELETE FROM metadata")
        except sqlite3.OperationalError:
            pass
        else:
            raise ValueError("Snapshot unexpectedly writable")
    return {"rows": len(queue), "bytes": path.stat().st_size, "row_limit": limit, "read_only_write_test": "passed"}


def run():
    capacity_gate()
    cohort, protocol = load_cohort()
    if not AUDIT.exists() or RELEASE.exists():
        raise ValueError("Require pinned audit and a new versioned release directory")
    audit = json.loads(AUDIT.read_text())
    if audit["protocol_sha256"] != checksum(PROTOCOL):
        raise ValueError("Protocol changed after audit; stop")
    train, test = partitions(cohort, protocol)
    train_features = clean_features(train[MODEL_FEATURES])
    test_features = clean_features(test[MODEL_FEATURES])
    if train_features[["vehicle_age_years", "mileage"]].isna().all(axis=1).any() or test_features[["vehicle_age_years", "mileage"]].isna().all(axis=1).any():
        raise ValueError("Both age/mileage missing; explicit eligibility review required before fitting")
    model = fixed_pipeline(protocol)
    with warnings.catch_warnings(), threadpool_limits(limits=1):
        warnings.simplefilter("error", ConvergenceWarning)
        model.fit(train_features, train.label.to_numpy(dtype=int))
    probability = model.predict_proba(test_features)[:, 1]
    prevalence = float(train.label.mean())
    constant = np.full(len(test), prevalence)
    ranking = test_features.brake_advisory_count.to_numpy()
    comparisons = {}
    for name, scores, probabilities in [("training_prevalence", constant, constant),
                                         ("brakes_advisory_count", ranking, None), ("logistic", probability, probability)]:
        comparisons[name] = evaluate(test, scores, probabilities, protocol["capacities"])
    unseen_mask = ~test.vehicle_id.isin(train.vehicle_id).to_numpy()
    secondary = {name: evaluate(test.loc[unseen_mask], scores[unseen_mask], None if probabilities is None else probabilities[unseen_mask], protocol["capacities"])
                 for name, scores, probabilities in [("training_prevalence", constant, constant),
                                                      ("brakes_advisory_count", ranking, None), ("logistic", probability, probability)]}
    metrics = {"version": VERSION, "generated_at": now(), "status": "exploratory, not production validation",
               "training": counts(train), "training_prevalence": prevalence, "primary_temporal": comparisons,
               "secondary_unseen_vehicle_evaluation": secondary, "secondary_overlaps_primary": True,
               "primary_seen_vehicle_count": int(test.vehicle_id.isin(train.vehicle_id).sum()),
               "logistic_minus_constant_brier": comparisons["logistic"]["brier_score"] - comparisons["training_prevalence"]["brier_score"],
               "calibration_established": False, "recurrence_prediction_validated": False,
               "hyperparameter_search": False, "holdout_tuning_or_selection": False,
               "intervals": "Not calculated; no bootstrap or ungrouped uncertainty claims",
               "availability": protocol["availability"]}
    RELEASE.mkdir(parents=True)
    bundle = {"version": VERSION, "data_version": "dvsa-2022-2024-splitmix1000-v1", "pipeline": model,
              "features": MODEL_FEATURES, "training_prevalence": prevalence,
              "training_ranges": {column: [float(train_features[column].min()), float(train_features[column].max())] for column in MODEL_FEATURES},
              "recurrence_used": False, "freeze": protocol["freeze"]}
    joblib.dump(bundle, RELEASE / "bundle.joblib", compress=3, protocol=5)
    save_json(RELEASE / "metrics.json", metrics)
    save_json(RELEASE / "feature-schema.json", {"version": VERSION, "features": MODEL_FEATURES,
              "feature_origins": "current inspection only", "optional": ["vehicle_age_years", "mileage"],
              "required": ["brake_advisory_count", "advisory_count"], "recurrence": "excluded from model",
              "missingness": protocol["preprocessing"], "unsupported_scope": "Any non-class4/non-brakes/non-NT/non-P request"})
    shutil.copyfile(PROTOCOL, RELEASE / "protocol.json")
    shutil.copyfile(AUDIT, RELEASE / "split-audit.json")
    prediction_audit = test[["test_id", "vehicle_id", "index_date", "label", "label_available_at"]].copy()
    prediction_audit["logistic_probability_for_evaluation_only"] = probability
    prediction_audit.to_parquet(EVALUATION / "historical-evaluation.parquet", index=False)
    snapshot = make_snapshot(RELEASE, cohort, bundle, protocol["snapshot_limit"])
    card = f"""# Exploratory model card: {VERSION}

Class-4 NT/P inspections with recorded brakes advisories; recorded same-family F or rectified-P at immediate next NT in 9–15 calendar months. Conditional on usable observed follow-up, not mechanical failure/survival risk or proof of unrepaired advisories.

Training: {len(train)} examples/vehicles, {int(train.label.sum())} positives; evaluation {len(test)} examples/vehicles, {int(test.label.sum())} positives. Train 2022-Q1, freeze 2023-07-01 UTC, test 2023-Q3; outcomes observed through 2024-12-31. Retrospective event-time only, not contemporaneous public-release availability. Actual primary evaluation vehicles are all unseen; the secondary analysis is identical, not independent corroboration.

Four current-inspection predictors: age, mileage, brakes advisory count, total advisory count. Training-only median imputation/missing indicators and standardization, fixed C=1 L2 logistic lbfgs, max_iter=1000, no class weighting/search. No mature independent development partition; no threshold tuning, calibration or production-winner selection. Baselines: training prevalence and advisory-count ranking; full metrics/raw counts in metrics.json. Brier ranking baseline is undefined, not invented.

Recurrence is descriptive only and its predictive value remains UNVALIDATED. Training history is left-truncated at 2022; absent prior records do not confirm no earlier advisories. No identifier, postcode, recurrence, mileage change or outcome feature enters the model. Serving explanations are signed logit contributions relative to centered training inputs, not causal statements. Score 0–100 is exploratory prioritization, not calibrated failure percentage or safety category.

Limited positive count, one quarter, seasonal shift, observed-follow-up selection, nine F/one PRS missing source items, excluded ambiguous/attribute-conflicting records, unresolved first-use/revision semantics, and no prospective validation limit conclusions. All baselines and the fixed model are reported without a production winner. No confidence intervals are claimed.

Serving snapshot: {snapshot['rows']} historical demonstration cases as of 2024-12-31, read-only, no outcome fields. Selected using latest uniquely dated inspection and a fixed outcome-independent hash, not observed labels. Evaluation row-level outcomes live separately under artifacts/evaluations, not in the queue. Recurrence has a distinct descriptive table. Inputs may be insufficient or unsupported; see API_CONTRACT.md.

Trusted local joblib only: pickle-based loading can execute code; verify an externally trusted release-manifest SHA256 and every artifact checksum before loading. Pin identical dependency versions. A checksum is integrity, not a signature/authenticity guarantee. No uploaded model loading.
"""
    (RELEASE / "model-card.md").write_text(card, encoding="utf-8")
    files = {path.name: {"bytes": path.stat().st_size, "sha256": checksum(path)} for path in RELEASE.iterdir() if path.is_file()}
    manifest = {"version": VERSION, "data_version": bundle["data_version"], "created_at": now(),
                "python_minor": f"{sys.version_info.major}.{sys.version_info.minor}",
                "dependencies": {package: importlib.metadata.version(package) for package in PACKAGES},
                "files": files, "snapshot": snapshot, "cohort_sha256": protocol["cohort_sha256"],
                "protocol_sha256": checksum(PROTOCOL), "code_sha256": {name: checksum(ROOT / f"pipeline/{name}.py") for name in ["evaluation", "modeling", "serving"]}}
    save_json(RELEASE / "release-manifest.json", manifest)
    expected = checksum(RELEASE / "release-manifest.json")
    loaded, _ = load_release(RELEASE, expected)
    np.testing.assert_allclose(loaded["pipeline"].predict_proba(test_features)[:, 1], probability, rtol=0, atol=0)
    save_json(EVALUATION / "run-checks.json", {"completed_at": now(), "release_manifest_sha256": expected,
              "round_trip_predictions": "identical", "snapshot": snapshot, "resources": resource_snapshot(),
              "preprocessor_training_rows": int(model["scale"].n_samples_seen_), "training_only_imputer_medians": model["impute"].statistics_.tolist()})
    print(json.dumps({"release": str(RELEASE), "release_manifest_sha256": expected, "metrics": metrics, "snapshot": snapshot}))


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    scratch = ROOT / "data/tmp"
    os.environ.update(TEMP=str(scratch), TMP=str(scratch), SQLITE_TMPDIR=str(scratch))
    run()
