"""Model-free class-4 annual brakes labels, index-only features and audit partitions."""

import argparse
import json
import os
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import datetime, timedelta, timezone

from pipeline.pilot import ITEM_COLUMNS, capacity_gate, resource_snapshot, vehicle_hash
from pipeline.sources import MANIFEST, ROOT, checksum, now, save_json
import numpy as np
import pandas as pd
import pyarrow.parquet as pq


FEATURES = ["vehicle_age_years", "mileage", "mileage_delta", "mileage_delta_days",
            "annualized_mileage_delta", "mileage_rollback", "advisory_count", "brake_advisory_count",
            "prior_recorded_tests", "prior_normal_tests", "prior_brake_advisory_tests",
            "prior_brake_failure_tests", "brake_advisory_recurrence", "days_since_prior_brake_advisory",
            "observed_history_days", "prior_mileage_available", "prior_unknown_mapping_tests"]
FREEZE = pd.Timestamp("2023-07-01", tz="UTC")


def dictionary_mapping():
    manifest = json.loads(MANIFEST.read_text())
    frames = []
    for filename in ["dft_item_detail_extract.csv", "dft_item_group_extract.csv"]:
        record = next(record for record in manifest["sources"] if record["filename"] == filename)
        path = ROOT / record["path"]
        if checksum(path) != record["sha256"]:
            raise ValueError("Current dictionary checksum differs")
        frames.append(pd.read_csv(path, dtype=str, keep_default_na=False))
    details, groups = frames
    if details.duplicated(["rfr_id", "test_class_id"]).any() or groups.duplicated(["test_item_id", "test_class_id"]).any():
        raise ValueError("Conflicting dictionary keys")
    hierarchy = {(row.test_item_id, row.test_class_id): row for row in groups.itertuples()}
    mapped = []
    for row in details.itertuples():
        current = row.test_item_id
        seen = set()
        names = []
        while current != "0":
            if current in seen or (current, row.test_class_id) not in hierarchy:
                raise ValueError("Invalid current dictionary hierarchy")
            seen.add(current)
            group = hierarchy[(current, row.test_class_id)]
            names.append(group.item_name.strip().casefold())
            current = group.parent_id
        brakes = any(name in ["brakes", "motorcycle brakes"] for name in names)
        tyres = "tyres" in names
        if brakes and tyres:
            raise ValueError("Conflicting component ancestry")
        mapped.append({"rfr_id": row.rfr_id, "test_class_id": row.test_class_id,
                       "family": "brakes" if brakes else "tyres" if tyres else "other"})
    return pd.DataFrame(mapped)


def availability(test, rows, extra_completed=None):
    timestamps = [pd.Timestamp(datetime.fromisoformat(test["test_date"]).replace(tzinfo=timezone.utc)
                               + timedelta(days=1, microseconds=-1))]
    completed = test.get("completed_date", "")
    if completed:
        timestamps.append(pd.Timestamp(completed))
    if not rows.empty and "completed_date" in rows:
        timestamps.extend(pd.to_datetime(rows.loc[rows.completed_date != "", "completed_date"], utc=True))
    if extra_completed is not None and pd.notna(extra_completed):
        timestamps.append(extra_completed)
    return max(timestamps)


def valid_mileage(value):
    text = str(value)
    if not text.isdecimal():
        return None
    number = int(text)
    return float(number) if number > 0 else None


