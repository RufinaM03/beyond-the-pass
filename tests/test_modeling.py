"""Synthetic modelling/serving fixtures only; never used for evaluation claims."""

import json
import math
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from pipeline import modeling, serving
from pipeline.evaluation import partitions
from pipeline.sources import ROOT, checksum, save_json


def synthetic_bundle():
    train = pd.DataFrame([[5, 10000, 1, 2], [10, 20000, 2, 3], [15, None, 3, 3], [20, 40000, 4, 5]], columns=serving.MODEL_FEATURES)
    protocol = {"logistic": {"C": 1.0, "solver": "lbfgs", "max_iter": 1000, "tol": 0.0001,
                              "class_weight": None, "random_state": 2026}}
    pipeline = modeling.fixed_pipeline(protocol)
    pipeline.fit(serving.clean_features(train), [0, 0, 1, 1])
    return {"version": "synthetic", "data_version": "synthetic", "pipeline": pipeline,
            "training_ranges": {column: [float(train[column].min()), float(train[column].max())] for column in train},
            "features": serving.MODEL_FEATURES}


def payload():
    return {"vehicle_class": 4, "component_family": "brakes", "test_type": "NT", "test_result": "P",
            "features": dict(zip(serving.MODEL_FEATURES, [10, 20000, 2, 3]))}


