"""Existing-stack image releases; no S3 writes, provisioning, IAM mutation or teardown."""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from scripts.aws_app_update import parameter_update, validate_changes


ROOT = Path(__file__).resolve().parents[1]
ACCOUNT = "044854093109"
REGION = "ap-south-1"
STACK = "btp-demo-app"
REPO = "RufinaM03/beyond-the-pass"
REGISTRY = ACCOUNT + ".dkr.ecr." + REGION + ".amazonaws.com"
REPOSITORY = REGISTRY + "/btp-demo-app"
BASE = "https://d1qxms20novn1p.cloudfront.net"
ARTIFACTS = json.loads((ROOT / "docs/cd-artifacts.json").read_text())


def safe_aws_error(stderr):
    return {
        "actions": sorted(set(re.findall(r"(?<![:\w])(?:cloudformation|ecs|ecr|iam|s3|elasticloadbalancing):[A-Z][A-Za-z]+\b", stderr))),
        "resources": sorted(set(re.findall(r"arn:aws:(?:sts|iam|cloudformation|ecs|ecr|elasticloadbalancing):[A-Za-z0-9_:/.*@-]+", stderr))),
        "no_identity_allow": "no identity-based policy allows" in stderr,
        "explicit_deny": "explicit deny" in stderr.lower(),
        "boundary_mentioned": "permissions boundary" in stderr.lower(),
        "account_control_mentioned": "service control policy" in stderr.lower(),
    }


def run(arguments, input_text=None):
    result = subprocess.run(arguments, input=input_text, text=True, capture_output=True, cwd=ROOT, timeout=2400)
    if result.returncode:
        code = re.search(r"An error occurred \(([A-Za-z0-9]+)\)", result.stderr)
        operation = " ".join(arguments[:3] if arguments[0] == "aws" else arguments[:2])
        details = json.dumps(safe_aws_error(result.stderr)) if arguments[0] == "aws" else "{}"
        raise RuntimeError(f"{operation} failed (exit {result.returncode}, code {code.group(1) if code else 'unavailable'}); safe diagnostic: {details}")
    return result.stdout.strip()


def aws(*arguments):
    command = ["aws", *arguments, "--region", REGION, "--no-cli-pager"]
    if os.environ.get("BTP_AWS_PROFILE"):
        command += ["--profile", os.environ["BTP_AWS_PROFILE"]]
    return run(command)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def identity():
    caller = json.loads(aws("sts", "get-caller-identity"))
    if caller["Account"] != ACCOUNT:
        raise ValueError("Unexpected AWS account")
    return caller["Arn"]


def verify_oidc_subject(settings, trust):
    prefix = settings.get("sub_claim_prefix")
    if settings.get("use_default") is not True or not isinstance(prefix, str) or not prefix.startswith("repo:"):
        raise ValueError("Unexpected GitHub OIDC subject customization; review exact trust before deploying")
    expected = prefix + ":ref:refs/heads/main"
    condition = trust["Statement"][0]["Condition"]["StringEquals"]
    if condition.get("token.actions.githubusercontent.com:sub") != expected or condition.get("token.actions.githubusercontent.com:aud") != "sts.amazonaws.com":
        raise ValueError("Repository OIDC subject/audience differs from the reviewed trust policy")
    return expected