def feature_row(index, history, items_by_test, cutoff=None):
    date = pd.Timestamp(index["test_date"])
    prior = history[history.test_date < index["test_date"]]
    current_items = items_by_test.get(int(index["test_id"]), pd.DataFrame())
    cutoff = cutoff if cutoff is not None else availability(index, current_items)
    if "completed_date" in prior:
        known = pd.to_datetime(prior.completed_date.replace("", None), utc=True)
        prior = prior[known.isna() | (known <= cutoff)]
    current_a = current_items[current_items.rfr_type_code == "A"] if not current_items.empty else current_items
    previous_brakes_a = []
    previous_brakes_f = []
    prior_unknown = 0
    prior_normal = prior[(prior.test_type == "NT") & (prior.test_class_id == "4")]
    for test in prior_normal.to_dict("records"):
        records = items_by_test.get(int(test["test_id"]), pd.DataFrame())
        if records.empty:
            continue
        if "completed_date" in records:
            known = pd.to_datetime(records.completed_date.replace("", None), utc=True)
            records = records[known.isna() | (known <= cutoff)]
        prior_unknown += int((records.family == "unknown").any())
        brakes = records[records.family == "brakes"]
        if (brakes.rfr_type_code == "A").any():
            previous_brakes_a.append(test["test_date"])
        if brakes.rfr_type_code.isin(["F", "P"]).any():
            previous_brakes_f.append(test["test_date"])
    mileage = valid_mileage(index["test_mileage"])
    readings = []
    for prior_date, group in prior.groupby("test_date", sort=True):
        values = {value for value in group.test_mileage.map(valid_mileage) if pd.notna(value)}
        if len(values) == 1:
            readings.append((prior_date, next(iter(values))))
    previous = readings[-1] if readings else None
    delta = mileage - previous[1] if mileage is not None and previous else None
    rollback = int(delta is not None and delta < 0)
    gap = (date - pd.Timestamp(previous[0])).days if previous else None
    if rollback:
        delta = None
    age_date = pd.to_datetime(index["first_use_date"], format="%Y-%m-%d", errors="coerce")
    age = (date - age_date).days / 365.2425 if pd.notna(age_date) and age_date <= date else None
    return {"vehicle_age_years": age, "mileage": mileage, "mileage_delta": delta,
            "mileage_delta_days": gap, "annualized_mileage_delta": delta * 365.2425 / gap if delta is not None and gap else None,
            "mileage_rollback": rollback, "advisory_count": len(current_a),
            "brake_advisory_count": int((current_a.family == "brakes").sum()) if not current_a.empty else 0,
            "prior_recorded_tests": len(prior), "prior_normal_tests": len(prior_normal),
            "prior_brake_advisory_tests": len(previous_brakes_a), "prior_brake_failure_tests": len(previous_brakes_f),
            "brake_advisory_recurrence": int(bool(previous_brakes_a)),
            "days_since_prior_brake_advisory": (date - pd.Timestamp(previous_brakes_a[-1])).days if previous_brakes_a else None,
            "observed_history_days": (date - pd.Timestamp(prior.test_date.min())).days if len(prior) else 0,
            "prior_mileage_available": int(previous is not None), "prior_unknown_mapping_tests": prior_unknown}


def outcome_flags(test, rows):
    codes = set(rows.rfr_type_code) if not rows.empty else set()
    result = test["test_result"]
    return ((result == "P" and bool(codes & {"F", "P"}))
            or (result == "F" and "F" not in codes)
            or (result == "PRS" and "P" not in codes))


