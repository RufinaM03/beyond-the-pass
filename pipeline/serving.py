"""Trusted local artifact loading, index-only scores and read-only snapshot access."""

import importlib.metadata
import json
import numbers
import sqlite3
import sys
from pathlib import Path

from pipeline.pilot import capacity_gate
from pipeline.sources import checksum
import joblib
import numpy as np
import pandas as pd


MODEL_FEATURES = ["vehicle_age_years", "mileage", "brake_advisory_count", "advisory_count"]


def clean_features(frame):
    if list(frame.columns) != MODEL_FEATURES:
        raise ValueError("Exact current-inspection feature allowlist required")
    result = frame.astype(float).copy()
    result = result.replace([np.inf, -np.inf], np.nan)
    result.loc[result.vehicle_age_years < 0, "vehicle_age_years"] = np.nan
    result.loc[result.mileage <= 0, "mileage"] = np.nan
    for column in ["brake_advisory_count", "advisory_count"]:
        if (result[column].isna() | (result[column] < 1) | (result[column] % 1 != 0)).any():
            raise ValueError("Advisory counts must be known positive integers")
    if (result.advisory_count < result.brake_advisory_count).any():
        raise ValueError("Total advisory count cannot be smaller than brakes count")
    return result


def load_release(directory, expected_manifest_sha256):
    capacity_gate()
    directory = Path(directory).resolve()
    path = directory / "release-manifest.json"
    if checksum(path) != expected_manifest_sha256:
        raise ValueError("Release manifest differs from trusted external checksum")
    manifest = json.loads(path.read_text())
    required = {"bundle.joblib", "metrics.json", "feature-schema.json", "protocol.json", "split-audit.json", "snapshot.sqlite3", "model-card.md"}
    if set(manifest["files"]) != required:
        raise ValueError("Incomplete or unsupported release file manifest")
    for filename, record in manifest["files"].items():
        target = (directory / filename).resolve()
        if record["bytes"] > (10 * 1024 ** 2 if filename == "snapshot.sqlite3" else 1024 ** 2):
            raise ValueError("Release file exceeds bounded size")
        if target.parent != directory or target.stat().st_size != record["bytes"] or checksum(target) != record["sha256"]:
            raise ValueError("Release file identity/checksum mismatch")
    if manifest["python_minor"] != f"{sys.version_info.major}.{sys.version_info.minor}":
        raise ValueError("Python runtime version mismatch")
    for package, version in manifest["dependencies"].items():
        if importlib.metadata.version(package) != version:
            raise ValueError(f"Dependency version mismatch: {package}")
    bundle = joblib.load(directory / "bundle.joblib")
    if bundle["features"] != MODEL_FEATURES or bundle["version"] != manifest["version"]:
        raise ValueError("Unsupported bundle feature/version contract")
    if list(bundle["pipeline"].feature_names_in_) != MODEL_FEATURES:
        raise ValueError("Pipeline input features differ")
    return bundle, manifest


def open_snapshot(path):
    path = Path(path).resolve()
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro&immutable=1", uri=True)
    connection.execute("PRAGMA query_only=ON")
    return connection


def predict_case(bundle, payload):
    base = {"model_version": bundle["version"], "data_version": bundle["data_version"],
            "status": None, "exploratory_prioritization_score": None,
            "recurrence_used_by_model": False, "probability_reliability": "unestablished"}
    allowed = {"vehicle_class", "component_family", "test_type", "test_result", "features"}
    if not isinstance(payload, dict) or set(payload) - allowed:
        return base | {"status": "invalid_input", "reasons": ["Unsupported request fields"]}
    if any(payload.get(key) != value for key, value in {
        "vehicle_class": 4, "component_family": "brakes", "test_type": "NT", "test_result": "P"}.items()):
        return base | {"status": "unsupported_scope", "reasons": ["Requires class 4 NT/P with brakes advisory"]}
    features = payload.get("features")
    if not isinstance(features, dict) or set(features) - set(MODEL_FEATURES):
        return base | {"status": "invalid_input", "reasons": ["Only declared current-inspection predictors accepted"]}
    if any(value is not None and (isinstance(value, bool) or not isinstance(value, numbers.Real)) for value in features.values()):
        return base | {"status": "invalid_input", "reasons": ["Features must be JSON numbers or null"]}
    if any(features.get(column) is None for column in ["brake_advisory_count", "advisory_count"]):
        return base | {"status": "insufficient_data", "reasons": ["Advisory counts required"]}
    try:
        frame = clean_features(pd.DataFrame([{key: features.get(key) for key in MODEL_FEATURES}]))
    except (ValueError, OverflowError):
        return base | {"status": "invalid_input", "reasons": ["Invalid or inconsistent advisory counts"]}
    if frame[["vehicle_age_years", "mileage"]].isna().all(axis=1).iloc[0]:
        return base | {"status": "insufficient_data", "reasons": ["At least age or mileage must be usable"]}
    pipeline = bundle["pipeline"]
    transformed = pipeline[:-1].transform(frame)
    coefficients = pipeline[-1].coef_[0]
    names = pipeline["impute"].get_feature_names_out(MODEL_FEATURES)
    terms = [{"feature": str(name), "log_odds_contribution": float(value * coefficient),
              "interpretation": "association relative to training-centered transformed input, not causation"}
             for name, value, coefficient in zip(names, transformed[0], coefficients)]
    imputed = [column for column in MODEL_FEATURES if pd.isna(frame.iloc[0][column])]
    outside = [column for column in MODEL_FEATURES if pd.notna(frame.iloc[0][column])
               and not bundle["training_ranges"][column][0] <= float(frame.iloc[0][column]) <= bundle["training_ranges"][column][1]]
    score = float(pipeline.predict_proba(frame)[0, 1]) * 100
    return base | {"status": "scored", "exploratory_prioritization_score": score,
                   "imputed_features": imputed, "outside_training_range": outside,
                   "explanation": {"intercept_log_odds": float(pipeline[-1].intercept_[0]), "terms": terms,
                                   "recurrence": "Descriptive history only; its predictive value is unvalidated"},
                   "warning": "Not a calibrated failure probability, safety classification or inspection substitute"}