def gate(sha, allow_older=False):
    if not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise ValueError("Use a full Git SHA")
    if run(["git", "rev-parse", "HEAD"]) != sha:
        raise ValueError("Checkout must match exact deployment SHA")
    run(["git", "diff", "--exit-code", "HEAD", "--", "backend", "frontend/src", "frontend/package.json",
         "frontend/package-lock.json", "Dockerfile", "pipeline", "scripts/package_release.py", "requirements-app.lock"])
    main = json.loads(run(["gh", "api", "repos/" + REPO + "/commits/main"]))["sha"]
    if not allow_older and main != sha:
        raise ValueError("Obsolete automatic deployment: main has advanced")
    if allow_older:
        comparison = json.loads(run(["gh", "api", "repos/" + REPO + "/compare/" + sha + "...main"]))
        if comparison["status"] not in {"ahead", "identical"}:
            raise ValueError("Manual deployment SHA must be on main history")
    runs = json.loads(run(["gh", "run", "list", "--repo", REPO, "--workflow", "ci.yml", "--commit", sha,
                           "--limit", "20", "--json", "databaseId,headSha,headBranch,event,status,conclusion,url"]))
    valid = [entry for entry in runs if entry["headSha"] == sha and entry["headBranch"] == "main" and
             entry["event"] in {"push", "workflow_dispatch"} and entry["status"] == "completed" and entry["conclusion"] == "success"]
    if not valid:
        raise ValueError("Exact main commit has no successful required CI")
    proof = json.loads(run(["gh", "api", "repos/" + REPO + "/actions/runs/" + str(valid[0]["databaseId"])]))
    if proof["head_repository"]["full_name"] != REPO or proof["path"] != ".github/workflows/ci.yml":
        raise ValueError("CI provenance differs")
    jobs = json.loads(run(["gh", "api", "repos/" + REPO + "/actions/runs/" + str(valid[0]["databaseId"]) + "/jobs?per_page=100"]))
    required = {"infrastructure", "software-and-fixture-container"}
    passed = {entry["name"] for entry in jobs["jobs"] if entry["conclusion"] == "success"}
    if not required <= passed:
        raise ValueError("Required CI jobs did not both succeed")
    settings = json.loads(run(["gh", "api", "repos/" + REPO + "/actions/oidc/customization/sub"]))
    trust = json.loads((ROOT / "infra/iam/github-deploy-trust.json").read_text())
    verify_oidc_subject(settings, trust)
    return {"commit": sha, "ci_url": valid[0]["url"]}


def restore_archive(archive, destination):
    from scripts.package_release import RELEASE_FILES

    if archive.stat().st_size > ARTIFACTS["maximum_archive_bytes"] or hashlib.sha256(archive.read_bytes()).hexdigest() != ARTIFACTS["archive_sha256"]:
        raise ValueError("Trusted archive size/checksum mismatch; do not extract")
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        total = sum(entry.size for entry in members)
        if total > ARTIFACTS["maximum_expanded_bytes"] or len(members) > 20:
            raise ValueError("Archive expansion exceeds bounds")
        allowed = {"release"} | {"release/" + name for name in RELEASE_FILES} | {"package-manifest.json"}
        if any(entry.name not in allowed or (not entry.isfile() and not entry.isdir()) for entry in members):
            raise ValueError("Unexpected archive path/type")
        if destination.exists():
            raise ValueError("Do not overwrite an existing artifact directory")
        destination.mkdir(parents=True)
        for entry in members:
            if entry.isfile() and entry.name.startswith("release/") and entry.name != "release/descriptor.json":
                with bundle.extractfile(entry) as source:
                    (destination / entry.name.split("/")[1]).write_bytes(source.read())


def hydrate():
    identity()
    destination = ROOT / "artifacts/releases/btp-exploratory-v1"
    if not destination.exists():
        archive = ROOT / "data/tmp/trusted-release.tar.gz"
        archive.parent.mkdir(parents=True, exist_ok=True)
        metadata = json.loads(aws("s3api", "head-object", "--bucket", ARTIFACTS["bucket"], "--key", ARTIFACTS["key"]))
        if metadata["ContentLength"] > ARTIFACTS["maximum_archive_bytes"]:
            raise ValueError("Unexpected S3 artifact size")
        aws("s3api", "get-object", "--bucket", ARTIFACTS["bucket"], "--key", ARTIFACTS["key"], str(archive))
        restore_archive(archive, destination)
    from backend.app import Release
    release = Release(ROOT / "docs/serving_release.json")
    if release.descriptor["release_manifest_sha256"] != ARTIFACTS["manifest_sha256"]:
        raise ValueError("Release differs from approved artifact")
    print("Existing trusted artifact verified; no S3 writes/model changes")


