"""Pinned source discovery, cached acquisition, and bounded ZIP inspection."""

import argparse
import hashlib
import io
import json
import re
import shutil
import time
import zipfile64.zipfile as zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = "https://open.data.dvsa.gov.uk/mot-anonymised/index.html"
MANIFEST = ROOT / "docs/source_manifest.json"
TIMEOUT = 60
ATTEMPTS = 3
BLOCK = 1024 * 1024


def now():
    return datetime.now(timezone.utc).isoformat()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(BLOCK), b""):
            digest.update(block)
    return digest.hexdigest()


def request(url, method="GET", headers=None):
    for attempt in range(ATTEMPTS):
        try:
            return urlopen(Request(url, method=method, headers=headers or {}), timeout=TIMEOUT)
        except (OSError, HTTPError):
            if attempt == ATTEMPTS - 1:
                raise
            time.sleep(2 ** attempt)


class CatalogueParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.href = None
        self.label = ""
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.label = ""

    def handle_data(self, data):
        if self.href:
            self.label += data

    def handle_endtag(self, tag):
        if tag == "a" and self.href:
            if ".amazonaws.com/" in self.href or "open-government-licence" in self.href:
                self.links.append({"url": self.href, "label": self.label.strip()})
            self.href = None


def catalogue():
    with request(CATALOGUE) as response:
        body = response.read(2 * BLOCK)
        if response.read(1):
            raise ValueError("Catalogue exceeds bounded response size")
    parser = CatalogueParser()
    parser.feed(body.decode("utf-8"))
    if not parser.links:
        raise ValueError("No source links found; catalogue structure may have changed")
    return body, parser.links


def enrich_manifest(manifest):
    html = (ROOT / "data/sources/catalogue.html").read_text(encoding="utf-8")
    for record in manifest["sources"]:
        for row in re.findall(r"<tr\b.*?</tr>", html, re.DOTALL):
            if record["url"] in row:
                cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.DOTALL)
                record["catalogue_added_text"] = re.sub(r"<[^>]+>", "", cells[2]).strip()
                break
        year = re.search(r"202[2-5]", record["filename"])
        record["year"] = int(year.group()) if year else None
        if record["year"] in [2022, 2023]:
            record["selection"] = "selected pilot: original annual result/item pair"
        elif "extracts_202" in record["filename"]:
            record["selection"] = "selected expansion candidate: paired June 2026 releases; cross-year identifiers still require validation"
        elif record["year"] == 2024:
            record["selection"] = "older March 2025 alternative not selected; revision extent undocumented; do not mix with June 2026 pair"
            if record["status"] == "pending":
                record["status"] = "not_selected"
        elif "pre-May" in record["label"]:
            record["selection"] = "not needed: pre-May-2018 guide"
            if record["status"] == "pending":
                record["status"] = "not_selected"
        else:
            record["selection"] = "supporting source"
    return manifest


def discover():
    if MANIFEST.exists():
        raise ValueError("Pinned manifest exists; use check-sources, never overwrite automatically")
    body, links = catalogue()
    records = []
    for link in links:
        if "open-government-licence" in link["url"]:
            continue
        with request(link["url"], "HEAD") as response:
            headers = response.headers
            records.append({
                **link,
                "filename": unquote(urlsplit(link["url"]).path.rsplit("/", 1)[1]),
                "compressed_bytes": int(headers["Content-Length"]) if headers.get("Content-Length") else None,
                "etag": headers.get("ETag"),
                "last_modified": headers.get("Last-Modified"),
                "accept_ranges": headers.get("Accept-Ranges"),
                "observed_at": now(),
                "status": "pending",
                "sha256": None,
            })
    snapshot = ROOT / "data/sources/catalogue.html"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_bytes(body)
    save_json(MANIFEST, {
        "catalogue_url": CATALOGUE,
        "retrieved_at": now(),
        "catalogue_sha256": hashlib.sha256(body).hexdigest(),
        "catalogue_links": links,
        "sources": records,
    })
    print(f"Pinned {len(records)} sources; no annual archives downloaded")


