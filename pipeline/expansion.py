"""Targeted stored ZIP members and separately validated June 2026 CSV adapter."""

import argparse
import csv
import gc
import hashlib
import json
import os
import sqlite3
import struct
import subprocess
import sys
import time
import warnings
import zlib
from collections import Counter
from contextlib import closing
from itertools import islice

from pipeline.pilot import (ITEM_COLUMNS, RESULT_COLUMNS, append_rows, capacity_gate,
                            chunks, numeric_ids, resource_snapshot, vehicle_hash)
from pipeline.sources import (BLOCK, MANIFEST, ROOT, RemoteZip, checksum, now,
                              request, save_json)
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import zipfile64.zipfile as zipfile


MEMBERS = ROOT / "docs/member_manifest.json"
CSV_RESULTS = RESULT_COLUMNS + ["completed_date"]
CSV_ITEMS = ["test_id", "rfr_id", "rfr_type_code", "mot_test_rfr_location_type_id",
             "dangerous_mark", "completed_date"]


def source(kind):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return next(record for record in manifest["sources"]
                if record["filename"] == f"dft_test_{kind}_extracts_2024.zip")


def member_path(kind, month):
    return ROOT / f"data/raw/members2024/{kind}-2024{month:02d}.csv"


def download_member(record, member, remote, pinned):
    if member.compress_type != 0 or member.compress_size != member.file_size:
        raise ValueError("Selective acquisition supports stored members only; use a full archive otherwise")
    if member.flag_bits & 1 or member.file_size > 600_000_000:
        raise ValueError("Encrypted or oversized member")
    remote.seek(member.header_offset)
    header = remote.read(30)
    fields = struct.unpack("<IHHHHHIIIHH", header)
    if fields[0] != 0x04034B50 or fields[3] != 0:
        raise ValueError("Unexpected ZIP local header")
    start = member.header_offset + 30 + fields[-2] + fields[-1]
    end = start + member.file_size - 1
    month = int(member.filename.rsplit(".", 1)[0][-2:])
    kind = "result" if "result" in record["filename"] else "item"
    path = member_path(kind, month)
    identity = {"url": record["url"], "etag": record["etag"], "archive_bytes": record["compressed_bytes"],
                "member": member.filename, "range_start": start, "range_end": end,
                "bytes": member.file_size, "crc32": f"{member.CRC:08x}", "kind": kind, "month": month}
    previous = next((value for value in pinned["members"] if value["member"] == member.filename), None)
    if path.exists():
        if (previous and all(previous[key] == value for key, value in identity.items())
                and path.stat().st_size == member.file_size and checksum(path) == previous["sha256"]):
            return previous
        raise ValueError("Existing member differs from pinned identity/checksum")
    capacity_gate()
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".csv.part")
    for attempt in range(3):
        try:
            digest = hashlib.sha256()
            crc = 0
            received = 0
            with request(record["url"], headers={"Range": f"bytes={start}-{end}", "If-Match": record["etag"]}) as response:
                if (response.status != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end}/{remote.size}"
                        or response.headers.get("ETag") != record["etag"]):
                    raise ValueError("Server did not honor pinned exact member range")
                with partial.open("wb") as stream:
                    while block := response.read(BLOCK):
                        received += len(block)
                        if received > member.file_size:
                            raise ValueError("Member response exceeds pinned size")
                        digest.update(block)
                        crc = zlib.crc32(block, crc)
                        stream.write(block)
                        capacity_gate()
            if received != member.file_size:
                raise OSError("Incomplete member transfer")
            if crc != member.CRC or (previous and digest.hexdigest() != previous["sha256"]):
                raise ValueError("Member CRC/checksum differs")
            partial.replace(path)
            return {**identity, "sha256": digest.hexdigest(), "retrieved_at": now(),
                    "path": path.relative_to(ROOT).as_posix(), "status": "downloaded"}
        except OSError:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def fetch(months):
    if any(month != 1 for month in months):
        gate_path = ROOT / "artifacts/reports/expansion-gate.json"
        if not gate_path.exists() or not json.loads(gate_path.read_text()).get("passed"):
            raise ValueError("January linkage gate must pass before larger transfers")
    pinned = json.loads(MEMBERS.read_text()) if MEMBERS.exists() else {
        "scope": "Complete stored CSV members; parent ZIPs NOT fully downloaded or SHA256 verified",
        "retry_policy": "Sequential exact ranges; interrupted member restarts, never unvalidated resume",
        "members": []}
    for kind in ["result", "item"]:
        record = source(kind)
        remote = RemoteZip(record)
        with zipfile.ZipFile(remote) as archive:
            members = [member for member in archive.infolist() if member.filename.endswith(".csv")]
            if len(members) != 12:
                raise ValueError("Expected 12 monthly CSVs")
            for month in months:
                member = next(member for member in members if member.filename.endswith(f"2024{month:02d}.csv"))
                value = download_member(record, member, remote, pinned)
                pinned["members"] = [old for old in pinned["members"] if old["member"] != value["member"]] + [value]
                save_json(MEMBERS, pinned)
                print(f"Verified {kind} 2024-{month:02d}: {value['bytes']:,} bytes", flush=True)


