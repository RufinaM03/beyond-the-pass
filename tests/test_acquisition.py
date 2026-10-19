"""Synthetic transport and cohort fixtures only; no evaluation metrics."""

import hashlib
import io
import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import zipfile64.zipfile as zipfile

from pipeline import sources
from pipeline import pilot
from pipeline.pilot import comparisons, vehicle_hash


class SyntheticHandler(BaseHTTPRequestHandler):
    payload = b"clearly synthetic transport fixture\n" * 100
    honor_range = True
    interrupt_once = False
    ranges = []

    def log_message(self, *args):
        pass

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Length", str(len(self.payload)))
        self.send_header("ETag", '"synthetic-v1"')
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

    def do_GET(self):
        requested = self.headers.get("Range")
        self.ranges.append(requested)
        offset = int(requested.split("=")[1].split("-")[0]) if requested and self.honor_range else 0
        self.send_response(206 if requested and self.honor_range else 200)
        self.send_header("ETag", '"synthetic-v1"')
        self.send_header("Content-Length", str(len(self.payload) - offset))
        if requested and self.honor_range:
            self.send_header("Content-Range", f"bytes {offset}-{len(self.payload)-1}/{len(self.payload)}")
        self.end_headers()
        if self.interrupt_once:
            type(self).interrupt_once = False
            self.wfile.write(self.payload[offset:offset + 100])
            self.close_connection = True
        else:
            self.wfile.write(self.payload[offset:])


class Downloads(unittest.TestCase):
    def setUp(self):
        (sources.ROOT / "data/tmp").mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=sources.ROOT / "data/tmp")
        self.root = Path(self.directory.name)
        SyntheticHandler.honor_range = True
        SyntheticHandler.interrupt_once = False
        SyntheticHandler.ranges = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), SyntheticHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.record = {"url": f"http://127.0.0.1:{self.server.server_port}/synthetic.zip",
                       "compressed_bytes": len(SyntheticHandler.payload), "etag": '"synthetic-v1"',
                       "accept_ranges": "bytes", "sha256": None}
        self.destination = self.root / "synthetic.zip"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.directory.cleanup()

    def partial(self):
        partial = self.destination.with_suffix(".zip.part")
        partial.write_bytes(SyntheticHandler.payload[:123])
        sources.save_json(partial.with_suffix(".part.json"), {
            "url": self.record["url"], "etag": self.record["etag"], "size": self.record["compressed_bytes"]})

    def test_resume_and_checksum_cache(self):
        self.partial()
        sources.download(self.record, self.destination, 10000)
        self.assertEqual(SyntheticHandler.ranges, ["bytes=123-"])
        self.assertEqual(self.record["sha256"], hashlib.sha256(SyntheticHandler.payload).hexdigest())
        sources.download(self.record, self.destination, 10000)
        self.assertEqual(len(SyntheticHandler.ranges), 1)
        self.destination.write_bytes(b"corrupted synthetic fixture")
        with self.assertRaisesRegex(ValueError, "checksum"):
            sources.download(self.record, self.destination, 10000)

    def test_reject_ignored_range_without_promoting_partial(self):
        self.partial()
        SyntheticHandler.honor_range = False
        with self.assertRaisesRegex(ValueError, "resume range"):
            sources.download(self.record, self.destination, 10000)
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.destination.with_suffix(".zip.part").stat().st_size, 123)

    def test_nonresumable_partial_restarts(self):
        self.partial()
        self.record["accept_ranges"] = None
        sources.download(self.record, self.destination, 10000)
        self.assertEqual(SyntheticHandler.ranges, [None])

    def test_interrupted_transfer_retries_with_validated_resume(self):
        SyntheticHandler.interrupt_once = True
        with patch.object(sources.time, "sleep"):
            sources.download(self.record, self.destination, 10000)
        self.assertEqual(SyntheticHandler.ranges, [None, "bytes=100-"])
        self.assertEqual(self.destination.read_bytes(), SyntheticHandler.payload)

    def test_bounds_and_changed_source(self):
        with self.assertRaisesRegex(ValueError, "bound exceeded"):
            sources.download(self.record, self.destination, 1)
        self.record["etag"] = '"stale"'
        with self.assertRaisesRegex(ValueError, "Source changed"):
            sources.download(self.record, self.destination, 10000)

    def test_reacquisition_must_match_pinned_sha256(self):
        self.record["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "pinned SHA-256"):
            sources.download(self.record, self.destination, 10000)
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.record["sha256"], "0" * 64)

    def test_check_sources_reports_change_without_replacing_manifest(self):
        manifest = {"catalogue_links": [], "catalogue_sha256": hashlib.sha256(b"original").hexdigest(),
                    "sources": [self.record]}
        before = json.dumps(manifest)
        with patch.object(sources, "catalogue", return_value=(b"changed", [])), patch.object(sources, "ROOT", self.root), patch("builtins.print"):
            self.assertTrue(sources.check_sources(manifest))
        self.assertEqual(json.dumps(manifest), before)
        self.assertTrue((self.root / "artifacts/reports/source_check.json").exists())