def download(record, destination, max_bytes):
    size = record["compressed_bytes"]
    if size is None or size > max_bytes:
        raise ValueError("Unknown source size or explicit transfer bound exceeded")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if record.get("sha256") and destination.stat().st_size == size and checksum(destination) == record["sha256"]:
            return
        raise ValueError(f"Existing file has no matching trusted local checksum: {destination}")
    partial = destination.with_suffix(destination.suffix + ".part")
    metadata_path = partial.with_suffix(partial.suffix + ".json")
    validator = record.get("etag")
    resumable = record.get("accept_ranges") == "bytes" and validator and not validator.startswith("W/")
    expected_metadata = {"url": record["url"], "etag": validator, "size": size}
    for attempt in range(ATTEMPTS):
        try:
            with request(record["url"], "HEAD") as response:
                if response.headers.get("ETag") != validator or int(response.headers["Content-Length"]) != size:
                    raise ValueError("Source changed since pinning; review check-sources before acquiring")
            offset = 0
            if partial.exists():
                if resumable and metadata_path.exists() and json.loads(metadata_path.read_text()) == expected_metadata:
                    offset = partial.stat().st_size
                else:
                    partial.unlink()
            if offset > size:
                raise ValueError("Partial file exceeds pinned size")
            if shutil.disk_usage(destination.parent).free < size - offset + 5 * 1024 ** 3:
                raise ValueError("Insufficient disk: retain at least 5 GiB reserve")
            save_json(metadata_path, expected_metadata)
            if offset < size:
                headers = {"If-Match": validator} if validator else {}
                if offset:
                    headers.update({"Range": f"bytes={offset}-", "If-Range": validator})
                with request(record["url"], headers=headers) as response:
                    if response.headers.get("ETag") != validator:
                        raise ValueError("GET validator differs from pinned source")
                    if offset and (response.status != 206 or response.headers.get("Content-Range") != f"bytes {offset}-{size - 1}/{size}"):
                        raise ValueError("Server did not honor exact resume range; partial preserved")
                    with partial.open("ab" if offset else "wb") as stream:
                        received = offset
                        while block := response.read(BLOCK):
                            received += len(block)
                            if received > size:
                                raise ValueError("Response exceeds pinned size")
                            stream.write(block)
            if partial.stat().st_size != size:
                raise OSError("Incomplete transfer; partial retained for validated resume")
            digest = checksum(partial)
            if record.get("sha256") and digest != record["sha256"]:
                raise ValueError("Downloaded content differs from pinned SHA-256; partial preserved")
            partial.replace(destination)
            metadata_path.unlink(missing_ok=True)
            record.update(status="downloaded", sha256=digest, retrieved_at=now(), path=destination.relative_to(ROOT).as_posix())
            return
        except OSError:
            if attempt == ATTEMPTS - 1:
                raise
            time.sleep(2 ** attempt)


class RemoteZip(io.RawIOBase):
    def __init__(self, record):
        self.record = record
        self.size = record["compressed_bytes"]
        self.position = 0
        self.cache_start = -1
        self.cache = b""
        self.transferred = 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self.position = offset + (self.position if whence == 1 else self.size if whence == 2 else 0)
        if self.position < 0:
            raise ValueError("Negative seek")
        return self.position

    def read(self, size=-1):
        size = self.size - self.position if size < 0 else size
        size = min(size, self.size - self.position)
        if size > 16 * BLOCK:
            raise ValueError("Remote ZIP read exceeds 16 MiB bound")
        if size <= 0:
            return b""
        if not (self.cache_start <= self.position and self.position + size <= self.cache_start + len(self.cache)):
            start = self.position
            end = min(self.size - 1, start + max(size, BLOCK) - 1)
            with request(self.record["url"], headers={"Range": f"bytes={start}-{end}", "If-Match": self.record["etag"]}) as response:
                if response.status != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end}/{self.size}":
                    raise ValueError("Server does not support validated bounded ranges")
                if response.headers.get("ETag") != self.record["etag"]:
                    raise ValueError("Remote ZIP changed")
                self.cache = response.read(end - start + 2)
                if len(self.cache) != end - start + 1:
                    raise ValueError("Range response length mismatch")
            self.cache_start = start
            self.transferred += len(self.cache)
        result = self.cache[self.position - self.cache_start:self.position - self.cache_start + size]
        self.position += len(result)
        return result