def csv_records(path, expected, diagnostics=None):
    diagnostics = diagnostics if diagnostics is not None else Counter()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        if next(csv.reader([stream.readline()])) != expected:
            raise ValueError("Newer CSV header differs from explicit adapter")
        for line_number, line in enumerate(stream, 2):
            literal = line.rstrip("\r\n").split(",")
            if '"' not in line:
                if len(literal) != len(expected):
                    raise ValueError(f"Ambiguous CSV structure at {path.name}:{line_number}; no rows skipped")
                diagnostics["unquoted_records"] += 1
                yield literal
                continue
            try:
                parsed = next(csv.reader([line], strict=True))
            except csv.Error:
                parsed = []
            if len(parsed) == len(expected):
                diagnostics["standard_csv_records"] += 1
                yield parsed
            elif len(literal) == len(expected):
                diagnostics["literal_quote_records"] += 1
                yield literal
            else:
                raise ValueError(f"Ambiguous CSV structure at {path.name}:{line_number}; no rows skipped")


def modern_frames(path, kind, chunk_rows, diagnostics):
    expected = CSV_RESULTS if kind == "result" else CSV_ITEMS
    if kind == "result":
        records = csv_records(path, expected, diagnostics)
        while batch := list(islice(records, chunk_rows)):
            yield pd.DataFrame(batch, columns=expected)
    else:
        with path.open(encoding="utf-8-sig") as stream:
            if next(csv.reader([stream.readline()])) != expected:
                raise ValueError("Newer CSV header differs from explicit adapter")
        with warnings.catch_warnings():
            warnings.simplefilter("error", pd.errors.ParserWarning)
            with pd.read_csv(path, dtype=str, keep_default_na=False, chunksize=chunk_rows,
                             quoting=csv.QUOTE_NONE, index_col=False, skip_blank_lines=False,
                             on_bad_lines="error", encoding="utf-8-sig") as reader:
                for frame in reader:
                    if list(frame.columns) != expected:
                        raise ValueError("Unexpected item columns")
                    if diagnostics is not None:
                        diagnostics["unquoted_item_records"] += len(frame)
                    yield frame


def modern_chunks(kind, month, chunk_rows=25000, diagnostics=None):
    path = member_path(kind, month)
    for frame in modern_frames(path, kind, chunk_rows, diagnostics):
        dates = pd.to_datetime(frame.completed_date, format="ISO8601", utc=True, errors="raise")
        if dates.isna().any():
            raise ValueError("Missing completion timestamp")
        if kind == "result":
            test_dates = pd.to_datetime(frame.test_date, format="%Y-%m-%d", errors="raise")
            if not ((test_dates.dt.year == 2024) & (test_dates.dt.month == month)).all():
                raise ValueError("Monthly source test dates outside expected coverage")
            if (dates.dt.tz_localize(None).dt.normalize() < test_dates).any():
                raise ValueError("Completion precedes test date")
        else:
            frame = frame.rename(columns={"mot_test_rfr_location_type_id": "location_id"})
        if diagnostics is not None:
            diagnostics[f"month_{month:02d}_rows"] += len(frame)
        yield frame


def joined_test_mask(identifiers, sorted_test_ids):
    positions = np.searchsorted(sorted_test_ids, identifiers)
    inside = positions < len(sorted_test_ids)
    matched = np.zeros(len(identifiers), dtype=bool)
    matched[inside] = sorted_test_ids[positions[inside]] == identifiers[inside]
    return matched