def construct(tests, items, coverage_end="2024-12-31"):
    if tests.test_id.duplicated().any():
        raise ValueError("Conflicting/duplicate test identifiers")
    if not items.test_id.isin(tests.test_id).all():
        raise ValueError("Ambiguous/unjoined item identifiers")
    completion_by_test = {}
    if "completed_date" in items:
        completed = pd.to_datetime(items.completed_date.replace("", None), utc=True)
        completion_by_test = completed.groupby(items.test_id).max().dropna().to_dict()
    items = items.drop_duplicates(ITEM_COLUMNS)
    by_test = {int(identifier): group for identifier, group in items.groupby("test_id", sort=False)}
    rows = []
    observation_end = pd.Timestamp(datetime.fromisoformat(coverage_end).replace(tzinfo=timezone.utc)
                                   + timedelta(days=1, microseconds=-1))
    grouped_vehicles = tests.sort_values(["vehicle_id", "test_date", "test_id"]).groupby("vehicle_id", sort=False)
    for vehicle_number, (vehicle_id, history) in enumerate(grouped_vehicles, 1):
        if vehicle_number % 500 == 0:
            capacity_gate()
        routine = history[history.test_type == "NT"]
        records = routine.to_dict("records")
        same_day = routine.test_date.value_counts()
        for position, index in enumerate(records):
            current_items = by_test.get(int(index["test_id"]), pd.DataFrame())
            if index["test_class_id"] != "4" or index["test_result"] != "P" or current_items.empty:
                continue
            if not ((current_items.family == "brakes") & (current_items.rfr_type_code == "A")).any():
                continue
            following = records[position + 1] if position + 1 < len(records) else None
            next_items = by_test.get(int(following["test_id"]), pd.DataFrame()) if following else pd.DataFrame()
            available = availability(following, next_items, completion_by_test.get(int(following["test_id"]))) if following else None
            index_date = pd.Timestamp(index["test_date"])
            earliest = index_date + pd.DateOffset(months=9)
            latest = index_date + pd.DateOffset(months=15)
            flags = []
            index_available = availability(index, current_items, completion_by_test.get(int(index["test_id"])))
            if same_day[index["test_date"]] > 1 or (following and same_day[following["test_date"]] > 1):
                flags.append("ambiguous_same_day")
            if (current_items.family == "unknown").any() or (not next_items.empty and (next_items.family == "unknown").any()):
                flags.append("unknown_mapping")
            if outcome_flags(index, current_items):
                flags.append("conflicting_index_items")
            if not following:
                flags.append("missing_followup")
                if latest > pd.Timestamp(coverage_end):
                    flags.append("administratively_immature")
            else:
                if available > observation_end:
                    flags.append("outcome_available_after_observation")
                if index_available >= pd.Timestamp(following["test_date"], tz="UTC"):
                    flags.append("index_not_available_before_followup")
                if following["test_class_id"] != "4":
                    flags.append("class_change")
                if any(index[field] != following[field] for field in ["make", "model", "first_use_date"]):
                    flags.append("conflicting_vehicle_attributes")
                if following["test_result"] not in ["P", "F", "PRS"]:
                    flags.append("incomplete_followup")
                if not earliest <= pd.Timestamp(following["test_date"]) <= latest:
                    flags.append("next_outside_9_15_months")
                if outcome_flags(following, next_items):
                    flags.append("conflicting_or_missing_failure_items")
            label = None
            if not flags:
                label = int(not next_items.empty and ((next_items.family == "brakes") & next_items.rfr_type_code.isin(["F", "P"])).any())
            feature_history = history[history.test_date <= index["test_date"]]
            feature_values = feature_row(index, feature_history, by_test, cutoff=index_available)
            partition = "outside_windows"
            if "2022-01-01" <= index["test_date"] <= "2022-03-31":
                partition = "train"
            elif "2023-07-01" <= index["test_date"] <= "2023-09-30":
                partition = "holdout"
            cohort = {"test_id": int(index["test_id"]), "vehicle_id": int(vehicle_id), "index_date": index["test_date"],
                      "next_test_id": int(following["test_id"]) if following else None,
                      "next_test_date": following["test_date"] if following else None,
                      "next_test_result": following["test_result"] if following else None,
                      "label_available_at": available.isoformat() if available is not None else None,
                      "prediction_available_at": index_available.isoformat(),
                      "label": label, "status": "labelled" if label is not None else "censored" if "missing_followup" in flags else "excluded",
                      "reason": flags[0] if flags else "labelled", "all_reasons": "|".join(flags),
                      "partition_window": partition,
                      "rectified_brake_failure": int(not next_items.empty and ((next_items.family == "brakes") & (next_items.rfr_type_code == "P")).any()),
                      "feature_history_end": index["test_date"], **feature_values}
            rows.append(cohort)
    cohort = pd.DataFrame(rows)
    if cohort.empty:
        return cohort
    cohort["test_id"] = cohort.test_id.astype("int64")
    cohort["next_test_id"] = pd.array([row["next_test_id"] for row in rows], dtype="Int64")
    cohort["label"] = pd.array([row["label"] for row in rows], dtype="Int64")
    hashes = vehicle_hash(cohort.vehicle_id.to_numpy())
    cohort["vehicle_role"] = np.where((hashes // np.uint64(1000)) % np.uint64(5) == 0, "holdout", "train")
    cohort["partition"] = "unused"
    for partition in ["train", "holdout"]:
        selected = (cohort.partition_window == partition) & (cohort.vehicle_role == partition) & cohort.label.notna()
        if partition == "train":
            available = pd.to_datetime(cohort.label_available_at, utc=True)
            selected &= available < FREEZE
        cohort.loc[selected, "partition"] = partition
    return cohort


def summarize(cohort):
    counts = {}
    for name in ["train", "holdout"]:
        candidates = cohort[cohort.partition_window == name]
        assigned = candidates[candidates.vehicle_role == name]
        selected = cohort[cohort.partition == name]
        counts[name] = {"window_anchors": len(candidates), "assigned_vehicle_anchors": len(assigned),
                        "assigned_status_counts": assigned.reason.value_counts().to_dict(),
                        "assigned_category_counts": assigned.status.value_counts().to_dict(),
                        "labelled_before_vehicle_split": int(candidates.label.notna().sum()),
                        "examples": len(selected), "positive": int((selected.label == 1).sum()),
                        "negative": int((selected.label == 0).sum()), "vehicles": int(selected.vehicle_id.nunique()),
                        "prior_recorded_history": int((selected.prior_recorded_tests > 0).sum()),
                        "prior_brake_advisory_history": int((selected.prior_brake_advisory_tests > 0).sum()),
                        "recurrence_positives": int(((selected.prior_brake_advisory_tests > 0) & (selected.label == 1)).sum()),
                        "recurrence_negatives": int(((selected.prior_brake_advisory_tests > 0) & (selected.label == 0)).sum()),
                        "prior_unknown_mapping": int((selected.prior_unknown_mapping_tests > 0).sum()),
                        "missing_mileage": int(selected.mileage.isna().sum()),
                        "missing_mileage_delta": int(selected.mileage_delta.isna().sum()),
                        "mileage_rollbacks": int(selected.mileage_rollback.sum()),
                        "history_at_least_365_days": int((selected.observed_history_days >= 365).sum()),
                        "history_days_median": float(selected.observed_history_days.median()) if len(selected) else None,
                        "label_available_min": selected.label_available_at.min() if len(selected) else None,
                        "label_available_max": selected.label_available_at.max() if len(selected) else None}
    overlap = set(cohort.loc[cohort.partition == "train", "vehicle_id"]) & set(cohort.loc[cohort.partition == "holdout", "vehicle_id"])
    if overlap:
        raise ValueError("Vehicle leakage across partitions")
    return {"all_anchors": len(cohort), "status_counts": cohort.reason.value_counts().to_dict(),
            "status_category_counts": cohort.status.value_counts().to_dict(),
            "all_reason_flags": dict(Counter(reason for value in cohort.all_reasons for reason in value.split("|") if reason)),
            "labelled": int(cohort.label.notna().sum()), "positive": int((cohort.label == 1).sum()),
            "negative": int((cohort.label == 0).sum()), "partitions": counts, "partition_vehicle_overlap": len(overlap)}


def run(name):
    capacity_gate()
    directory = ROOT / "data/processed" / name
    acquisition = json.loads((directory / "acquisition.json").read_text())
    if acquisition["status"] != "complete":
        raise ValueError("Cohort requires complete acquisition")
    with closing(sqlite3.connect(directory / "sample.sqlite3")) as connection:
        if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity failure")
        if connection.execute("SELECT count(*) FROM tests").fetchone()[0] > 200000:
            raise ValueError("Cohort test-row memory bound exceeded")
        if connection.execute("SELECT count(*) FROM items").fetchone()[0] > 2000000:
            raise ValueError("Cohort item-row memory bound exceeded")
        tests = pd.read_sql_query("SELECT * FROM tests", connection)
        items = pd.read_sql_query("SELECT * FROM items", connection)
    for kind, frame, prefix in [("result", tests, "tests"), ("item", items, "items")]:
        expected = sum(value["retained_rows"] for value in acquisition["sources"] if value["kind"] == kind)
        if len(frame) != expected or sum(pq.ParquetFile(path).metadata.num_rows for path in directory.glob(f"{prefix}-*.parquet")) != expected:
            raise ValueError("Completed receipts/SQLite/Parquet counts disagree")
    with closing(sqlite3.connect(ROOT / "data/processed/sample2022-2023/sample.sqlite3")) as connection:
        original = pd.read_sql_query("SELECT test_id FROM tests", connection)
    if not original.test_id.isin(tests.test_id).all():
        raise ValueError("Original deterministic subset not preserved")
    mapping = dictionary_mapping()
    capacity_gate()
    items = items.merge(tests[["test_id", "test_class_id", "source_year"]].rename(columns={"source_year": "result_source_year"}),
                        on="test_id", how="left", validate="many_to_one")
    unjoined = int(items.test_class_id.isna().sum())
    items = items.merge(mapping, on=["rfr_id", "test_class_id"], how="left", validate="many_to_one")
    items.family = items.family.fillna("unknown")
    duplicate_items = int(items.duplicated(ITEM_COLUMNS + ["source_year"]).sum())
    linked = set(tests.loc[tests.source_year == 2023, "vehicle_id"]) & set(tests.loc[tests.source_year == 2024, "vehicle_id"])
    linked_groups = tests[tests.vehicle_id.isin(linked)].groupby("vehicle_id")
    changes = {field: int((linked_groups[field].nunique() > 1).sum()) for field in ["make", "model", "first_use_date"]}
    coverage = [{"year": int(year), "tests": len(group), "vehicles": int(group.vehicle_id.nunique()),
                 "date_min": group.test_date.min(), "date_max": group.test_date.max()}
                for year, group in tests.groupby("source_year")]
    observation_end = f"{max(acquisition['years'])}-12-31"
    cohort = construct(tests, items, coverage_end=observation_end)
    training = cohort[cohort.partition == "train"]
    holdout = cohort[cohort.partition == "holdout"]
    if (pd.to_datetime(training.label_available_at, utc=True) >= FREEZE).any():
        raise ValueError("Training labels extend past model freeze")
    if (pd.to_datetime(holdout.prediction_available_at, utc=True) < FREEZE).any():
        raise ValueError("Evaluated predictions precede model freeze")
    if (vehicle_hash(tests.vehicle_id.to_numpy()) % acquisition["modulus"] != 0).any():
        raise ValueError("Sample contains vehicles outside deterministic rule")
    cohort.to_parquet(directory / "brakes-cohort.parquet", index=False)
    for partition in ["train", "holdout"]:
        subset = cohort[cohort.partition == partition]
        subset[FEATURES].to_parquet(directory / f"{partition}-features.parquet", index=False)
        subset[["test_id", "vehicle_id", "index_date", "label", "label_available_at"]].to_parquet(directory / f"{partition}-audit.parquet", index=False)
    feature_manifest = {"generated_at": now(), "features": FEATURES,
                        "row_alignment": "Feature and audit rows have identical order within each partition; no identifiers in feature files",
                        "files": {path.name: {"sha256": checksum(path), "bytes": path.stat().st_size,
                                               "rows": pq.ParquetFile(path).metadata.num_rows}
                                  for path in [directory / "brakes-cohort.parquet"]
                                  + [directory / f"{partition}-{kind}.parquet" for partition in ["train", "holdout"] for kind in ["features", "audit"]]},
                        "code_sha256": {name: checksum(ROOT / f"pipeline/{name}.py") for name in ["cohort", "expansion"]}}
    save_json(directory / "feature-manifest.json", feature_manifest)
    examples = {}
    for description, mask in [("positive", cohort.label == 1), ("negative", cohort.label == 0), ("censored", cohort.reason == "missing_followup")]:
        candidate = cohort.loc[mask.fillna(False)].sort_values(["index_date", "test_id"]).iloc[0]
        identifier = int(candidate.vehicle_id)
        history = tests[tests.vehicle_id == identifier]
        traces = []
        for test in history.sort_values(["test_date", "test_id"]).to_dict("records"):
            records = items[items.test_id == test["test_id"]]
            traces.append({key: test[key] for key in ["test_id", "test_date", "test_type", "test_result", "source_year"]}
                          | {"brake_items": records.loc[records.family == "brakes", ["rfr_id", "rfr_type_code", "location_id"]].to_dict("records"),
                             "item_counts_by_family_type": [{"family": family, "code": code, "rows": int(count)}
                                                           for (family, code), count in records.groupby(["family", "rfr_type_code"]).size().items()]})
        examples[description] = {"anchor": json.loads(candidate.to_json()), "recorded_test_trace": traces}
    save_json(directory / "real-example-traces.json", examples)
    family_advisories = set(items.loc[(items.family == "brakes") & (items.rfr_type_code == "A"), "test_id"])
    class_four = tests[tests.test_class_id == "4"]
    normal = class_four[class_four.test_type == "NT"]
    passed = normal[normal.test_result == "P"]
    coverage_items = []
    for (year, outcome), group in tests.groupby(["source_year", "test_result"]):
        coverage_items.append({"year": int(year), "outcome": outcome, "tests": len(group),
                               "with_items": int(group.test_id.isin(items.test_id).sum())})
    report = {"generated_at": now(), "sample": name, "vehicles": int(tests.vehicle_id.nunique()),
              "tests": len(tests), "items": len(items), "coverage": coverage,
              "linked_2023_2024_vehicles": len(linked), "linked_attribute_changes": changes,
              "unjoined_retained_items": unjoined, "unknown_mapping_rows": int((items.family == "unknown").sum()),
              "duplicate_item_rows": duplicate_items, "original_subset_tests_verified": len(original),
              "item_result_source_year_mismatches": int((items.source_year != items.result_source_year).sum()),
              "item_coverage_by_year_outcome": coverage_items,
              "eligibility_funnel": {"retained_tests": len(tests), "class4_tests": len(class_four),
                                     "class4_normal_tests": len(normal), "class4_normal_passes": len(passed),
                                     "class4_normal_pass_brake_advisory": int(passed.test_id.isin(family_advisories).sum())},
              "features": FEATURES, "cohort": summarize(cohort), "resources": resource_snapshot(),
              "timeline": {"training_indices": ["2022-01-01", "2022-03-31"],
                           "actual_observation_end": observation_end,
                           "training_outcome_envelope": ["2022-10-01", "2023-06-30"],
                           "model_freeze": FREEZE.isoformat(), "evaluated_indices": ["2023-07-01", "2023-09-30"],
                           "holdout_outcome_envelope": ["2024-04-01", "2024-12-30"],
                           "outcomes": "immediate NT only; inclusive 9-15 calendar months; missing never negative"},
              "ready_for_training": False,
              "readiness": "No training. Recurrence/history coverage, held-out positive counts, season shift, no mature tuning partition and retrospective revision availability require review."}
    save_json(directory / "cohort-report.json", report)
    save_json(ROOT / "artifacts/reports/phase2-cohort.json", report)
    print(json.dumps(report))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="expanded2022-2024")
    args = parser.parse_args()
    if not args.name.replace("-", "").isalnum():
        raise ValueError("Invalid sample name")
    scratch = ROOT / "data/tmp"
    os.environ.update(TEMP=str(scratch), TMP=str(scratch), SQLITE_TMPDIR=str(scratch))
    run(args.name)


if __name__ == "__main__":
    main()
