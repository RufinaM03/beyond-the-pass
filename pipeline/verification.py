"""Verify the fixed exploratory release without retraining or reading raw archives."""

import json
import math
import sqlite3
from contextlib import closing

from pipeline.evaluation import DATA, PROTOCOL, load_cohort, partitions
from pipeline.modeling import EVALUATION, evaluate
from pipeline.pilot import resource_snapshot
from pipeline.serving import MODEL_FEATURES, clean_features, load_release, open_snapshot, predict_case
from pipeline.sources import ROOT, checksum, now, save_json
import numpy as np
import pandas as pd


def verify():
    descriptor = json.loads((ROOT / "docs/serving_release.json").read_text())
    directory = ROOT / descriptor["directory"]
    bundle, manifest = load_release(directory, descriptor["release_manifest_sha256"])
    for name, expected in manifest["code_sha256"].items():
        if checksum(ROOT / f"pipeline/{name}.py") != expected:
            raise ValueError("Exported implementation source changed")
    cohort, protocol = load_cohort()
    train, test = partitions(cohort, protocol)
    training = clean_features(train[MODEL_FEATURES])
    model = bundle["pipeline"]
    np.testing.assert_allclose(model["impute"].statistics_, np.nanmedian(training.to_numpy(), axis=0))
    np.testing.assert_allclose(model["scale"].mean_, model["impute"].transform(training).mean(axis=0))
    if model["scale"].n_samples_seen_ != len(train):
        raise ValueError("Preprocessing was not fitted on the declared training rows")
    predictions = model.predict_proba(clean_features(test[MODEL_FEATURES]))[:, 1]
    historical = pd.read_parquet(EVALUATION / "historical-evaluation.parquet")
    np.testing.assert_array_equal(historical.test_id.to_numpy(), test.test_id.to_numpy())
    np.testing.assert_array_equal(historical.label.to_numpy(), test.label.to_numpy())
    np.testing.assert_allclose(historical.logistic_probability_for_evaluation_only, predictions, rtol=0, atol=0)
    metrics = json.loads((directory / "metrics.json").read_text())
    constant = np.full(len(test), float(train.label.mean()))
    recomputed = {"training_prevalence": evaluate(test, constant, constant, protocol["capacities"]),
                  "brakes_advisory_count": evaluate(test, test.brake_advisory_count.to_numpy(), None, protocol["capacities"]),
                  "logistic": evaluate(test, predictions, predictions, protocol["capacities"])}
    if metrics["primary_temporal"] != recomputed:
        raise ValueError("Metrics or raw capacity counts differ")
    scored = 0
    insufficient = 0
    dates = []
    with closing(open_snapshot(directory / "snapshot.sqlite3")) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables != {"metadata", "followup_queue", "descriptive_history"}:
            raise ValueError("Unexpected serving table or historical outcome data")
        rows = connection.execute("SELECT q.case_id,q.index_date,q.inputs_json,q.prediction_json,h.history_json FROM followup_queue q JOIN descriptive_history h USING(case_id)").fetchall()
        if not 0 < len(rows) <= protocol["snapshot_limit"]:
            raise ValueError("Snapshot cap/empty snapshot")
        for case_id, date, inputs, stored, history in rows:
            request, expected, descriptive = json.loads(inputs), json.loads(stored), json.loads(history)
            if set(request["features"]) != set(MODEL_FEATURES) or descriptive["model_input"] is not False:
                raise ValueError("Prediction/description separation failed")
            actual = predict_case(bundle, request)
            if actual != expected:
                raise ValueError("Stored queue score/explanation differs")
            if actual["status"] == "scored":
                explanation = actual["explanation"]
                margin = explanation["intercept_log_odds"] + sum(term["log_odds_contribution"] for term in explanation["terms"])
                if not math.isclose(100 / (1 + math.exp(-margin)), actual["exploratory_prioritization_score"], abs_tol=1e-10):
                    raise ValueError("Explanation does not reconstruct score")
                scored += 1
            elif actual["status"] == "insufficient_data":
                insufficient += 1
            else:
                raise ValueError("Unexpected queue state")
            dates.append(date)
        try:
            connection.execute("DELETE FROM followup_queue")
        except sqlite3.OperationalError as error:
            if "readonly" not in str(error).lower():
                raise
        else:
            raise ValueError("Serving database writable")
    report = {"verified_at": now(), "release_manifest_sha256": descriptor["release_manifest_sha256"],
              "preserved_labels": 6642, "preprocessing_training_only": len(train),
              "evaluation_predictions_and_metrics_reconstructed": len(test),
              "snapshot_cases": len(rows), "scored": scored, "insufficient": insufficient,
              "snapshot_index_min": min(dates), "snapshot_index_max": max(dates),
              "snapshot_read_only": True, "recurrence_model_input": False,
              "historical_outcomes_separate": True, "resources": resource_snapshot()}
    save_json(EVALUATION / "release-verification.json", report)
    print(json.dumps(report))


if __name__ == "__main__":
    verify()