def gate():
    capacity_gate()
    manifest = json.loads(MEMBERS.read_text())
    for kind in ["result", "item"]:
        record = next(value for value in manifest["members"] if value["kind"] == kind and value["month"] == 1)
        if checksum(ROOT / record["path"]) != record["sha256"]:
            raise ValueError("Gate source checksum differs")
    retained = []
    scanned = 0
    codes = Counter()
    lexical = Counter()
    for frame in modern_chunks("result", 1, diagnostics=lexical):
        frame.vehicle_id = numeric_ids(frame.vehicle_id, "vehicle_id")
        frame.test_id = numeric_ids(frame.test_id, "test_id")
        scanned += len(frame)
        codes.update(frame.test_type.value_counts().to_dict())
        retained.append(frame.loc[vehicle_hash(frame.vehicle_id.to_numpy()) % 10000 == 0])
        gc.collect()
        capacity_gate()
    tests = pd.concat(retained, ignore_index=True)
    with closing(sqlite3.connect(ROOT / "data/processed/sample2022-2023/sample.sqlite3")) as connection:
        old = pd.read_sql_query("SELECT vehicle_id,make,model,first_use_date FROM tests WHERE source_year=2023", connection)
    pairs = tests.merge(old.drop_duplicates(), on="vehicle_id", suffixes=("", "_old"))
    changes = {field: int((pairs[field] != pairs[f"{field}_old"]).sum()) for field in ["make", "model", "first_use_date"]}
    selected_items = []
    scanned_items = 0
    for frame in modern_chunks("item", 1, diagnostics=lexical):
        frame.test_id = numeric_ids(frame.test_id, "test_id")
        scanned_items += len(frame)
        selected_items.append(frame.loc[frame.test_id.isin(tests.test_id)])
        gc.collect()
        capacity_gate()
    items = pd.concat(selected_items, ignore_index=True)
    from pipeline.cohort import dictionary_mapping
    mapping = dictionary_mapping()
    joined = items.merge(tests[["test_id", "test_class_id"]], on="test_id", validate="many_to_one")
    joined = joined.merge(mapping, on=["rfr_id", "test_class_id"], how="left", validate="many_to_one")
    outcomes = []
    for outcome, group in tests.groupby("test_result"):
        outcomes.append({"outcome": outcome, "tests": len(group), "with_items": int(group.test_id.isin(items.test_id).sum())})
    report = {"generated_at": now(), "scope": "Complete January 2024 paired members; fixed 1/10000 diagnostic sample",
              "result_rows": scanned, "item_rows": scanned_items, "sample_tests": len(tests),
              "sample_vehicles": int(tests.vehicle_id.nunique()), "sample_items": len(items),
              "linked_2023_vehicle_ids": int(pairs.vehicle_id.nunique()), "attribute_disagreements": changes,
              "duplicate_test_ids": int(tests.test_id.duplicated().sum()),
              "unknown_mapping_rows": int(joined.family.isna().sum()), "outcomes": outcomes,
              "actual_test_types": dict(codes), "lexical_diagnostics": dict(lexical), "resources": resource_snapshot()}
    failed_items = any(value["with_items"] != value["tests"] for value in outcomes if value["outcome"] in ["F", "PRS"])
    report["passed"] = bool(report["linked_2023_vehicle_ids"] >= 100 and not any(changes.values())
                            and not report["duplicate_test_ids"] and not report["unknown_mapping_rows"] and not failed_items)
    save_json(ROOT / "artifacts/reports/expansion-gate.json", report)
    print(json.dumps(report))
    if not report["passed"]:
        raise ValueError("Cross-release gate failed; diagnose before more acquisition")


