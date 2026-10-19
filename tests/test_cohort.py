"""Clearly synthetic fixtures: annual labels, index-only history and CSV adapters."""

import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import closing

import pandas as pd
import numpy as np
import zipfile64.zipfile as zipfile

from pipeline import cohort, expansion
from pipeline.pilot import RESULT_COLUMNS


def test_record(identifier, date, outcome="P", kind="NT", vehicle=1, mileage="20000", **changes):
    record = dict(zip(RESULT_COLUMNS, [identifier, vehicle, date, "4", kind, outcome, mileage,
                                      "XX", "SYNTHETIC", "FIXTURE", "BLACK", "PE", "1000", "2010-01-01"]))
    return record | {"completed_date": "", "source_year": int(date[:4])} | changes


def item_record(identifier, code="A", family="brakes"):
    return {"test_id": identifier, "rfr_id": "999" if family == "brakes" else "998",
            "rfr_type_code": code, "location_id": "0", "dangerous_mark": "N", "family": family}


class AnnualCohort(unittest.TestCase):
    def build(self, tests, items):
        return cohort.construct(pd.DataFrame(tests), pd.DataFrame(items)).set_index("test_id")

    def test_retests_skipped_but_earlier_normal_never_skipped(self):
        result = self.build([test_record(1, "2022-01-31"), test_record(2, "2022-02-01", kind="RT"),
                             test_record(3, "2022-08-31"), test_record(4, "2023-01-31", "F")],
                            [item_record(1), item_record(4, "F")])
        self.assertEqual(result.loc[1, "next_test_id"], 3)
        self.assertIn("next_outside_9_15_months", result.loc[1, "all_reasons"])
        self.assertTrue(pd.isna(result.loc[1, "label"]))

    def test_calendar_boundary_and_different_component_failure(self):
        result = self.build([test_record(1, "2022-01-31"), test_record(2, "2022-10-31", "F")],
                            [item_record(1), item_record(2, "F", "tyres")])
        self.assertEqual(result.loc[1, "label"], 0)
        outside = self.build([test_record(1, "2022-01-31"), test_record(2, "2022-10-30")], [item_record(1)])
        self.assertIn("next_outside_9_15_months", outside.loc[1, "all_reasons"])

    def test_rectification_positive_and_prs_not_anchor(self):
        result = self.build([test_record(1, "2022-01-31"), test_record(2, "2023-01-31", "PRS")],
                            [item_record(1), item_record(2, "P"), item_record(2)])
        self.assertEqual(result.loc[1, "label"], 1)
        self.assertEqual(result.loc[1, "rectified_brake_failure"], 1)
        self.assertNotIn(2, result.index)

    def test_missing_and_itemless_pass(self):
        missing = self.build([test_record(1, "2023-07-01")], [item_record(1)])
        self.assertEqual(missing.loc[1, "reason"], "missing_followup")
        self.assertTrue(pd.isna(missing.loc[1, "label"]))
        negative = self.build([test_record(1, "2022-01-01"), test_record(2, "2023-01-01")], [item_record(1)])
        self.assertEqual(negative.loc[1, "label"], 0)

    def test_conflicts_unknown_and_same_day_excluded(self):
        for outcome, records in [("F", []), ("PRS", []), ("P", [item_record(2, "F")]),
                                  ("P", [item_record(2, family="unknown")])]:
            with self.subTest(outcome=outcome, records=records):
                result = self.build([test_record(1, "2022-01-01"), test_record(2, "2023-01-01", outcome)],
                                    [item_record(1)] + records)
                self.assertTrue(pd.isna(result.loc[1, "label"]))
        duplicate = pd.DataFrame([test_record(1, "2022-01-01"), test_record(1, "2022-01-02")])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            cohort.construct(duplicate, pd.DataFrame([item_record(1)]))
        same_day = self.build([test_record(1, "2022-01-01"), test_record(2, "2022-01-01"),
                               test_record(3, "2023-01-01")], [item_record(1)])
        self.assertEqual(same_day.loc[1, "reason"], "ambiguous_same_day")

    def test_recurrence_uses_recorded_past_not_future(self):
        tests = [test_record(1, "2022-02-01", mileage="10000"), test_record(2, "2023-02-01"),
                 test_record(3, "2024-02-01", "F", mileage="30000")]
        items = [item_record(1), item_record(2), item_record(3, "F")]
        before = self.build(tests, items)
        self.assertEqual(before.loc[1, "prior_brake_advisory_tests"], 0)
        self.assertEqual(before.loc[2, "prior_brake_advisory_tests"], 1)
        self.assertEqual(before.loc[2, "brake_advisory_recurrence"], 1)
        self.assertEqual(before.loc[2, "mileage_delta"], 10000)
        tests[2] = test_record(3, "2024-02-01", "P", mileage="999999", first_use_date="2024-01-01")
        after = self.build(tests, items[:-1])
        pd.testing.assert_series_equal(before.loc[2, cohort.FEATURES], after.loc[2, cohort.FEATURES])

    def test_mileage_rollback_not_valid_delta(self):
        result = self.build([test_record(1, "2022-01-01", mileage="30000"),
                             test_record(2, "2023-01-01", mileage="20000"), test_record(3, "2024-01-01")],
                            [item_record(2)])
        self.assertEqual(result.loc[2, "mileage_rollback"], 1)
        self.assertTrue(pd.isna(result.loc[2, "mileage_delta"]))
        self.assertNotIn("test_id", cohort.FEATURES)
        self.assertNotIn("postcode_area", cohort.FEATURES)

    def test_large_ids_and_late_item_completion(self):
        identifier = 2 ** 53 + 3
        tests = [test_record(1, "2022-01-01"), test_record(identifier, "2023-01-01", "F")]
        items = [item_record(1), item_record(identifier, "F") | {"completed_date": "2023-07-02T00:00:00Z"}]
        result = self.build(tests, items)
        self.assertEqual(result.loc[1, "next_test_id"], identifier)
        self.assertEqual(result.loc[1, "label_available_at"], "2023-07-02T00:00:00+00:00")
        self.assertEqual(result.loc[1, "vehicle_role"], "train")
        self.assertEqual(result.loc[1, "partition_window"], "train")
        self.assertNotEqual(result.loc[1, "partition"], "train")

    def test_prior_same_day_conflicting_mileage_is_not_a_reading(self):
        result = self.build([test_record(1, "2022-01-01", mileage="10000"),
                             test_record(2, "2022-01-01", kind="RT", mileage="9000"),
                             test_record(3, "2023-01-01"), test_record(4, "2024-01-01")], [item_record(3)])
        self.assertEqual(result.loc[3, "prior_mileage_available"], 0)
        self.assertTrue(pd.isna(result.loc[3, "mileage_delta"]))

    def test_late_historical_item_not_a_recurrence_feature(self):
        tests = [test_record(1, "2022-01-01"), test_record(2, "2023-01-01"), test_record(3, "2024-01-01")]
        items = [item_record(1) | {"completed_date": "2023-06-01T12:00:00Z"}, item_record(2)]
        result = self.build(tests, items)
        self.assertEqual(result.loc[2, "prior_brake_advisory_tests"], 0)

    def test_duplicate_item_completion_does_not_hide_late_label(self):
        tests = [test_record(1, "2022-01-01"), test_record(2, "2023-01-01", "F")]
        items = [item_record(1), item_record(2, "F"),
                 item_record(2, "F") | {"completed_date": "2023-07-02T12:00:00Z"}]
        result = self.build(tests, items)
        self.assertEqual(result.loc[1, "label_available_at"], "2023-07-02T12:00:00+00:00")
        self.assertEqual(result.loc[1, "partition"], "unused")

    def test_next_class_change_and_incomplete_not_skipped(self):
        for changed in [{"test_class_id": "7"}, {"test_result": "ABR"}]:
            result = self.build([test_record(1, "2022-01-01"), test_record(2, "2023-01-01", **changed),
                                 test_record(3, "2023-02-01", "F")], [item_record(1), item_record(3, "F")])
            self.assertEqual(result.loc[1, "next_test_id"], 2)
            self.assertTrue(pd.isna(result.loc[1, "label"]))