class SamplingAndLabels(unittest.TestCase):
    def test_hash_is_fixed_and_independent_of_chunk_order(self):
        self.assertEqual(vehicle_hash([0, 1, 2]).tolist(),
                         [16294208416658607535, 10451216379200822465, 10905525725756348110])
        identifiers = np.arange(200000, dtype=np.uint64)
        full = vehicle_hash(identifiers)
        chunked = np.concatenate([vehicle_hash(chunk) for chunk in np.array_split(identifiers, 7)])
        np.testing.assert_array_equal(full, chunked)
        np.testing.assert_array_equal(vehicle_hash(identifiers[::-1])[::-1], full)
        self.assertTrue(np.all((full[full % 100000 == 0] % 10000) == 0))

    def test_censoring_retests_mapping_and_completed_outcomes(self):
        tests = pd.DataFrame([
            [1, 10, "2022-03-01", "4", "NT", "P", 2022],
            [2, 10, "2022-03-02", "4", "PV", "P", 2022],
            [3, 10, "2023-03-01", "4", "NT", "F", 2023],
            [4, 20, "2023-01-01", "4", "NT", "P", 2023],
            [5, 30, "2022-02-01", "4", "NT", "P", 2022],
            [6, 30, "2023-02-01", "4", "NT", "P", 2023],
            [7, 40, "2022-02-01", "4", "NT", "P", 2022],
            [8, 40, "2023-02-01", "4", "NT", "ABR", 2023],
        ], columns=["test_id", "vehicle_id", "test_date", "test_class_id", "test_type", "test_result", "source_year"])
        items = pd.DataFrame([
            [1, "brakes", "A"], [3, "brakes", "F"], [4, "brakes", "A"],
            [5, "brakes", "A"], [6, "unknown", "A"], [7, "brakes", "A"],
        ], columns=["test_id", "family", "rfr_type_code"])
        results = {family: (summary, labels) for family, summary, labels in comparisons(tests, items)}
        summary, labels = results["brakes"]
        self.assertEqual(summary["eligible_advisory_tests"], 4)
        self.assertEqual(summary["no_next_test_censored"], 1)
        self.assertEqual(summary["unknown_mapping_in_pair"], 1)
        self.assertEqual(summary["next_incomplete_or_refused"], 1)
        self.assertEqual(labels.next_test_id.tolist(), [3])
        self.assertEqual(summary["positive_fail_or_prs"], 1)
        self.assertEqual(summary["chronological_2023_cut"]["training_labels_observed_before_2023"], 0)

    def test_itemless_pass_prs_and_class_changes_are_distinguished(self):
        tests = pd.DataFrame([
            [1, 10, "2022-03-01", "4", "NT", "P", 2022],
            [2, 10, "2023-03-01", "4", "NT", "P", 2023],
            [3, 20, "2022-03-01", "4", "NT", "P", 2022],
            [4, 20, "2023-03-01", "4", "NT", "PRS", 2023],
            [5, 30, "2022-03-01", "4", "NT", "P", 2022],
            [6, 30, "2023-03-01", "7", "NT", "F", 2023],
            [7, 30, "2023-04-01", "4", "NT", "P", 2023],
            [8, 40, "2022-03-01", "4", "NT", "P", 2022],
            [9, 40, "2023-03-01", "4", "NT", "F", 2023],
        ], columns=["test_id", "vehicle_id", "test_date", "test_class_id", "test_type", "test_result", "source_year"])
        items = pd.DataFrame([[1, "tyres", "A"], [3, "tyres", "A"], [4, "tyres", "P"],
                              [5, "tyres", "A"], [6, "tyres", "F"], [8, "tyres", "A"]],
                             columns=["test_id", "family", "rfr_type_code"])
        summary, labels = {family: (summary, labels) for family, summary, labels in comparisons(tests, items)}["tyres"]
        self.assertEqual(summary["usable_followups"], 2)
        self.assertEqual(summary["positive_fail_or_prs"], 1)
        self.assertEqual(summary["positive_fail_items_only"], 0)
        self.assertEqual(summary["next_test_class_change"], 1)
        self.assertEqual(summary["next_failure_without_items"], 1)
        self.assertEqual(labels.next_test_id.tolist(), [2, 4])

    def test_followup_ids_never_round_through_float(self):
        anchor_id = 2 ** 53 + 1
        followup_id = 2 ** 53 + 3
        tests = pd.DataFrame([
            [anchor_id, 10, "2022-03-01", "4", "NT", "P", 2022],
            [followup_id, 10, "2023-03-01", "4", "NT", "F", 2023],
        ], columns=["test_id", "vehicle_id", "test_date", "test_class_id", "test_type", "test_result", "source_year"])
        items = pd.DataFrame([[anchor_id, "brakes", "A"], [followup_id, "brakes", "F"]],
                             columns=["test_id", "family", "rfr_type_code"])
        summary, labels = {family: (summary, labels) for family, summary, labels in comparisons(tests, items)}["brakes"]
        self.assertEqual(summary["positive_fail_or_prs"], 1)
        self.assertEqual(labels.next_test_id.tolist(), [followup_id])

    def test_synthetic_archives_keep_full_selected_histories_and_join_items(self):
        identifiers = np.arange(200000, dtype=np.uint64)
        vehicle_id = int(identifiers[vehicle_hash(identifiers) % 100000 == 0][0])
        with tempfile.TemporaryDirectory(dir=sources.ROOT / "data/tmp") as directory:
            root = Path(directory)
            records = []
            for year in [2022, 2023]:
                result_rows = [[year * 10, vehicle_id, f"{year}-03-01", "4", "NT", "P" if year == 2022 else "F",
                                "10000", "XX", "SYNTHETIC", "FIXTURE", "BLACK", "PE", "1000", "2010-01-01"]]
                if year == 2023:
                    result_rows.append([20231, vehicle_id, "2023-03-02", "4", "PV", "P", "10000", "XX",
                                        "SYNTHETIC", "FIXTURE", "BLACK", "PE", "1000", "2010-01-01"])
                for kind, columns, rows in [
                    ("result", pilot.RESULT_COLUMNS, result_rows),
                    ("item", pilot.ITEM_COLUMNS, [[year * 10, "999", "A" if year == 2022 else "F", "0", "N"]]),
                ]:
                    if year == 2023 and kind == "item":
                        rows.append([20220, "998", "A", "0", "N"])
                    filename = f"dft_test_{kind}_{year}.zip"
                    path = root / filename
                    buffer = io.StringIO()
                    pd.DataFrame(rows, columns=columns).to_csv(buffer, sep="|", index=False)
                    with zipfile.ZipFile(path, "w", compression=9 if kind == "result" else 8) as archive:
                        archive.writestr(f"test_{kind}.csv", buffer.getvalue())
                    records.append({"filename": filename, "status": "downloaded", "path": filename,
                                    "sha256": sources.checksum(path)})
            manifest_path = root / "manifest.json"
            sources.save_json(manifest_path, {"sources": records})

            def run_synthetic_worker(arguments, **kwargs):
                kind = arguments[arguments.index("--kind") + 1]
                year = int(arguments[arguments.index("--years") + 1])
                pilot.scan_stages([year], 100000, 1, root / "data/processed/synthetic",
                                  {"sources": []}, {"sources": records}, kind)

            with patch.object(pilot, "ROOT", root), patch.object(pilot, "MANIFEST", manifest_path), patch("builtins.print"):
                with patch.object(pilot.subprocess, "run", side_effect=run_synthetic_worker) as workers:
                    output = pilot.ingest([2022, 2023], 100000, 1, "synthetic")
                self.assertEqual(workers.call_count, 4)
            acquisition = json.loads((output / "acquisition.json").read_text())
            self.assertEqual(acquisition["status"], "complete")
            self.assertEqual(sum(source["retained_rows"] for source in acquisition["sources"] if source["kind"] == "result"), 3)
            self.assertEqual(sum(source["retained_rows"] for source in acquisition["sources"] if source["kind"] == "item"), 3)
            self.assertEqual(len(pd.read_parquet(output / "tests-2023.parquet")), 2)
            acquisition["status"] = "incomplete"
            sources.save_json(output / "acquisition.json", acquisition)
            (output / "result-2023-scan.json").unlink()
            (output / "tests-2023.parquet").write_bytes(b"synthetic interrupted footer")
            with closing(sqlite3.connect(output / "sample.sqlite3")) as connection:
                connection.execute("DELETE FROM tests WHERE source_year=2023")
                connection.commit()
            with patch.object(pilot, "ROOT", root), patch.object(pilot, "MANIFEST", manifest_path), patch("builtins.print"):
                with patch.object(pilot.subprocess, "run", side_effect=run_synthetic_worker) as workers:
                    pilot.resume("synthetic")
                self.assertEqual(workers.call_count, 1)
                with self.assertRaisesRegex(ValueError, "Only incomplete"):
                    pilot.resume("synthetic")
            self.assertEqual(json.loads((output / "acquisition.json").read_text())["status"], "complete")
            self.assertEqual(len(pd.read_parquet(output / "tests-2023.parquet")), 2)
            self.assertEqual(len(list((output / "failed").glob("*.parquet"))), 1)


if __name__ == "__main__":
    unittest.main()