def stage(name, kind, year, modulus):
    output = ROOT / "data/processed" / name
    receipt = output / f"{kind}-{year}-scan.json"
    if receipt.exists():
        raise ValueError("Stage receipt already exists")
    provenance = []
    if year < 2024:
        from pipeline.pilot import source_record
        record, path = source_record(json.loads(MANIFEST.read_text()), year, kind)
        provenance.append({"path": record["path"], "sha256": record["sha256"]})
        frames = chunks(path, kind, 25000)
    else:
        pinned = json.loads(MEMBERS.read_text())
        records = sorted([value for value in pinned["members"] if value["kind"] == kind], key=lambda value: value["month"])
        if [value["month"] for value in records] != list(range(1, 13)):
            raise ValueError("Complete 2024 member pair required before claiming annual histories")
        for record in records:
            if checksum(ROOT / record["path"]) != record["sha256"]:
                raise ValueError("Monthly checksum differs")
            provenance.append({"path": record["path"], "sha256": record["sha256"]})
        lexical = Counter()
        frames = (frame for month in range(1, 13) for frame in modern_chunks(kind, month, diagnostics=lexical))
    stats = {"kind": kind, "year": year, "provenance": provenance, "scanned_rows": 0,
             "retained_rows": 0, "codes": Counter(), "started_at": now(), "resources_start": capacity_gate()}
    writer = None
    table_name = "tests" if kind == "result" else "items"
    with closing(sqlite3.connect(output / "sample.sqlite3")) as connection:
        connection.execute("PRAGMA cache_size=-16384")
        connection.execute("PRAGMA temp_store=FILE")
        if kind == "item":
            count = connection.execute("SELECT count(*) FROM tests").fetchone()[0]
            if count > 200000:
                raise ValueError("Sampled-ID cap exceeded; disk join required")
            test_ids = pd.read_sql_query("SELECT test_id FROM tests ORDER BY test_id", connection).test_id.to_numpy(dtype="int64")
            stats["join_index_bytes"] = test_ids.nbytes
        try:
            for number, frame in enumerate(frames, 1):
                frame.test_id = numeric_ids(frame.test_id, "test_id")
                if kind == "result":
                    frame.vehicle_id = numeric_ids(frame.vehicle_id, "vehicle_id")
                    dates = pd.to_datetime(frame.test_date, format="%Y-%m-%d", errors="raise")
                    if not (dates.dt.year == year).all():
                        raise ValueError("Result outside selected year")
                    if not frame.test_type.isin(["NT", "PV", "PL", "RT", "EI", "ES"]).all():
                        raise ValueError("Unknown test type")
                    if not frame.test_result.isin(["P", "F", "PRS", "ABA", "ABR", "ABRVE", "R"]).all():
                        raise ValueError("Unknown outcome")
                    selected = frame.loc[vehicle_hash(frame.vehicle_id.to_numpy()) % modulus == 0].copy()
                    stats["codes"].update(frame.test_result.value_counts().to_dict())
                else:
                    if not frame.rfr_type_code.isin(["A", "F", "P", "M"]).all():
                        raise ValueError("Unknown item code")
                    selected = frame.loc[joined_test_mask(frame.test_id.to_numpy(), test_ids)].copy()
                    stats["codes"].update(frame.rfr_type_code.value_counts().to_dict())
                if "completed_date" not in selected:
                    selected["completed_date"] = ""
                selected["source_year"] = year
                selected = selected[(RESULT_COLUMNS if kind == "result" else ITEM_COLUMNS) + ["completed_date", "source_year"]]
                append_rows(connection, selected, table_name)
                stats["scanned_rows"] += len(frame)
                stats["retained_rows"] += len(selected)
                if kind == "result":
                    stats["date_min"] = min(stats.get("date_min", frame.test_date.min()), frame.test_date.min())
                    stats["date_max"] = max(stats.get("date_max", frame.test_date.max()), frame.test_date.max())
                if not selected.empty:
                    arrow = pa.Table.from_pandas(selected, preserve_index=False)
                    if writer is None:
                        writer = pq.ParquetWriter(output / f"{table_name}-{year}.parquet", arrow.schema, compression="zstd")
                    writer.write_table(arrow)
                if number % 16 == 0:
                    gc.collect()
                capacity_gate()
        finally:
            if writer:
                writer.close()
    stats.update(finished_at=now(), resources_end=resource_snapshot(),
                 lexical_diagnostics=dict(lexical) if year == 2024 else {})
    save_json(receipt, stats)
    print(f"{kind} {year}: scanned {stats['scanned_rows']:,}; retained {stats['retained_rows']:,}", flush=True)


def ingest(name, modulus):
    capacity_gate()
    gate_report = json.loads((ROOT / "artifacts/reports/expansion-gate.json").read_text())
    if not gate_report["passed"]:
        raise ValueError("January linkage gate must pass")
    output = ROOT / "data/processed" / name
    if output.exists():
        raise ValueError("Existing output protected; choose an explicit new name")
    output.mkdir(parents=True)
    stats = {"started_at": now(), "years": [2022, 2023, 2024], "modulus": modulus,
             "hash": "SplitMix64(unsigned decimal vehicle_id); hash % modulus == 0",
             "status": "incomplete", "sources": [], "resources_start": resource_snapshot()}
    save_json(output / "acquisition.json", stats)
    with closing(sqlite3.connect(output / "sample.sqlite3")) as connection:
        declarations = ",".join(f'"{column}" {"INTEGER" if column in ["test_id", "vehicle_id"] else "TEXT"}' for column in RESULT_COLUMNS)
        connection.execute(f"CREATE TABLE tests ({declarations}, completed_date TEXT, source_year INTEGER, PRIMARY KEY(test_id))")
        connection.execute("CREATE INDEX vehicle_history ON tests(vehicle_id,test_date,test_id)")
        connection.execute("CREATE TABLE items (test_id INTEGER, rfr_id TEXT, rfr_type_code TEXT, location_id TEXT, dangerous_mark TEXT, completed_date TEXT, source_year INTEGER)")
        connection.execute("CREATE INDEX item_test ON items(test_id)")
    for kind in ["result", "item"]:
        for year in [2022, 2023, 2024]:
            subprocess.run([sys.executable, "-u", "-m", "pipeline.expansion", "stage", "--name", name,
                            "--kind", kind, "--year", str(year), "--modulus", str(modulus)], cwd=ROOT, check=True)
            stats["sources"].append(json.loads((output / f"{kind}-{year}-scan.json").read_text()))
            save_json(output / "acquisition.json", stats)
    stats.update(status="complete", finished_at=now(), resources_end=resource_snapshot())
    save_json(output / "acquisition.json", stats)


