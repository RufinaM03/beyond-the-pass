"""One bounded, model-free split audit using preserved processed artifacts only."""

import argparse
import json
import sqlite3
from contextlib import closing

from pipeline.pilot import capacity_gate
from pipeline.sources import ROOT, checksum, now, save_json
import pandas as pd


DATA = ROOT / "data/processed/expanded2022-2024"
PROTOCOL = ROOT / "docs/phase3_protocol.json"
AUDIT = ROOT / "artifacts/evaluations/btp-exploratory-v1/split-audit.json"


def load_cohort():
    capacity_gate()
    protocol = json.loads(PROTOCOL.read_text())
    path = DATA / "brakes-cohort.parquet"
    if checksum(path) != protocol["cohort_sha256"]:
        raise ValueError("Preserved cohort checksum differs; stop before modelling")
    manifest = json.loads((DATA / "feature-manifest.json").read_text())
    for filename, record in manifest["files"].items():
        if checksum(DATA / filename) != record["sha256"]:
            raise ValueError("Preserved feature/audit artifacts differ")
    frame = pd.read_parquet(path)
    if frame.test_id.duplicated().any() or frame.label.notna().sum() != 6642:
        raise ValueError("Preserved label identity/count differs")
    if (frame.feature_history_end > frame.index_date).any():
        raise ValueError("Future feature information")
    return frame, protocol


def partitions(frame, protocol):
    labelled = frame[frame.label.notna()].copy()
    train = labelled[labelled.index_date.between(*protocol["training_indices"])].copy()
    available = pd.to_datetime(train.label_available_at, utc=True)
    if not (available < pd.Timestamp(protocol["freeze"])).all():
        raise ValueError("Unavailable training labels; do not silently drop")
    test = labelled[labelled.index_date.between(*protocol["evaluation_indices"])].copy()
    if not (pd.to_datetime(test.prediction_available_at, utc=True) >= pd.Timestamp(protocol["freeze"])).all():
        raise ValueError("Evaluation prediction before freeze")
    for subset in [train, test]:
        if subset.vehicle_id.duplicated().any():
            raise ValueError("Expected one annual example per vehicle inside each quarter")
    return train, test


def counts(frame):
    return {"examples": len(frame), "vehicles": int(frame.vehicle_id.nunique()),
            "positive": int((frame.label == 1).sum()), "negative": int((frame.label == 0).sum())}


def audit():
    if AUDIT.exists():
        raise ValueError("Audit already pinned; reuse it, do not repeatedly redesign the split")
    frame, protocol = load_cohort()
    labelled = frame[frame.label.notna()].copy()
    reasons = []
    for row in labelled.itertuples():
        if row.partition == "train":
            reason = "selected_reference_training"
        elif row.partition == "holdout":
            reason = "selected_reference_holdout"
        elif row.partition_window == "outside_windows":
            reason = "outside_reference_index_windows"
        elif row.partition_window == "train" and row.vehicle_role == "holdout":
            reason = "reference_training_window_reserved_holdout_role"
        elif row.partition_window == "holdout" and row.vehicle_role == "train":
            reason = "reference_holdout_window_reserved_training_role"
        else:
            raise ValueError("Unaccounted labelled example")
        reasons.append(reason)
    labelled["reference_disposition"] = reasons
    reason_counts = labelled.reference_disposition.value_counts().to_dict()
    if sum(reason_counts.values()) != 6642:
        raise ValueError("Label accounting failed")
    windows = []
    for candidate in protocol["candidate_freezes"]:
        freeze = pd.Timestamp(candidate, tz="UTC")
        mature_train_end = (freeze - pd.DateOffset(months=15) - pd.DateOffset(days=1)).date().isoformat()
        train = labelled[labelled.index_date.between("2022-01-01", mature_train_end)]
        if not (pd.to_datetime(train.label_available_at, utc=True) < freeze).all():
            raise ValueError("Candidate maturity proxy inconsistent")
        test = labelled[labelled.index_date.between(candidate, "2023-09-30")]
        windows.append({"freeze": candidate, "mature_training_index_end": mature_train_end,
                        "training": counts(train), "fully_mature_evaluation": counts(test)})
    train, test = partitions(frame, protocol)
    history = {}
    for name, subset in [("training", train), ("evaluation", test)]:
        history[name] = {"any_prior_record": int((subset.prior_recorded_tests > 0).sum()),
                         "recorded_recurrence": int((subset.prior_brake_advisory_tests > 0).sum()),
                         "history_365_days": int((subset.observed_history_days >= 365).sum()),
                         "median_history_days": float(subset.observed_history_days.median()),
                         "missing_mileage_delta": int(subset.mileage_delta.isna().sum())}
    with closing(sqlite3.connect(f"{(DATA / 'sample.sqlite3').as_uri()}?mode=ro", uri=True)) as connection:
        for row in labelled.itertuples():
            following = connection.execute("SELECT test_id FROM tests WHERE vehicle_id=? AND test_type='NT' AND (test_date>? OR (test_date=? AND test_id>?)) ORDER BY test_date,test_id LIMIT 1",
                                           (row.vehicle_id, row.index_date, row.index_date, row.test_id)).fetchone()
            if following is None or following[0] != row.next_test_id:
                raise ValueError("Invalid immediate-next-test label")
            date = pd.Timestamp(row.index_date)
            if not date + pd.DateOffset(months=9) <= pd.Timestamp(row.next_test_date) <= date + pd.DateOffset(months=15):
                raise ValueError("Invalid annual label window")
    unseen = test[~test.vehicle_id.isin(train.vehicle_id)]
    report = {"generated_at": now(), "cohort_sha256": protocol["cohort_sha256"],
              "protocol_sha256": checksum(PROTOCOL), "labelled_accounted": len(labelled),
              "reference_dispositions": reason_counts, "candidate_windows": windows,
              "primary_training": counts(train), "primary_evaluation": counts(test),
              "secondary_unseen_vehicles": counts(unseen),
              "overlapping_vehicle_ids": len(set(train.vehicle_id) & set(test.vehicle_id)),
              "history": history, "one_index_per_vehicle": True,
              "one_index_reason": "A second NT inside a quarter would be the first anchor's immediate next NT, below nine months; both cannot be labelled annual examples",
              "label_checks": "All 6642 preserved labelled examples pass next-NT/calendar checks; hashes and feature-time guards pass",
              "availability": protocol["availability"]}
    save_json(AUDIT, report)
    labelled[["test_id", "reference_disposition"]].to_parquet(AUDIT.parent / "reference-accounting.parquet", index=False)
    print(json.dumps(report))


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    audit()