def publish(args):
    proof = gate(args.sha, args.allow_older)
    identity()
    from scripts.package_release import validate_context
    resource = validate_context(args.context, "release", code_version=args.sha)
    if resource.descriptor["release_manifest_sha256"] != ARTIFACTS["manifest_sha256"]:
        raise ValueError("Wrong trusted artifact")
    local = json.loads(run(["docker", "image", "inspect", args.image]))[0]
    if local["Os"] != "linux" or local["Architecture"] != "amd64" or local["Config"]["Labels"]["org.opencontainers.image.revision"] != args.sha:
        raise ValueError("Image is not the expected exact-commit Linux build")
    password = aws("ecr", "get-login-password")
    run(["docker", "login", "--username", "AWS", "--password-stdin", REGISTRY], password)
    try:
        tag = REPOSITORY + ":" + args.sha
        existing = json.loads(aws("ecr", "describe-images", "--repository-name", "btp-demo-app", "--filter", "tagStatus=TAGGED",
                                 "--query", "imageDetails[?contains(imageTags, '" + args.sha + "')]"))
        if existing:
            immutable = REPOSITORY + "@" + existing[0]["imageDigest"]
            run(["docker", "pull", immutable])
            previous = json.loads(run(["docker", "image", "inspect", immutable]))[0]
            if previous["Config"]["Labels"]["org.opencontainers.image.revision"] != args.sha:
                raise ValueError("Existing immutable tag has wrong code identity; do not overwrite")
            print("Reusing existing immutable SHA image; no retag/delete")
        else:
            run(["docker", "tag", args.image, tag])
            run(["docker", "push", tag])
        details = json.loads(aws("ecr", "describe-images", "--repository-name", "btp-demo-app", "--image-ids", "imageTag=" + args.sha))["imageDetails"][0]
        digest = details["imageDigest"]
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
            raise ValueError("Invalid ECR digest")
        manifest = json.loads(run(["docker", "buildx", "imagetools", "inspect", REPOSITORY + "@" + digest, "--raw"]))
        children = [entry["digest"] for entry in manifest.get("manifests", []) if entry.get("platform", {}).get("architecture") == "amd64" and entry.get("platform", {}).get("os") == "linux"]
        if manifest.get("manifests") and len(children) != 1:
            raise ValueError("Expected one Linux amd64 child")
        save(args.record, {**proof, "image_uri": REPOSITORY + "@" + digest, "image_tag": args.sha, "digest": digest,
                          "platform_digests": children or [digest], "code_version": args.sha,
                          "artifact_manifest": ARTIFACTS["manifest_sha256"], "published_utc": datetime.now(timezone.utc).isoformat()})
    finally:
        run(["docker", "logout", REGISTRY])
    print("SHA-tagged image published to existing ECR; no S3 writes")


def stack():
    value = json.loads(aws("cloudformation", "describe-stacks", "--stack-name", STACK))["Stacks"][0]
    outputs = {entry["OutputKey"]: entry["OutputValue"] for entry in value["Outputs"]}
    return value, outputs


def deploy(args, target_sha=None):
    gate(args.sha, args.allow_older)
    identity()
    record = json.loads(args.record.read_text())
    desired_sha = target_sha or args.sha
    if record["code_version"] != desired_sha or record["image_uri"] != REPOSITORY + "@" + record["digest"]:
        raise ValueError("Record identity mismatch")
    current, outputs = stack()
    record["previous"] = {key: outputs[key] for key in ["ImageUri", "CodeVersion", "TaskDefinition"]}
    if outputs["ImageUri"] == record["image_uri"] and outputs["CodeVersion"] == desired_sha:
        save(args.record, record)
        print("Exact immutable release already deployed; health/smoke still required")
        return
    if current["StackStatus"] not in {"CREATE_COMPLETE", "UPDATE_COMPLETE", "UPDATE_ROLLBACK_COMPLETE"}:
        raise ValueError("Stack not ready for application update")
    aws("cloudformation", "validate-template", "--template-body", "file://" + str(ROOT / "infra/application.json"))
    parameters = parameter_update(current["Parameters"], record["image_uri"], desired_sha)
    parameter_path = ROOT / "data/tmp/cd-parameters.json"
    save(parameter_path, parameters)
    name = "btp-cd-" + args.sha[:16] + "-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    aws("cloudformation", "create-change-set", "--stack-name", STACK, "--change-set-name", name, "--change-set-type", "UPDATE",
        "--use-previous-template", "--parameters", "file://" + str(parameter_path), "--capabilities", "CAPABILITY_NAMED_IAM")
    record["change_set"] = name
    save(args.record, record)
    aws("cloudformation", "wait", "change-set-create-complete", "--stack-name", STACK, "--change-set-name", name)
    change = json.loads(aws("cloudformation", "describe-change-set", "--stack-name", STACK, "--change-set-name", name))
    validate_changes(change["Changes"])
    record["changes"] = [{key: entry["ResourceChange"].get(key) for key in ["LogicalResourceId", "ResourceType", "Action", "Replacement"]} for entry in change["Changes"]]
    save(args.record, record)
    print(json.dumps({"reviewed_changes": record["changes"]}))
    gate(args.sha, args.allow_older)
    aws("cloudformation", "execute-change-set", "--stack-name", STACK, "--change-set-name", name)
    aws("cloudformation", "wait", "stack-update-complete", "--stack-name", STACK)
    print("CloudFormation update complete; actual task health and public smoke still required")