class NewCSVAdapter(unittest.TestCase):
    def test_item_chunk_parser_rejects_extra_fields_and_blank_records(self):
        directory = expansion.ROOT / "data/tmp"
        with tempfile.TemporaryDirectory(dir=directory) as temporary:
            path = Path(temporary) / "synthetic.csv"
            header = ",".join(expansion.CSV_ITEMS) + "\n"
            row = "1,999,A,0,N,2024-01-31T12:00:00Z\n"
            with patch.object(expansion, "member_path", return_value=path):
                path.write_text(header + row, encoding="utf-8")
                self.assertEqual(list(expansion.modern_chunks("item", 1))[0].location_id.tolist(), ["0"])
                path.write_text(header + row.rstrip() + ",extra\n", encoding="utf-8")
                with self.assertRaises((pd.errors.ParserWarning, pd.errors.ParserError)):
                    list(expansion.modern_chunks("item", 1))
                path.write_text(header + row + "\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "Missing completion"):
                    list(expansion.modern_chunks("item", 1))

    def test_bounded_sorted_join_matches_membership_with_large_ids(self):
        identifiers = np.array([0, 20, 10, 2 ** 53 + 3, 99], dtype="int64")
        index = np.array([10, 20, 2 ** 53 + 3], dtype="int64")
        np.testing.assert_array_equal(expansion.joined_test_mask(identifiers, index), np.isin(identifiers, index))
        np.testing.assert_array_equal(expansion.joined_test_mask(identifiers, np.array([], dtype="int64")), np.zeros(5, dtype=bool))

    def test_expansion_resume_preserves_completed_stage(self):
        directory = expansion.ROOT / "data/tmp"
        with tempfile.TemporaryDirectory(dir=directory) as temporary:
            root = Path(temporary)
            output = root / "data/processed/synthetic"
            output.mkdir(parents=True)
            source = root / "synthetic.txt"
            source.write_text("clearly synthetic source", encoding="utf-8")
            source_hash = expansion.checksum(source)
            manifest = root / "manifest.json"
            members = root / "members.json"
            expansion.save_json(manifest, {"sources": [{"path": "synthetic.txt", "sha256": source_hash}]})
            expansion.save_json(members, {"members": []})
            expansion.save_json(output / "acquisition.json", {"status": "incomplete", "years": [2022], "modulus": 1000})
            with closing(sqlite3.connect(output / "sample.sqlite3")) as connection:
                connection.execute("CREATE TABLE tests(test_id INTEGER,source_year INTEGER)")
                connection.execute("INSERT INTO tests VALUES(1,2022)")
                connection.execute("CREATE TABLE items(test_id INTEGER,source_year INTEGER)")
                connection.execute("INSERT INTO items VALUES(999,2022)")
                connection.commit()
            pd.DataFrame({"test_id": [1]}).to_parquet(output / "tests-2022.parquet")
            completed = {"retained_rows": 1, "provenance": [{"path": "synthetic.txt", "sha256": source_hash}]}
            expansion.save_json(output / "result-2022-scan.json", completed)
            (output / "items-2022.parquet").write_bytes(b"synthetic partial parquet")

            def synthetic_worker(arguments, **kwargs):
                with closing(sqlite3.connect(output / "sample.sqlite3")) as connection:
                    self.assertEqual(connection.execute("SELECT count(*) FROM items").fetchone()[0], 0)
                expansion.save_json(output / "item-2022-scan.json", {"retained_rows": 0, "provenance": completed["provenance"]})

            with patch.object(expansion, "ROOT", root), patch.object(expansion, "MANIFEST", manifest), patch.object(expansion, "MEMBERS", members):
                with patch.object(expansion.subprocess, "run", side_effect=synthetic_worker) as workers:
                    expansion.resume("synthetic")
                    self.assertEqual(workers.call_count, 1)
                self.assertEqual(json.loads((output / "acquisition.json").read_text())["status"], "complete")
                self.assertEqual(len(list((output / "failed").glob("*.parquet"))), 1)
                with self.assertRaisesRegex(ValueError, "Only incomplete"):
                    expansion.resume("synthetic")

    def test_member_range_crc_cache_and_corruption(self):
        directory = expansion.ROOT / "data/tmp"
        with tempfile.TemporaryDirectory(dir=directory) as temporary:
            root = Path(temporary)
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", compression=0) as archive:
                archive.writestr("synthetic_result_202401.csv", "clearly synthetic member\n")
            payload = buffer.getvalue()
            remote = io.BytesIO(payload)
            remote.size = len(payload)
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                member = archive.infolist()[0]
            record = {"url": "https://synthetic.invalid/fixture.zip", "filename": "synthetic_result.zip",
                      "etag": '"synthetic"', "compressed_bytes": len(payload)}

            def response(url, headers):
                start, end = map(int, headers["Range"].split("=")[1].split("-"))
                stream = io.BytesIO(payload[start:end + 1])
                stream.status = 206
                stream.headers = {"Content-Range": f"bytes {start}-{end}/{len(payload)}", "ETag": '"synthetic"'}
                return stream

            with patch.object(expansion, "ROOT", root), patch.object(expansion, "request", side_effect=response) as transport:
                pinned = {"members": []}
                value = expansion.download_member(record, member, remote, pinned)
                pinned["members"].append(value)
                expansion.download_member(record, member, remote, pinned)
                self.assertEqual(transport.call_count, 1)
                self.assertEqual((root / value["path"]).read_bytes(), b"clearly synthetic member\n")
                (root / value["path"]).unlink()
                member.CRC ^= 1
                with self.assertRaisesRegex(ValueError, "CRC"):
                    expansion.download_member(record, member, remote, {"members": []})
                self.assertFalse((root / value["path"]).exists())

    def test_literal_unbalanced_quote_and_quoted_comma_no_skipped_rows(self):
        directory = expansion.ROOT / "data/tmp"
        with tempfile.TemporaryDirectory(dir=directory) as temporary:
            path = Path(temporary) / "synthetic.csv"
            path.write_text('first,second,third\n1,"literal,3\n2,"quoted, comma",4\n', encoding="utf-8")
            from collections import Counter
            diagnostics = Counter()
            self.assertEqual(list(expansion.csv_records(path, ["first", "second", "third"], diagnostics)),
                             [["1", '"literal', "3"], ["2", "quoted, comma", "4"]])
            self.assertEqual(diagnostics["literal_quote_records"], 1)
            path.write_text('first,second,third\n1,ambiguous,extra,3\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Ambiguous CSV"):
                list(expansion.csv_records(path, ["first", "second", "third"]))

    def test_header_completion_and_month_validation(self):
        directory = expansion.ROOT / "data/tmp"
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=directory) as temporary:
            path = Path(temporary) / "synthetic.csv"
            frame = pd.DataFrame([test_record(1, "2024-01-31", completed_date="2024-01-31T12:00:00Z")])[expansion.CSV_RESULTS]
            frame.to_csv(path, index=False)
            with patch.object(expansion, "member_path", return_value=path):
                self.assertEqual(len(list(expansion.modern_chunks("result", 1))[0]), 1)
                with self.assertRaisesRegex(ValueError, "outside"):
                    list(expansion.modern_chunks("result", 2))
                frame.completed_date = "2024-01-30T12:00:00Z"
                frame.to_csv(path, index=False)
                with self.assertRaisesRegex(ValueError, "precedes"):
                    list(expansion.modern_chunks("result", 1))
                frame.drop(columns="completed_date").to_csv(path, index=False)
                with self.assertRaisesRegex(ValueError, "header"):
                    list(expansion.modern_chunks("result", 1))


if __name__ == "__main__":
    unittest.main()
