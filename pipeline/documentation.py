"""Verify cached documentation and compare published lookup generations."""

import csv
import hashlib
import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import zipfile64.zipfile as zipfile

from pipeline.sources import MANIFEST, ROOT, checksum, now, request, save_json


def verify_documentation():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    needed = [record for record in manifest["sources"] if record["filename"] in [
        "lookup.zip", "mot-testing-data-user-guide-v5.1.odt", "dft_item_detail_extract.csv"]]
    for record in needed:
        if record["status"] != "downloaded" or checksum(ROOT / record["path"]) != record["sha256"]:
            raise ValueError("Documentation checksum missing or invalid")
    guide = ROOT / "data/sources/mot-testing-data-user-guide-v5.1.odt"
    with zipfile.ZipFile(guide) as archive:
        if archive.getinfo("content.xml").file_size > 5 * 1024 ** 2:
            raise ValueError("Guide XML exceeds bounded size")
        tree = ET.fromstring(archive.read("content.xml"))
    paragraphs = tree.findall(".//{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p")
    (ROOT / "data/sources/user-guide.txt").write_text("\n".join("".join(paragraph.itertext()) for paragraph in paragraphs), encoding="utf-8")
    licence_url = "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
    licence_manifest = ROOT / "docs/licence_manifest.json"
    licence_path = ROOT / "data/sources/ogl-v3.html"
    if licence_manifest.exists():
        pinned = json.loads(licence_manifest.read_text())
        if not licence_path.exists():
            with request(pinned["url"], headers={"User-Agent": "Mozilla/5.0"}) as response:
                body = response.read(1024 ** 2 + 1)
            if len(body) > 1024 ** 2 or hashlib.sha256(body).hexdigest() != pinned["sha256"]:
                raise ValueError("Licence retrieval differs from pinned content; review before replacement")
            licence_path.write_bytes(body)
            pinned["cache_retrieved_at"] = now()
        elif checksum(licence_path) != pinned["sha256"]:
            raise ValueError("Pinned licence cache changed; review before replacement")
    else:
        with request(licence_url, headers={"User-Agent": "Mozilla/5.0"}) as response:
            body = response.read(1024 ** 2 + 1)
        if len(body) > 1024 ** 2:
            raise ValueError("Licence exceeds 1 MiB bound")
        licence_path.write_bytes(body)
        pinned = {"url": licence_url, "retrieved_at": now(), "sha256": hashlib.sha256(body).hexdigest(),
                  "path": licence_path.relative_to(ROOT).as_posix(), "status": "downloaded"}
    pinned["bytes"] = licence_path.stat().st_size
    pinned["path"] = licence_path.relative_to(ROOT).as_posix()
    save_json(licence_manifest, pinned)
    with zipfile.ZipFile(ROOT / "data/sources/lookup.zip") as archive:
        with archive.open("item_detail.csv") as stream:
            old_rows = list(csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig"), delimiter="|"))
    with (ROOT / "data/sources/dft_item_detail_extract.csv").open(encoding="utf-8-sig", newline="") as stream:
        new_rows = list(csv.DictReader(stream))
    old = {(row["rfr_id"], row["test_class_id"]): row for row in old_rows}
    new = {(row["rfr_id"], row["test_class_id"]): row for row in new_rows}
    if len(old) != len(old_rows) or len(new) != len(new_rows):
        raise ValueError("Duplicate dictionary keys")
    shared = old.keys() & new.keys()
    report = {"generated_at": now(), "old_rows": len(old), "new_rows": len(new),
              "old_category_values": sorted({row["rfr_deficiency_category"] for row in old_rows}),
              "shared_keys": len(shared), "new_only_keys": len(new.keys() - old.keys()),
              "old_only_keys": len(old.keys() - new.keys()),
              "changed_shared_fields": {field: sum(old[key][field] != new[key][field] for key in shared)
                                        for field in ["test_item_id", "test_item_set_section_id", "rfr_deficiency_category"]}}
    save_json(ROOT / "artifacts/reports/dictionary-comparison.json", report)
    print(json.dumps(report))


if __name__ == "__main__":
    verify_documentation()