def rollback(args):
    original = json.loads(args.record.read_text())
    previous = original["previous"]
    if not re.fullmatch(r"[a-f0-9]{40}", previous["CodeVersion"]) or not re.fullmatch(re.escape(REPOSITORY) + r"@sha256:[a-f0-9]{64}", previous["ImageUri"]):
        raise ValueError("Invalid previous production identity")
    args.record = ROOT / "data/tmp/rollback-release.json"
    save(args.record, {"code_version": previous["CodeVersion"], "image_uri": previous["ImageUri"],
                       "digest": previous["ImageUri"].split("@")[1], "rollback_from": original["code_version"]})
    deploy(args, target_sha=previous["CodeVersion"])
    current, outputs = stack()
    if current["StackStatus"] != "UPDATE_COMPLETE" or outputs["ImageUri"] != previous["ImageUri"] or outputs["CodeVersion"] != previous["CodeVersion"]:
        raise ValueError("Rollback did not restore expected stack image")
    aws("ecs", "wait", "services-stable", "--cluster", outputs["Cluster"], "--services", outputs["Service"])
    service = json.loads(aws("ecs", "describe-services", "--cluster", outputs["Cluster"], "--services", outputs["Service"]))["services"][0]
    if service["runningCount"] != 1 or service["pendingCount"] or service["taskDefinition"] != outputs["TaskDefinition"]:
        raise ValueError("Rollback service identity/health incomplete")
    targets = json.loads(aws("elbv2", "describe-target-health", "--target-group-arn", outputs["TargetGroup"]))["TargetHealthDescriptions"]
    if not targets or any(entry["TargetHealth"]["State"] != "healthy" for entry in targets):
        raise ValueError("Rollback ALB health incomplete")
    versions = json.loads(request("/api/versions")[2])
    if versions["code_version"] != previous["CodeVersion"] or versions["manifest_sha256"] != ARTIFACTS["manifest_sha256"] or request("/api/ready")[0] != 200:
        raise ValueError("Rollback public release/readiness mismatch")
    print("Previous immutable image restored through CloudFormation; public readiness and ALB health verified")