def inspect_record(record):
    remote = RemoteZip(record)
    members = []
    with zipfile.ZipFile(remote) as archive:
        inspected = False
        for member in archive.infolist():
            info = {"name": member.filename, "compressed_bytes": member.compress_size,
                    "uncompressed_bytes": member.file_size, "crc32": f"{member.CRC:08x}",
                    "compression_method": member.compress_type}
            if member.filename.endswith(".csv") and not member.filename.startswith("__MACOSX/") and not inspected:
                with archive.open(member) as stream:
                    prefix = stream.read(8192).decode("utf-8-sig", errors="replace")
                lines = prefix.splitlines()
                info["first_line"] = lines[0] if lines else ""
                info["prefix_line_count"] = len(lines)
                inspected = True
            members.append(info)
    record["zip_members"] = members
    record["uncompressed_bytes"] = sum(member["uncompressed_bytes"] for member in members)
    record["range_inspection"] = {"retrieved_at": now(), "transferred_bytes": remote.transferred,
                                  "scope": "central directory; header prefixes only for members with first_line; not complete records or full archive checksum"}
    return members


def check_sources(manifest):
    body, links = catalogue()
    changes = []
    if links != manifest["catalogue_links"]:
        changes.append("catalogue links/labels changed")
    if hashlib.sha256(body).hexdigest() != manifest["catalogue_sha256"]:
        changes.append("catalogue HTML changed (may be cosmetic)")
    for record in manifest["sources"]:
        with request(record["url"], "HEAD") as response:
            if response.headers.get("ETag") != record["etag"] or response.headers.get("Content-Length") != str(record["compressed_bytes"]):
                changes.append(f"source changed: {record['filename']}")
    report = {"checked_at": now(), "changes": changes, "action": "Review manually; pinned files and manifest unchanged"}
    save_json(ROOT / "artifacts/reports/source_check.json", report)
    print(json.dumps(report))
    return bool(changes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["discover", "check-sources", "fetch", "inspect", "annotate"])
    parser.add_argument("--match", default="")
    parser.add_argument("--max-bytes", type=int, default=10 * BLOCK)
    args = parser.parse_args()
    if args.command == "discover":
        discover()
        return
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if args.command == "annotate":
        save_json(MANIFEST, enrich_manifest(manifest))
        return
    if args.command == "check-sources":
        raise SystemExit(2 if check_sources(manifest) else 0)
    records = [record for record in manifest["sources"] if re.search(args.match, record["filename"])]
    if not records:
        raise ValueError("No matching pinned sources")
    for record in records:
        if args.command == "fetch":
            destination = ROOT / "data" / ("raw" if record["filename"].endswith(".zip") and "lookup" not in record["filename"] else "sources") / record["filename"]
            download(record, destination, args.max_bytes)
            print(f"Verified cache: {record['filename']} ({record['compressed_bytes']} bytes)", flush=True)
        else:
            members = inspect_record(record)
            print(json.dumps({"file": record["filename"], "member_count": len(members), "uncompressed_bytes": record["uncompressed_bytes"], "headers": [member["first_line"] for member in members if "first_line" in member]}), flush=True)
        latest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for current in latest["sources"]:
            if current["url"] == record["url"]:
                current.update(record)
        save_json(MANIFEST, latest)


if __name__ == "__main__":
    main()