class ExploratoryTests(unittest.TestCase):
    def test_temporal_guards_refuse_future_training_outcomes(self):
        frame = pd.DataFrame({"vehicle_id": [1, 2], "label": [0, 1],
                              "index_date": ["2022-02-01", "2023-08-01"],
                              "label_available_at": ["2023-07-01T00:00:00Z", "2024-08-01T00:00:00Z"],
                              "prediction_available_at": ["2022-02-01T23:59:59Z", "2023-08-01T23:59:59Z"]})
        protocol = {"training_indices": ["2022-01-01", "2022-03-31"],
                    "evaluation_indices": ["2023-07-01", "2023-09-30"], "freeze": "2023-07-01T00:00:00Z"}
        with self.assertRaisesRegex(ValueError, "Unavailable training"):
            partitions(frame, protocol)
        frame.loc[0, "label_available_at"] = "2023-02-01T00:00:00Z"
        frame.loc[1, "prediction_available_at"] = "2023-06-30T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "before freeze"):
            partitions(frame, protocol)

    def test_fixed_capacities_tie_breaks_and_raw_counts(self):
        frame = pd.DataFrame({"test_id": [4, 2, 1, 3, 5], "vehicle_id": [10, 20, 30, 40, 50], "label": [1, 0, 1, 0, 0]})
        metrics = modeling.evaluate(frame, np.ones(5), np.full(5, 0.4), [0.1, 0.2, 0.3])
        shuffled = modeling.evaluate(frame.iloc[::-1], np.ones(5), np.full(5, 0.4), [0.1, 0.2, 0.3])
        self.assertEqual(metrics, shuffled)
        self.assertEqual([row["selected"] for row in metrics["capacities"]], [1, 1, 2])
        self.assertAlmostEqual(metrics["average_precision"], 0.4)
        self.assertAlmostEqual(metrics["brier_score"], 0.24)
        for row in metrics["capacities"]:
            self.assertEqual(row["precision"], row["true_positives"] / row["selected"])
            self.assertEqual(row["recall"], row["true_positives"] / 2)

    def test_count_rank_is_not_fabricated_probability(self):
        frame = pd.DataFrame({"test_id": [1, 2], "vehicle_id": [1, 2], "label": [0, 1]})
        result = modeling.evaluate(frame, [1, 3], None, [0.1])
        self.assertIsNone(result["brier_score"])
        self.assertEqual(result["average_precision"], 1.0)
        frame.label = 0
        empty_positive = modeling.evaluate(frame, [1, 3], None, [0.1])
        self.assertIsNone(empty_positive["average_precision"])
        self.assertIsNone(empty_positive["capacities"][0]["recall"])

    def test_preprocessor_fits_training_only(self):
        bundle = synthetic_bundle()
        imputer = bundle["pipeline"]["impute"]
        np.testing.assert_allclose(imputer.statistics_, [12.5, 20000, 2.5, 3])
        before = imputer.statistics_.copy()
        bundle["pipeline"].predict_proba(pd.DataFrame([[100, 9999999, 5, 6]], columns=serving.MODEL_FEATURES))
        np.testing.assert_array_equal(imputer.statistics_, before)
        self.assertEqual(bundle["pipeline"]["scale"].n_samples_seen_, 4)

    def test_schema_invalid_values_and_scope_states(self):
        bundle = synthetic_bundle()
        request = payload()
        request["features"]["vehicle_age_years"] = -1
        request["features"]["mileage"] = 0
        self.assertEqual(serving.predict_case(bundle, request)["status"], "insufficient_data")
        for field, value in [("vehicle_class", 5), ("component_family", "tyres"), ("test_type", "RT"), ("test_result", "PRS")]:
            request = payload(); request[field] = value
            self.assertEqual(serving.predict_case(bundle, request)["status"], "unsupported_scope")
        request = payload(); request["features"]["brake_advisory_count"] = 1.5
        self.assertEqual(serving.predict_case(bundle, request)["status"], "invalid_input")
        request = payload(); request["features"]["mileage"] = True
        self.assertEqual(serving.predict_case(bundle, request)["status"], "invalid_input")
        request = payload(); del request["features"]["advisory_count"]
        self.assertEqual(serving.predict_case(bundle, request)["status"], "insufficient_data")

    def test_no_recurrence_identifier_or_outcome_inputs(self):
        bundle = synthetic_bundle()
        for forbidden in ["vehicle_id", "postcode_area", "label", "prior_brake_advisory_tests", "next_test_result"]:
            request = payload(); request["features"][forbidden] = 1
            self.assertEqual(serving.predict_case(bundle, request)["status"], "invalid_input")
        self.assertFalse(serving.predict_case(bundle, payload())["recurrence_used_by_model"])
        self.assertEqual(list(bundle["pipeline"].feature_names_in_), serving.MODEL_FEATURES)

    def test_exact_logit_explanation_and_imputation(self):
        bundle = synthetic_bundle(); request = payload()
        request["features"]["mileage"] = None
        result = serving.predict_case(bundle, request)
        self.assertEqual(result["imputed_features"], ["mileage"])
        explanation = result["explanation"]
        logit = explanation["intercept_log_odds"] + sum(term["log_odds_contribution"] for term in explanation["terms"])
        self.assertAlmostEqual(100 / (1 + math.exp(-logit)), result["exploratory_prioritization_score"])

    def test_snapshot_read_only_and_no_evaluation_columns(self):
        scratch = ROOT / "data/tmp"; scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            path = Path(temporary) / "synthetic.sqlite3"
            with closing(sqlite3.connect(path)) as connection:
                connection.execute("CREATE TABLE followup_queue(case_id TEXT,inputs_json TEXT)")
            with closing(serving.open_snapshot(path)) as connection:
                with self.assertRaises(sqlite3.OperationalError):
                    connection.execute("INSERT INTO followup_queue VALUES('synthetic','{}')")

    def test_checksum_failure_never_deserializes(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "data/tmp") as temporary:
            directory = Path(temporary)
            save_json(directory / "release-manifest.json", {"files": {}})
            with patch.object(serving.joblib, "load") as unpickle:
                with self.assertRaisesRegex(ValueError, "external checksum"):
                    serving.load_release(directory, "0" * 64)
                with self.assertRaisesRegex(ValueError, "Incomplete"):
                    serving.load_release(directory, checksum(directory / "release-manifest.json"))
                unpickle.assert_not_called()

    def test_modified_bundle_is_rejected_before_deserialization(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "data/tmp") as temporary:
            directory = Path(temporary)
            files = {}
            for filename in ["bundle.joblib", "metrics.json", "feature-schema.json", "protocol.json", "split-audit.json", "snapshot.sqlite3", "model-card.md"]:
                path = directory / filename; path.write_bytes(b"synthetic")
                files[filename] = {"bytes": path.stat().st_size, "sha256": checksum(path)}
            save_json(directory / "release-manifest.json", {"files": files})
            expected = checksum(directory / "release-manifest.json")
            (directory / "bundle.joblib").write_bytes(b"corrupted")
            with patch.object(serving.joblib, "load") as unpickle:
                with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                    serving.load_release(directory, expected)
                unpickle.assert_not_called()


if __name__ == "__main__":
    unittest.main()