def request(path, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    try:
        with urlopen(Request(BASE + path, data=body, headers={"Content-Type": "application/json"} if body else {}), timeout=30) as response:
            return response.status, response.headers, response.read()
    except HTTPError as error:
        return error.code, error.headers, error.read()


def verify(args):
    from backend.app import predictions_agree
    from pipeline.serving import predict_case
    from scripts.package_release import validate_context
    identity()
    record = json.loads(args.record.read_text())
    current, outputs = stack()
    if current["StackStatus"] not in {"CREATE_COMPLETE", "UPDATE_COMPLETE"} or outputs["ImageUri"] != record["image_uri"] or outputs["CodeVersion"] != args.sha:
        raise ValueError("Stack did not deploy expected release (possible rollback)")
    aws("ecs", "wait", "services-stable", "--cluster", outputs["Cluster"], "--services", outputs["Service"])
    service = json.loads(aws("ecs", "describe-services", "--cluster", outputs["Cluster"], "--services", outputs["Service"]))["services"][0]
    if service["runningCount"] != 1 or service["pendingCount"] != 0 or service["taskDefinition"] != outputs["TaskDefinition"]:
        raise ValueError("Unexpected service/task identity")
    tasks = json.loads(aws("ecs", "list-tasks", "--cluster", outputs["Cluster"], "--service-name", outputs["Service"]))["taskArns"]
    details = json.loads(aws("ecs", "describe-tasks", "--cluster", outputs["Cluster"], "--tasks", *tasks))["tasks"]
    for task in details:
        app = next(entry for entry in task["containers"] if entry["name"] == "app")
        if (task["lastStatus"] != "RUNNING" or task["taskDefinitionArn"] != outputs["TaskDefinition"] or
                app.get("healthStatus") != "HEALTHY" or app["image"] != record["image_uri"] or
                app["imageDigest"] not in set(record["platform_digests"] + [record["digest"]])):
            raise ValueError("Unhealthy/wrong production image")
    targets = json.loads(aws("elbv2", "describe-target-health", "--target-group-arn", outputs["TargetGroup"]))["TargetHealthDescriptions"]
    if not targets or any(entry["TargetHealth"]["State"] != "healthy" for entry in targets):
        raise ValueError("ALB target unhealthy")
    resource = validate_context(args.context, "release", code_version=args.sha)
    versions = json.loads(request("/api/versions")[2])
    assert versions["code_version"] == args.sha and versions["manifest_sha256"] == ARTIFACTS["manifest_sha256"]
    assert versions["demo_cases"] == 200 and versions["evaluation_examples"] == 936 and not versions["fixture"]
    assert json.loads(request("/api/ready")[2])["status"] == "ready" and request("/api/health")[0] == 200
    metrics = json.loads(request("/api/evaluation")[2])
    assert metrics == resource.metrics
    with closing(resource.connect()) as connection:
        case_id, inputs, stored = connection.execute("SELECT case_id,inputs_json,prediction_json FROM followup_queue ORDER BY case_id LIMIT 1").fetchone()
    status, headers, body = request("/api/predict/manual", {"eligibility_confirmed": True, "features": json.loads(inputs)["features"], "inspection_date": "2023-05-31"})
    manual = json.loads(body)
    assert status == 200 and headers.get("Cache-Control") == "no-store" and headers.get("X-Cache") != "Hit from cloudfront"
    assert predictions_agree(manual["prediction"], json.loads(stored)) and not manual["stored"]
    assert manual["nominal_followup_window"] == {"start": "2024-02-29", "end": "2024-08-31"}
    for path in ["/", "/predict", "/queue", "/evaluation", "/methodology"]:
        status, headers, body = request(path)
        assert status == 200 and b'<div id="root">' in body and b'/assets/' in body
    assets = set(re.findall(rb'[/]assets/[^"\s<>]+', body))
    assert assets
    for asset in assets:
        status, headers, content = request(asset.decode())
        assert status == 200 and content and "text/html" not in headers.get("Content-Type", "")
    queue = json.loads(request("/api/queue?capacity=500&limit=100")[2])
    assert queue["selected"] == 200 and queue["exceeds_available"]
    second = json.loads(request("/api/queue?capacity=500&limit=100&offset=100")[2])
    ranked = queue["items"] + second["items"]
    assert len(ranked) == 200 and len({entry["case_id"] for entry in ranked}) == 200
    assert ranked == sorted(ranked, key=lambda entry: (-entry["exploratory_prioritization_score"], entry["case_id"]))
    assert request("/api/queue?capacity=501")[0] == 422 and request("/api/cases/unknown")[0] == 404
    assert request("/api/no-such-endpoint")[0] == 404 and request("/assets/no-such.js")[0] == 404
    assert json.loads(request("/api/evaluation")[2]) == metrics
    record.update({"verified_utc": datetime.now(timezone.utc).isoformat(), "task_definition": outputs["TaskDefinition"],
                   "service_status": "stable one healthy task", "alb_targets": "healthy", "public_url": BASE,
                   "prediction_agreement": True, "evaluation_unchanged": True})
    save(args.record, record)
    print(json.dumps(record))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["gate", "hydrate", "publish", "deploy", "verify", "rollback"])
    parser.add_argument("--sha", default=os.environ.get("DEPLOY_SHA", ""))
    parser.add_argument("--context", type=Path, default=ROOT / "data/package/production")
    parser.add_argument("--image", default="btp-production:release")
    parser.add_argument("--record", type=Path, default=ROOT / "data/tmp/production-release.json")
    parser.add_argument("--allow-older", action="store_true")
    args = parser.parse_args()
    if args.action == "gate":
        print(json.dumps(gate(args.sha, args.allow_older)))
    elif args.action == "hydrate":
        hydrate()
    else:
        globals()[args.action](args)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as error:
        raise SystemExit(str(error)) from None