def resume(name):
    capacity_gate()
    output = ROOT / "data/processed" / name
    stats = json.loads((output / "acquisition.json").read_text())
    if stats["status"] != "incomplete":
        raise ValueError("Only incomplete expansions may resume")
    source_manifest = json.loads(MANIFEST.read_text())
    member_manifest = json.loads(MEMBERS.read_text())
    trusted = {value["path"]: value["sha256"] for value in source_manifest["sources"] if value.get("path")}
    trusted.update({value["path"]: value["sha256"] for value in member_manifest["members"]})
    stats["sources"] = []
    stats.setdefault("resumptions", []).append(now())
    for kind in ["result", "item"]:
        for year in stats["years"]:
            receipt = output / f"{kind}-{year}-scan.json"
            table = "tests" if kind == "result" else "items"
            parquet = output / f"{table}-{year}.parquet"
            if receipt.exists():
                completed = json.loads(receipt.read_text())
                with closing(sqlite3.connect(output / "sample.sqlite3")) as connection:
                    count = connection.execute(f"SELECT count(*) FROM {table} WHERE source_year=?", (year,)).fetchone()[0]
                parquet_count = pq.ParquetFile(parquet).metadata.num_rows if parquet.exists() else 0
                if count != completed["retained_rows"] or parquet_count != count:
                    raise ValueError("Completed stage counts differ; diagnose before resuming")
                if any(trusted.get(value["path"]) != value["sha256"] or checksum(ROOT / value["path"]) != value["sha256"]
                       for value in completed["provenance"]):
                    raise ValueError("Completed stage provenance differs")
            else:
                with closing(sqlite3.connect(output / "sample.sqlite3")) as connection:
                    connection.execute(f"DELETE FROM {table} WHERE source_year=?", (year,))
                    connection.commit()
                if parquet.exists():
                    failed = output / "failed"
                    failed.mkdir(exist_ok=True)
                    destination = failed / f"{parquet.stem}-{time.time_ns()}.parquet"
                    if not destination.resolve().is_relative_to(output.resolve()):
                        raise ValueError("Invalid failed artifact path")
                    parquet.replace(destination)
                subprocess.run([sys.executable, "-u", "-m", "pipeline.expansion", "stage", "--name", name,
                                "--kind", kind, "--year", str(year), "--modulus", str(stats["modulus"])], cwd=ROOT, check=True)
                completed = json.loads(receipt.read_text())
            stats["sources"].append(completed)
            save_json(output / "acquisition.json", stats)
    stats.update(status="complete", finished_at=now(), resources_end=resource_snapshot())
    save_json(output / "acquisition.json", stats)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["fetch", "gate", "ingest", "stage", "resume"])
    parser.add_argument("--months", nargs="+", type=int, default=[1])
    parser.add_argument("--name", default="expanded2022-2024")
    parser.add_argument("--modulus", type=int, default=1000)
    parser.add_argument("--kind", choices=["result", "item"])
    parser.add_argument("--year", type=int, choices=[2022, 2023, 2024])
    args = parser.parse_args()
    if not args.name.replace("-", "").isalnum() or args.modulus < 1000 or any(month not in range(1, 13) for month in args.months):
        raise ValueError("Invalid output name, sample bound or months")
    scratch = ROOT / "data/tmp"
    scratch.mkdir(exist_ok=True)
    os.environ.update(TEMP=str(scratch), TMP=str(scratch), SQLITE_TMPDIR=str(scratch))
    if args.command == "fetch":
        fetch(sorted(set(args.months)))
    elif args.command == "gate":
        gate()
    elif args.command == "ingest":
        ingest(args.name, args.modulus)
    elif args.command == "resume":
        resume(args.name)
    else:
        stats = json.loads((ROOT / "data/processed" / args.name / "acquisition.json").read_text())
        if stats["status"] != "incomplete" or stats["modulus"] != args.modulus or args.kind is None or args.year is None:
            raise ValueError("Stage requires matching incomplete acquisition")
        stage(args.name, args.kind, args.year, args.modulus)


if __name__ == "__main__":
    main()
