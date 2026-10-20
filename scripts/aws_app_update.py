"""Pinned application-only update; no S3 writes, IAM changes or hosting extension."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from scripts import aws_release as operations


ROOT = operations.ROOT
CONTEXT = ROOT / "data/package/manual-local-v2"
PLAN = ROOT / "docs/MANUAL_DEPLOYMENT_PLAN.md"
RECORD = ROOT / "data/tmp/manual-app-update.json"
IMAGE = "beyond-the-pass:manual-local-v2"
IMAGE_ID = "sha256:dc6e5fa4d40ec2364c9503dd491d29d4512c21cfd6fa221a105b3bb0ca4f3888"
SOURCE = "1552c00ab006d1112642039a2960e2ea4a3dbc53e0914c0392cdf3a331afa292"
CODE = "working-tree-" + SOURCE
MANIFEST = "56846f43cfc8e23f809d16b27d85b144a8d634f8fa42870d2e6f59df7531fa14"
DEADLINE = datetime(2026, 10, 21, 6, 12, 53, tzinfo=timezone.utc)
BASE = "https://d1qxms20novn1p.cloudfront.net"


def require_update_approval(approved, now=None):
    if approved != hashlib.sha256(PLAN.read_bytes()).hexdigest():
        raise ValueError("Explicit human approval of the bounded update plan and its SHA256 required")
    if (now or datetime.now(timezone.utc)) >= DEADLINE:
        raise ValueError("Original hosting deadline reached; no publication/update or duration extension authorized")


def parameter_update(parameters, image, code):
    changes = {"ImageUri": image, "CodeVersion": code}
    keys = [entry["ParameterKey"] for entry in parameters]
    if len(keys) != len(set(keys)) or not set(changes) <= set(keys):
        raise ValueError("Unexpected deployed parameter schema")
    return [{"ParameterKey": key, "ParameterValue": changes[key]} if key in changes else
            {"ParameterKey": key, "UsePreviousValue": True} for key in keys]


def validate_changes(changes):
    expected = {"Task": ("AWS::ECS::TaskDefinition", "True"), "Service": ("AWS::ECS::Service", "False")}
    if len(changes) != 2:
        raise ValueError("Stop: change set exceeds the approved two-resource scope")
    for entry in changes:
        resource = entry.get("ResourceChange", {})
        name = resource.get("LogicalResourceId")
        if (name not in expected or resource.get("Action") != "Modify" or
                (resource.get("ResourceType"), resource.get("Replacement")) != expected.pop(name)):
            raise ValueError("Stop: unexpected resource mutation/replacement")
    if expected:
        raise ValueError("Missing approved resource changes")


def preflight(approved):
    require_update_approval(approved)
    operations.identity()
    if operations.run(["git", "status", "--porcelain"]):
        raise ValueError("Commit all reviewed changes before deployment; working tree must be clean")
    ci = operations.verified_deployment_commit()
    from scripts.package_release import validate_context
    resource = validate_context(CONTEXT, "release", code_version=CODE, artifact_version=operations.EXPECTED_ARTIFACT)
    package = json.loads((CONTEXT / "package-manifest.json").read_text())
    if package["source_digest"] != SOURCE or resource.descriptor["release_manifest_sha256"] != MANIFEST:
        raise ValueError("Unexpected source/artifact identity")
    tracked = set(operations.run(["git", "ls-files"]).splitlines())
    for name, expected in package["files"].items():
        if name.startswith(("release/", "tools/")):
            continue
        if name not in tracked or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected["sha256"]:
            raise ValueError("Committed source differs from verified staged image")
    report = json.loads((ROOT / "artifacts/reports/manual-container-check-v2.json").read_text())
    browser = json.loads((ROOT / "artifacts/manual-browser/docker-v2/checks.json").read_text())
    if (report["image_id"] != IMAGE_ID or report["versions"]["code_version"] != CODE or
            report["verified_http_predictions"] != 200 or not report["verification_container_stopped"] or
            len(browser["checks"]) != 8 or browser["page_errors"]):
        raise ValueError("Final real Docker/browser acceptance missing")
    local = json.loads(operations.run(["docker", "image", "inspect", IMAGE]))[0]
    if (local["Id"] != IMAGE_ID or local["Architecture"] != "amd64" or local["Os"] != "linux" or
            local["Config"]["Labels"]["org.opencontainers.image.revision"] != CODE or
            local["Config"]["Labels"]["io.btp.artifact.kind"] != "release"):
        raise ValueError("Local image differs from accepted release")
    return ci


def publish(approved):
    from pipeline.pilot import resource_snapshot

    capacity = resource_snapshot()
    if min(capacity.get("available_ram_bytes", 0), capacity.get("available_commit_bytes", 0)) < 2 * 1024 ** 3:
        raise ValueError("Publication paused: require 2 GiB available RAM and Windows commit headroom")
    ci = preflight(approved)
    if RECORD.exists():
        raise ValueError("Preserve existing update record; do not blindly republish")
    storage = operations.outputs(operations.BOOTSTRAP)
    registry = storage["RepositoryUri"].split("/")[0]
    password = operations.aws("ecr", "get-login-password")
    operations.run(["docker", "login", "--username", "AWS", "--password-stdin", registry], input_text=password)
    try:
        tag = storage["RepositoryUri"] + ":manual-" + ci["deployment_commit"]
        operations.run(["docker", "tag", IMAGE_ID, tag])
        operations.run(["docker", "push", tag])
        details = json.loads(operations.aws("ecr", "describe-images", "--repository-name", "btp-demo-app",
                             "--image-ids", "imageTag=manual-" + ci["deployment_commit"], "--output", "json"))["imageDetails"][0]
        digest = details["imageDigest"]
        if digest != IMAGE_ID:
            raise ValueError("ECR digest differs from verified local manifest")
        image = storage["RepositoryUri"] + "@" + digest
        manifest = json.loads(operations.run(["docker", "buildx", "imagetools", "inspect", image, "--raw"]))
        children = [entry["digest"] for entry in manifest.get("manifests", [])
                    if entry.get("platform", {}).get("architecture") == "amd64" and entry.get("platform", {}).get("os") == "linux"]
        if len(children) != 1:
            raise ValueError("Expected exactly one Linux amd64 child")
        operations.save(RECORD, {**ci, "image_uri": image, "platform_digests": children, "code_version": CODE,
                        "source_digest": SOURCE, "manifest_sha256": MANIFEST, "artifact_version": operations.EXPECTED_ARTIFACT,
                        "local_image_id": IMAGE_ID, "ecr_size_bytes": details["imageSizeInBytes"],
                        "approved_plan_sha256": approved, "teardown_utc": DEADLINE.isoformat(),
                        "s3_writes": False, "artifact_provenance": "Original aws-published.json; unchanged bundle only"})
    finally:
        operations.run(["docker", "logout", registry])
    print("Pinned image published; no S3 writes. Record: data/tmp/manual-app-update.json")


def load_record(approved):
    ci = preflight(approved)
    record = json.loads(RECORD.read_text())
    if any(record[key] != value for key, value in {**ci, "approved_plan_sha256": approved, "code_version": CODE,
           "source_digest": SOURCE, "local_image_id": IMAGE_ID, "manifest_sha256": MANIFEST}.items()):
        raise ValueError("Update record differs from approved source/commit/plan")
    expected = f"{operations.ACCOUNT}.dkr.ecr.{operations.REGION}.amazonaws.com/btp-demo-app@{IMAGE_ID}"
    if record["image_uri"] != expected:
        raise ValueError("Unexpected image repository/digest")
    return record


def changeset(approved):
    record = load_record(approved)
    if "change_set" in record:
        raise ValueError("Change set already recorded; inspect it rather than blindly retry")
    stack = json.loads(operations.aws("cloudformation", "describe-stacks", "--stack-name", operations.APP))["Stacks"][0]
    if stack["StackStatus"] not in {"CREATE_COMPLETE", "UPDATE_COMPLETE"}:
        raise ValueError("Existing stack not ready for bounded update")
    parameters = parameter_update(stack["Parameters"], record["image_uri"], record["deployment_commit"])
    path = ROOT / "data/tmp/manual-update-parameters.json"
    operations.save(path, parameters)
    name = "manual-" + record["deployment_commit"][:16]
    operations.aws("cloudformation", "create-change-set", "--stack-name", operations.APP, "--change-set-name", name,
                   "--change-set-type", "UPDATE", "--use-previous-template", "--parameters", "file://" + str(path),
                   "--capabilities", "CAPABILITY_NAMED_IAM")
    record["change_set"] = name
    operations.save(RECORD, record)
    operations.aws("cloudformation", "wait", "change-set-create-complete", "--stack-name", operations.APP, "--change-set-name", name)
    response = json.loads(operations.aws("cloudformation", "describe-change-set", "--stack-name", operations.APP, "--change-set-name", name))
    validate_changes(response["Changes"])
    record["reviewed_changes"] = [{key: entry["ResourceChange"].get(key) for key in
                                  ["LogicalResourceId", "ResourceType", "Action", "Replacement"]} for entry in response["Changes"]]
    operations.save(RECORD, record)
    print(json.dumps({"approved_resource_changes": record["reviewed_changes"]}))


def execute(approved):
    record = load_record(approved)
    response = json.loads(operations.aws("cloudformation", "describe-change-set", "--stack-name", operations.APP,
                                       "--change-set-name", record["change_set"]))
    validate_changes(response["Changes"])
    if response["ExecutionStatus"] != "AVAILABLE":
        raise ValueError("Change set not available; inspect current stack instead of repeating execution")
    operations.aws("cloudformation", "execute-change-set", "--stack-name", operations.APP, "--change-set-name", record["change_set"])
    operations.aws("cloudformation", "wait", "stack-update-complete", "--stack-name", operations.APP)
    operations.verify_service(record)
    print("Existing service updated; run HTTPS acceptance. Original teardown deadline unchanged.")


def http(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    try:
        with urlopen(Request(BASE + path, data=data, headers=headers), timeout=30) as response:
            return response.status, response.headers, response.read()
    except HTTPError as error:
        return error.code, error.headers, error.read()


def verify():
    from contextlib import closing
    from backend.app import predictions_agree
    from scripts.package_release import validate_context

    operations.identity()
    record = json.loads(RECORD.read_text())
    operations.verify_service(record)
    resource = validate_context(CONTEXT, "release", code_version=CODE)
    status, headers, body = http("/api/versions")
    versions = json.loads(body)
    assert status == 200 and versions["code_version"] == CODE and versions["manifest_sha256"] == MANIFEST
    assert versions["demo_cases"] == 200 and versions["evaluation_examples"] == 936 and not versions["fixture"]
    assert http("/api/ready")[0] == 200
    before = json.loads(http("/api/evaluation")[2])
    assert before == resource.metrics
    with closing(resource.connect()) as connection:
        rows = connection.execute("SELECT case_id,inputs_json,prediction_json FROM followup_queue ORDER BY case_id").fetchall()
    for case_id, inputs, stored in rows:
        status, headers, body = http("/api/cases/" + case_id + "/prediction")
        assert status == 200 and predictions_agree(json.loads(body), json.loads(stored))
    inputs = json.loads(rows[0][1])
    payload = {"eligibility_confirmed": True, "features": inputs["features"], "inspection_date": "2023-05-31"}
    status, headers, body = http("/api/predict/manual", payload)
    manual = json.loads(body)
    assert status == 200 and headers.get("Cache-Control") == "no-store" and headers.get("X-Cache") != "Hit from cloudfront"
    assert predictions_agree(manual["prediction"], json.loads(rows[0][2]))
    assert manual["nominal_followup_window"] == {"start": "2024-02-29", "end": "2024-08-31"}
    assert not manual["stored"] and not manual["ranked_against_historical_queue"]
    for value in (False, 1):
        assert http("/api/predict/manual", {**payload, "eligibility_confirmed": value})[0] == 422
    assert http("/api/predict/manual", {**payload, "name": "illustrative-not-personal"})[0] == 422
    queue = json.loads(http("/api/queue?capacity=500&limit=100")[2])
    second = json.loads(http("/api/queue?capacity=500&limit=100&offset=100")[2])
    ranked = queue["items"] + second["items"]
    assert queue["selected"] == 200 and queue["exceeds_available"] and len(ranked) == 200
    assert ranked == sorted(ranked, key=lambda row: (-row["exploratory_prioritization_score"], row["case_id"]))
    assert http("/api/queue?capacity=501")[0] == 422 and http("/api/cases/not-a-case")[0] == 404
    assert http("/api/no-such-endpoint")[0] == 404 and http("/assets/no-such.js")[0] == 404
    assert json.loads(http("/api/evaluation")[2]) == before
    for path in ["/predict", "/queue", "/evaluation"]:
        assert http(path)[0] == 200
    result = {"checked_at": datetime.now(timezone.utc).isoformat(), "endpoint": BASE, "versions": versions,
              "historical_prediction_agreements": len(rows), "manual_post_agreement": True,
              "evaluation_unchanged": True, "deterministic_queue": True, "no_store": True,
              "teardown_utc": DEADLINE.isoformat(), "fixture": False}
    operations.save(ROOT / "artifacts/reports/manual-aws-checks.json", result)
    print(json.dumps(result))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["publish", "changeset", "execute", "verify"])
    parser.add_argument("--approved-plan-sha256")
    args = parser.parse_args()
    if args.action == "verify":
        verify()
    else:
        globals()[args.action](args.approved_plan_sha256)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as error:
        raise SystemExit(str(error)) from None
