"""Stream complete acquired years into deterministic vehicle samples; never train."""

import argparse
import csv
import ctypes
import gc
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from contextlib import closing
from datetime import datetime
from pathlib import Path

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import zipfile64.zipfile as zipfile

from pipeline.sources import MANIFEST, ROOT, checksum, now, save_json


RESULT_COLUMNS = ["test_id", "vehicle_id", "test_date", "test_class_id", "test_type",
                  "test_result", "test_mileage", "postcode_area", "make", "model", "colour",
                  "fuel_type", "cylinder_capacity", "first_use_date"]
ITEM_COLUMNS = ["test_id", "rfr_id", "rfr_type_code", "location_id", "dangerous_mark"]


def vehicle_hash(identifiers):
    values = np.asarray(identifiers, dtype=np.uint64)
    with np.errstate(over="ignore"):
        values = values + np.uint64(0x9E3779B97F4A7C15)
        values = (values ^ (values >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        values = (values ^ (values >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
    return values ^ (values >> np.uint64(31))


def resource_snapshot():
    result = {"disk_free_bytes": shutil.disk_usage(ROOT).free}
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in ["total_phys", "avail_phys", "total_page",
                                                        "avail_page", "total_virtual", "avail_virtual", "avail_extended"]]

        class ProcessMemory(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
                (name, ctypes.c_size_t) for name in ["peak_ws", "ws", "peak_paged", "paged",
                                                     "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile"]]

        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError("Cannot measure available RAM")
        counters = ProcessMemory()
        counters.cb = ctypes.sizeof(counters)
        ctypes.windll.kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        if not ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            raise OSError("Cannot measure process memory")
        result.update(available_ram_bytes=status.avail_phys, working_set_bytes=counters.ws,
                      peak_working_set_bytes=counters.peak_ws, available_commit_bytes=status.avail_page,
                      commit_limit_bytes=status.total_page, private_commit_bytes=counters.pagefile,
                      peak_private_commit_bytes=counters.peak_pagefile)
    return result


def capacity_gate():
    resources = resource_snapshot()
    if resources["disk_free_bytes"] < 5 * 1024 ** 3:
        raise ValueError("Less than 5 GiB project disk reserve")
    if resources.get("available_ram_bytes", 1024 ** 3) < 256 * 1024 ** 2:
        raise ValueError("Less than 256 MiB RAM available; close applications before resuming")
    if resources.get("available_commit_bytes", 1024 ** 3) < 256 * 1024 ** 2:
        raise ValueError("Less than 256 MiB Windows commit headroom; close applications before resuming")
    return resources


def numeric_ids(series, name):
    if not series.str.fullmatch(r"[0-9]+").all():
        raise ValueError(f"Invalid or missing {name}; input must be reviewed, not silently dropped")
    return series.astype("int64")


def source_record(manifest, year, kind):
    if year not in [2022, 2023]:
        raise ValueError("Only the verified 2022-2023 pipe schema is supported; validate a new release adapter first")
    filename = f"dft_test_{kind}_{year}.zip"
    record = next(record for record in manifest["sources"] if record["filename"] == filename)
    path = ROOT / record.get("path", f"data/raw/{filename}")
    if record["status"] != "downloaded" or not path.exists() or checksum(path) != record["sha256"]:
        raise ValueError(f"Missing or checksum-invalid archive: {filename}")
    return record, path


def chunks(path, kind, chunk_rows):
    expected = RESULT_COLUMNS if kind == "result" else ITEM_COLUMNS
    with zipfile.ZipFile(path) as archive:
        members = sorted(member.filename for member in archive.infolist()
                         if member.filename.endswith(".csv") and not member.filename.startswith("__MACOSX/"))
        if not members:
            raise ValueError("Archive contains no CSV records")
        for member in members:
            with archive.open(member) as stream:
                header = stream.readline().decode("utf-8-sig").rstrip("\r\n")
            if header.split("|") != expected:
                raise ValueError(f"Unexpected actual schema: {path.name}/{member}")
            with archive.open(member) as stream:
                yield from pd.read_csv(stream, sep="|", dtype=str, keep_default_na=False,
                                       chunksize=chunk_rows, quoting=csv.QUOTE_NONE, encoding="utf-8-sig")


def append_rows(connection, frame, table):
    if frame.empty:
        return
    placeholders = ",".join("?" for _ in frame.columns)
    connection.executemany(f"INSERT INTO {table} VALUES ({placeholders})", frame.itertuples(index=False, name=None))
    connection.commit()


def ingest(years, modulus, chunk_rows, name, isolated=True):
    resources = capacity_gate()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    output = ROOT / "data/processed" / name
    if output.exists():
        raise ValueError("Sample directory exists; use a new explicit --name to preserve prior artifacts")
    output.mkdir(parents=True)
    database = output / "sample.sqlite3"
    started = time.monotonic()
    stats = {"started_at": now(), "years": years, "modulus": modulus, "chunk_rows": chunk_rows,
             "hash": "SplitMix64(unsigned decimal vehicle_id); select hash % modulus == 0",
             "resources_start": resources, "sources": [], "status": "incomplete"}
    save_json(output / "acquisition.json", stats)
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("PRAGMA cache_size=-16384")
        connection.execute("PRAGMA temp_store=FILE")
        declarations = ",".join(f'"{column}" {"INTEGER" if column in ["test_id", "vehicle_id"] else "TEXT"}' for column in RESULT_COLUMNS)
        connection.execute(f"CREATE TABLE tests ({declarations}, source_year INTEGER, PRIMARY KEY(test_id))")
        connection.execute("CREATE INDEX vehicle_history ON tests(vehicle_id,test_date,test_id)")
        connection.execute("CREATE TABLE items (test_id INTEGER, rfr_id TEXT, rfr_type_code TEXT, location_id TEXT, dangerous_mark TEXT, source_year INTEGER)")
        connection.execute("CREATE INDEX item_test ON items(test_id)")
    if isolated:
        for kind in ["result", "item"]:
            for year in years:
                capacity_gate()
                subprocess.run([sys.executable, "-u", "-m", "pipeline.pilot", "stage", "--kind", kind,
                                "--years", str(year), "--modulus", str(modulus), "--chunk-rows", str(chunk_rows),
                                "--name", name], cwd=ROOT, check=True)
                stage_stats = json.loads((output / f"{kind}-{year}-scan.json").read_text())
                stats["sources"].append(stage_stats)
                save_json(output / "acquisition.json", stats)
        stats.update(status="complete", finished_at=now(), elapsed_seconds=round(time.monotonic() - started, 2),
                     resources_end=resource_snapshot(),
                     peak_worker_working_set_bytes=max(stage["resources_end"].get("peak_working_set_bytes", 0) for stage in stats["sources"]),
                     join_index_bytes=max(stage.get("join_index_bytes", 0) for stage in stats["sources"]))
        save_json(output / "acquisition.json", stats)
        return output
    scan_stages(years, modulus, chunk_rows, output, stats, manifest)
    stats.update(status="complete", finished_at=now(), elapsed_seconds=round(time.monotonic() - started, 2),
                 resources_end=resource_snapshot())
    save_json(output / "acquisition.json", stats)
    return output


def scan_stages(years, modulus, chunk_rows, output, stats, manifest, kind_only=None):
    with closing(sqlite3.connect(output / "sample.sqlite3")) as connection:
        connection.execute("PRAGMA cache_size=-16384")
        connection.execute("PRAGMA temp_store=FILE")
        result_years = years if kind_only in [None, "result"] else []
        item_years = years if kind_only in [None, "item"] else []
        for year in result_years:
            record, path = source_record(manifest, year, "result")
            counters = {"year": year, "kind": "result", "source_sha256": record["sha256"],
                        "scanned_rows": 0, "retained_rows": 0, "types": Counter(), "outcomes": Counter(),
                        "date_min": None, "date_max": None}
            writer = None
            try:
                for chunk_number, frame in enumerate(chunks(path, "result", chunk_rows), 1):
                    frame["vehicle_id"] = numeric_ids(frame.vehicle_id, "vehicle_id")
                    frame["test_id"] = numeric_ids(frame.test_id, "test_id")
                    dates = pd.to_datetime(frame.test_date, format="%Y-%m-%d", errors="raise")
                    if not (dates.dt.year == year).all():
                        raise ValueError("Results contain dates outside selected year")
                    if not frame.test_type.isin(["NT", "PV", "PL", "RT", "EI", "ES"]).all():
                        raise ValueError("Unknown test type")
                    if not frame.test_result.isin(["P", "F", "PRS", "ABA", "ABR", "ABRVE", "R"]).all():
                        raise ValueError("Unknown test outcome")
                    counters["scanned_rows"] += len(frame)
                    counters["date_min"] = min(counters["date_min"] or frame.test_date.min(), frame.test_date.min())
                    counters["date_max"] = max(counters["date_max"] or frame.test_date.max(), frame.test_date.max())
                    counters["types"].update(frame.test_type.value_counts().to_dict())
                    counters["outcomes"].update(frame.test_result.value_counts().to_dict())
                    selected = frame.loc[vehicle_hash(frame.vehicle_id.to_numpy()) % modulus == 0].copy()
                    selected["source_year"] = year
                    counters["retained_rows"] += len(selected)
                    append_rows(connection, selected, "tests")
                    if not selected.empty:
                        table = pa.Table.from_pandas(selected, preserve_index=False)
                        if writer is None:
                            writer = pq.ParquetWriter(output / f"tests-{year}.parquet", table.schema, compression="zstd")
                        writer.write_table(table)
                    if chunk_number % 16 == 0:
                        gc.collect()
                    capacity_gate()
            finally:
                if writer:
                    writer.close()
            stats["sources"].append(counters)
            counters["resources_end"] = resource_snapshot()
            save_json(output / f"result-{year}-scan.json", counters)
            print(f"Results {year}: scanned {counters['scanned_rows']:,}; retained {counters['retained_rows']:,}", flush=True)
        test_count = connection.execute("SELECT count(*) FROM tests").fetchone()[0]
        if test_count > 200000:
            raise ValueError("In-memory join index cap (200,000 sampled tests) exceeded; use a disk-backed staging join for expansion")
        test_ids = pd.read_sql_query("SELECT test_id FROM tests ORDER BY test_id", connection).test_id.to_numpy(dtype="int64")
        stats["join_index_bytes"] = test_ids.nbytes
        for year in item_years:
            record, path = source_record(manifest, year, "item")
            counters = {"year": year, "kind": "item", "source_sha256": record["sha256"],
                        "scanned_rows": 0, "retained_rows": 0, "types": Counter()}
            writer = None
            try:
                for chunk_number, frame in enumerate(chunks(path, "item", chunk_rows), 1):
                    frame["test_id"] = numeric_ids(frame.test_id, "test_id")
                    if not frame.rfr_type_code.isin(["A", "F", "P", "M"]).all():
                        raise ValueError("Unknown item severity")
                    counters["scanned_rows"] += len(frame)
                    counters["types"].update(frame.rfr_type_code.value_counts().to_dict())
                    selected = frame.loc[np.isin(frame.test_id.to_numpy(), test_ids, assume_unique=False)].copy()
                    selected["source_year"] = year
                    counters["retained_rows"] += len(selected)
                    append_rows(connection, selected, "items")
                    if not selected.empty:
                        table = pa.Table.from_pandas(selected, preserve_index=False)
                        if writer is None:
                            writer = pq.ParquetWriter(output / f"items-{year}.parquet", table.schema, compression="zstd")
                        writer.write_table(table)
                    if chunk_number % 16 == 0:
                        gc.collect()
                    capacity_gate()
            finally:
                if writer:
                    writer.close()
            stats["sources"].append(counters)
            counters["resources_end"] = resource_snapshot()
            counters["join_index_bytes"] = test_ids.nbytes
            save_json(output / f"item-{year}-scan.json", counters)
            print(f"Items {year}: scanned {counters['scanned_rows']:,}; joined {counters['retained_rows']:,}", flush=True)


def resume(name):
    capacity_gate()
    output = ROOT / "data/processed" / name
    stats = json.loads((output / "acquisition.json").read_text())
    if stats["status"] != "incomplete":
        raise ValueError("Only incomplete acquisitions can be resumed")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    stats.setdefault("resumptions", []).append({"resumed_at": now(), "resources": resource_snapshot()})
    stats["sources"] = []
    for kind in ["result", "item"]:
        for year in stats["years"]:
            receipt = output / f"{kind}-{year}-scan.json"
            table = "tests" if kind == "result" else "items"
            parquet = output / f"{table}-{year}.parquet"
            if receipt.exists():
                completed = json.loads(receipt.read_text())
                record = next(record for record in manifest["sources"] if record["filename"] == f"dft_test_{kind}_{year}.zip")
                with closing(sqlite3.connect(output / "sample.sqlite3")) as connection:
                    retained = connection.execute(f"SELECT count(*) FROM {table} WHERE source_year=?", (year,)).fetchone()[0]
                parquet_rows = pq.ParquetFile(parquet).metadata.num_rows if parquet.exists() else 0
                if (completed["source_sha256"] != record["sha256"]
                        or retained != completed["retained_rows"] or parquet_rows != retained):
                    raise ValueError("Completed-stage provenance/counts differ; diagnose before resuming")
                stats["sources"].append(completed)
                save_json(output / "acquisition.json", stats)
                continue
            with closing(sqlite3.connect(output / "sample.sqlite3")) as connection:
                connection.execute(f"DELETE FROM {table} WHERE source_year=?", (year,))
                connection.commit()
            if parquet.exists():
                failed = output / "failed"
                failed.mkdir(exist_ok=True)
                target = failed / f"{parquet.stem}-{time.time_ns()}.parquet"
                if not target.resolve().is_relative_to(output.resolve()):
                    raise ValueError("Invalid failed-artifact destination")
                parquet.replace(target)
            capacity_gate()
            subprocess.run([sys.executable, "-u", "-m", "pipeline.pilot", "stage", "--kind", kind,
                            "--years", str(year), "--modulus", str(stats["modulus"]),
                            "--chunk-rows", str(stats["chunk_rows"]), "--name", name], cwd=ROOT, check=True)
            stats["sources"].append(json.loads(receipt.read_text()))
            save_json(output / "acquisition.json", stats)
    stats.update(status="complete", finished_at=now(), resources_end=resource_snapshot(),
                 elapsed_seconds=round((datetime.fromisoformat(now()) - datetime.fromisoformat(stats["started_at"])).total_seconds(), 2),
                 peak_worker_working_set_bytes=max(stage["resources_end"].get("peak_working_set_bytes", 0) for stage in stats["sources"]),
                 peak_worker_private_commit_bytes=max(stage["resources_end"].get("peak_private_commit_bytes", 0) for stage in stats["sources"]),
                 private_commit_measurement_stages=sum("peak_private_commit_bytes" in stage["resources_end"] for stage in stats["sources"]),
                 join_index_bytes=max(stage.get("join_index_bytes", 0) for stage in stats["sources"]))
    save_json(output / "acquisition.json", stats)


def dictionaries():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    record = next(record for record in manifest["sources"] if record["filename"] == "lookup.zip")
    path = ROOT / record["path"]
    if checksum(path) != record["sha256"]:
        raise ValueError("Lookup checksum differs")
    with zipfile.ZipFile(path) as archive:
        details = pd.read_csv(archive.open("item_detail.csv"), sep="|", dtype=str, keep_default_na=False)
        groups = pd.read_csv(archive.open("item_group.csv"), sep="|", dtype=str, keep_default_na=False)
    if details.duplicated(["rfr_id", "test_class_id"]).any() or groups.duplicated(["test_item_id", "test_class_id"]).any():
        raise ValueError("Duplicate dictionary keys")
    group_map = {(row.test_item_id, row.test_class_id): row for row in groups.itertuples()}
    mapping = []
    for row in details.itertuples():
        ancestors = []
        current = row.test_item_id
        seen = set()
        while current != "0":
            if current in seen or (current, row.test_class_id) not in group_map:
                raise ValueError("Invalid dictionary hierarchy")
            seen.add(current)
            group = group_map[(current, row.test_class_id)]
            ancestors.append(group.item_name.strip().casefold())
            current = group.parent_id
        brakes = any(name in ["brakes", "motorcycle brakes"] for name in ancestors)
        tyres = "tyres" in ancestors
        if brakes and tyres:
            raise ValueError("Overlapping component mapping")
        mapping.append({"rfr_id": row.rfr_id, "test_class_id": row.test_class_id,
                        "family": "brakes" if brakes else "tyres" if tyres else "other",
                        "deficiency_category": row.rfr_deficiency_category})
    return pd.DataFrame(mapping), {"lookup_sha256": record["sha256"], "detail_rows": len(details),
                                   "group_rows": len(groups), "family_mapping_rows": pd.DataFrame(mapping).family.value_counts().to_dict()}


def comparisons(tests, items):
    counts = items.groupby(["test_id", "family", "rfr_type_code"]).size().unstack(["family", "rfr_type_code"], fill_value=0)
    routine = tests[tests.test_type == "NT"].copy()
    routine["test_id"] = routine.test_id.astype("Int64")
    routine = routine.sort_values(["vehicle_id", "test_date", "test_id"])
    routine["same_day_count"] = routine.groupby(["vehicle_id", "test_date"]).test_id.transform("size")
    grouped = routine.groupby("vehicle_id", sort=False)
    for column in ["test_id", "test_date", "test_result", "same_day_count", "test_class_id"]:
        routine[f"next_{column}"] = grouped[column].shift(-1)
    unknown_tests = set(items.loc[items.family == "unknown", "test_id"])
    item_counts = items.groupby("test_id").size()
    failure_tests = set(items.loc[items.rfr_type_code.isin(["F", "P"]), "test_id"])
    unrepaired_tests = set(items.loc[items.rfr_type_code == "F", "test_id"])
    rectified_tests = set(items.loc[items.rfr_type_code == "P", "test_id"])
    summaries = {}
    for family in ["brakes", "tyres"]:
        advisory = counts.get((family, "A"), pd.Series(dtype=int))
        failed = counts.get((family, "F"), pd.Series(dtype=int))
        repaired = counts.get((family, "P"), pd.Series(dtype=int))
        anchors = routine[(routine.test_class_id == "4") & (routine.test_result == "P")
                          & routine.test_id.isin(advisory[advisory > 0].index)].copy()
        anchors["gap_days"] = (pd.to_datetime(anchors.next_test_date) - pd.to_datetime(anchors.test_date)).dt.days
        ambiguous = (anchors.same_day_count > 1) | (anchors.next_same_day_count > 1)
        invalid_outcome = anchors.next_test_id.notna() & ~anchors.next_test_result.isin(["P", "F", "PRS"])
        missing_failure_items = anchors.next_test_result.isin(["F", "PRS"]) & ~anchors.next_test_id.isin(item_counts.index)
        inconsistent = (anchors.test_id.isin(failure_tests)
                        | ((anchors.next_test_result == "P") & anchors.next_test_id.isin(failure_tests))
                        | ((anchors.next_test_result == "F") & ~anchors.next_test_id.isin(unrepaired_tests))
                        | ((anchors.next_test_result == "PRS") & ~anchors.next_test_id.isin(rectified_tests)))
        unknown = anchors.test_id.isin(unknown_tests) | anchors.next_test_id.isin(unknown_tests)
        class_change = anchors.next_test_id.notna() & (anchors.next_test_class_id != "4")
        valid = (anchors.next_test_id.notna() & ~ambiguous & ~invalid_outcome & ~missing_failure_items & ~inconsistent & ~unknown & ~class_change
                 & anchors.gap_days.between(1, 550))
        labels = anchors.loc[valid].copy()
        labels["family"] = family
        labels["positive"] = labels.next_test_id.isin(failed[failed > 0].index.union(repaired[repaired > 0].index))
        labels["unrepaired_failure"] = labels.next_test_id.isin(failed[failed > 0].index)
        summaries[family] = {
            "eligible_advisory_tests": len(anchors), "advisory_item_rows": int(advisory.reindex(anchors.test_id, fill_value=0).sum()),
            "observed_next_routine": int(anchors.next_test_id.notna().sum()), "usable_followups": len(labels),
            "positive_fail_or_prs": int(labels.positive.sum()), "positive_fail_items_only": int(labels.unrepaired_failure.sum()),
            "no_next_test_censored": int(anchors.next_test_id.isna().sum()), "ambiguous_same_day": int(ambiguous.sum()),
            "next_incomplete_or_refused": int(invalid_outcome.sum()), "next_failure_without_items": int(missing_failure_items.sum()),
            "inconsistent_result_item_pair": int(inconsistent.sum()),
            "next_test_class_change": int(class_change.sum()),
            "unknown_mapping_in_pair": int(unknown.sum()), "gap_outside_1_550_days": int((anchors.next_test_id.notna() & ~anchors.gap_days.between(1, 550)).sum()),
            "anchors_by_year": anchors.source_year.value_counts().sort_index().to_dict(),
            "usable_by_anchor_year": labels.source_year.value_counts().sort_index().to_dict(),
            "gap_days_quantiles": {str(quantile): float(value) for quantile, value in labels.gap_days.quantile([0, 0.5, 0.9, 1]).dropna().items()},
            "usable_gap_below_180_days": int((labels.gap_days < 180).sum()),
            "chronological_2023_cut": {
                "training_labels_observed_before_2023": int((labels.next_test_date < "2023-01-01").sum()),
                "evaluation_anchors_in_2023_with_observed_labels": int((labels.test_date >= "2023-01-01").sum()),
                "cross_boundary_pairs_excluded_from_training": int(((labels.test_date < "2023-01-01") & (labels.next_test_date >= "2023-01-01")).sum()),
            },
        }
        yield family, summaries[family], labels


def report(sample_name):
    output = ROOT / "data/processed" / sample_name
    acquisition = json.loads((output / "acquisition.json").read_text())
    if acquisition["status"] != "complete":
        raise ValueError("Cannot report incomplete scan as complete histories")
    with closing(sqlite3.connect(output / "sample.sqlite3")) as connection:
        integrity = connection.execute("PRAGMA quick_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError("SQLite integrity check failed")
        if connection.execute("SELECT count(*) FROM tests").fetchone()[0] > 200000:
            raise ValueError("Report exceeds bounded sampled-test count")
        if connection.execute("SELECT count(*) FROM items").fetchone()[0] > 2000000:
            raise ValueError("Report exceeds bounded sampled-item count")
        tests = pd.read_sql_query("SELECT * FROM tests", connection)
        items = pd.read_sql_query("SELECT * FROM items", connection)
    for kind, frame in [("result", tests), ("item", items)]:
        expected = sum(source["retained_rows"] for source in acquisition["sources"] if source["kind"] == kind)
        if len(frame) != expected:
            raise ValueError("SQLite row count differs from completed scan manifest")
        parquet_prefix = "tests" if kind == "result" else "items"
        parquet_rows = sum(pq.ParquetFile(path).metadata.num_rows for path in output.glob(f"{parquet_prefix}-*.parquet"))
        if parquet_rows != expected:
            raise ValueError("Parquet row count differs from completed scan manifest")
    mapping, mapping_stats = dictionaries()
    items = items.merge(tests[["test_id", "test_class_id", "test_result"]], on="test_id", how="left", validate="many_to_one")
    items = items.merge(mapping, on=["rfr_id", "test_class_id"], how="left", validate="many_to_one")
    items["family"] = items.family.fillna("unknown")
    groups = tests.groupby("vehicle_id")
    stable_fields = ["make", "model", "first_use_date"]
    contradictions = {field: int((groups[field].nunique() > 1).sum()) for field in stable_fields}
    cross_year = groups.source_year.nunique() > 1
    linked_ids = cross_year.index[cross_year]
    linked_groups = tests[tests.vehicle_id.isin(linked_ids)].groupby("vehicle_id")
    linked_changes = {field: int((linked_groups[field].nunique() > 1).sum()) for field in stable_fields}
    by_outcome = []
    with_item = set(items.test_id)
    for (year, outcome), frame in tests.groupby(["source_year", "test_result"]):
        by_outcome.append({"year": int(year), "outcome": outcome, "tests": len(frame),
                           "with_items": int(frame.test_id.isin(with_item).sum()),
                           "without_items": int((~frame.test_id.isin(with_item)).sum())})
    comparison = {}
    for family, summary, labels in comparisons(tests, items):
        comparison[family] = summary
        labels.to_parquet(output / f"{family}-followups.parquet", index=False)
    quality = {"generated_at": now(), "sample": sample_name, "acquisition": acquisition,
               "tests": len(tests), "vehicles": int(tests.vehicle_id.nunique()), "items": len(items),
               "date_min": tests.test_date.min(), "date_max": tests.test_date.max(),
               "cross_year_vehicles": int(cross_year.sum()), "vehicle_attribute_changes": contradictions,
               "cross_year_vehicle_attribute_changes": linked_changes,
               "sqlite_integrity": integrity,
               "unjoined_retained_items": int(items.test_class_id.isna().sum()),
               "join_scope": "Items filtered against sampled test IDs; this does not measure orphan items in the unsampled population",
               "duplicate_test_ids": int(tests.test_id.duplicated().sum()),
               "duplicate_item_rows": int(items.duplicated(ITEM_COLUMNS + ["source_year"]).sum()),
               "mapping": {**mapping_stats, "unknown_item_rows": int((items.family == "unknown").sum()),
                           "unknown_rfr_ids": int(items.loc[items.family == "unknown", "rfr_id"].nunique()),
                           "unknown_by_class": items.loc[items.family == "unknown", "test_class_id"].value_counts().to_dict(),
                           "observed_categories": items.deficiency_category.fillna("unknown").value_counts().to_dict()},
               "coverage_by_year_outcome": by_outcome, "comparison_class4": comparison,
               "item_types_by_test_outcome": [
                   {"test_result": outcome, "item_type": kind, "rows": int(count)}
                   for (outcome, kind), count in items.groupby(["test_result", "rfr_type_code"]).size().items()],
               "resources_report": resource_snapshot(),
               "limitation": "Complete scanned histories for acquired years only; unresolved status and repairs between tests are unobserved"}
    save_json(output / "quality.json", quality)
    save_json(ROOT / "artifacts/reports" / f"{sample_name}-quality.json", quality)
    print(json.dumps({"sample": sample_name, "tests": len(tests), "vehicles": quality["vehicles"],
                      "cross_year_vehicles": quality["cross_year_vehicles"], "comparison_class4": comparison}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["ingest", "report", "stage", "resume"])
    parser.add_argument("--kind", choices=["result", "item"])
    parser.add_argument("--years", nargs="+", type=int, default=[2022, 2023])
    parser.add_argument("--modulus", type=int, default=100000)
    parser.add_argument("--chunk-rows", type=int, default=25000)
    parser.add_argument("--name", default="pilot")
    args = parser.parse_args()
    if not args.name.replace("-", "").isalnum() or args.modulus < 1000 or not 1 <= args.chunk_rows <= 100000:
        raise ValueError("Invalid name, modulus (<1000), or chunk bound")
    if args.years != sorted(set(args.years)):
        raise ValueError("Years must be unique and ascending")
    scratch = ROOT / "data/tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    os.environ.update(TEMP=str(scratch), TMP=str(scratch), SQLITE_TMPDIR=str(scratch))
    if args.command == "ingest":
        ingest(args.years, args.modulus, args.chunk_rows, args.name)
    elif args.command == "resume":
        resume(args.name)
    elif args.command == "stage":
        if args.kind is None or len(args.years) != 1:
            raise ValueError("Internal stage requires exactly one year and kind")
        output = ROOT / "data/processed" / args.name
        acquisition = json.loads((output / "acquisition.json").read_text())
        if (acquisition["status"] != "incomplete" or acquisition["modulus"] != args.modulus
                or args.years[0] not in acquisition["years"] or args.chunk_rows != acquisition["chunk_rows"]):
            raise ValueError("Stage is only valid for the matching incomplete acquisition")
        scan_stages(args.years, args.modulus, args.chunk_rows, output, {"sources": []},
                    json.loads(MANIFEST.read_text(encoding="utf-8")), args.kind)
    else:
        capacity_gate()
        report(args.name)


if __name__ == "__main__":
    main()
