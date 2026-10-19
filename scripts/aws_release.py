"""Manual Phase 6 operations. Mutations require an explicitly approved plan hash."""

import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE = "beyond-the-pass"
REGION = "ap-south-1"
ACCOUNT = "044854093109"
BOOTSTRAP = "btp-demo-storage"
APP = "btp-demo-app"
CONTEXT = ROOT / "data/package/phase5-real-portable"
RECORD = ROOT / "data/tmp/aws-published.json"
PARAMETERS = ROOT / "data/tmp/aws-parameters.json"
PLAN = ROOT / "docs/DEPLOYMENT_PLAN.md"
EXPECTED_IMAGE = "sha256:ef69b2d2b4ac3e75d32744b745318e88e85e921cdfcec01004f139406f6f801f"
EXPECTED_CODE = "f668daf9447f2f97175c7355a9388f47354b2b75"
EXPECTED_ARTIFACT = "btp-exploratory-v1"


def plan_hash():
    return hashlib.sha256(PLAN.read_bytes()).hexdigest()


def require_approval(approved):
    if not approved or approved != plan_hash():
        raise ValueError("STOP: obtain human approval of the current deployment plan, then supply its SHA256. A hash alone is not approval.")


def verified_deployment_commit():
    if run(["git", "status", "--porcelain", "--", "infra", "scripts", "tests", ".github", "requirements-infra.lock"]):
        raise ValueError("Deployment code/configuration must be committed and match the verified CI revision")
    revision = run(["git", "rev-parse", "HEAD"])
    runs = json.loads(run(["gh", "run", "list", "--repo", "RufinaM03/beyond-the-pass", "--workflow", "ci.yml", "--commit", revision,
                           "--limit", "1", "--json", "headSha,status,conclusion,url"]))
    if not runs or runs[0]["headSha"] != revision or runs[0]["status"] != "completed" or runs[0]["conclusion"] != "success":
        raise ValueError("Exact deployment commit has no current successful CI run")
    return {"deployment_commit": revision, "ci_url": runs[0]["url"]}


def run(arguments, *, input_text=None):
    result = subprocess.run(arguments, input=input_text, text=True, capture_output=True, cwd=ROOT, timeout=2400)
    if result.returncode:
        raise RuntimeError(f"{arguments[0]} operation failed (exit {result.returncode}); inspect the service/CLI without printing secrets or parameter files")
    return result.stdout.strip()


def aws(*arguments):
    return run(["aws", *arguments, "--profile", PROFILE, "--region", REGION, "--no-cli-pager"])


def identity():
    caller = json.loads(aws("sts", "get-caller-identity", "--output", "json"))
    if caller["Account"] != ACCOUNT:
        raise ValueError("Unexpected account; do not deploy into it")
    return caller["Arn"]


def outputs(stack):
    response = json.loads(aws("cloudformation", "describe-stacks", "--stack-name", stack, "--output", "json"))
    return {item["OutputKey"]: item["OutputValue"] for item in response["Stacks"][0]["Outputs"]}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    if os.name != "nt":
        path.chmod(0o600)


def validate_parameters(parameters):
    values = {item["ParameterKey"]: item["ParameterValue"] for item in parameters}
    if len(values) != len(parameters):
        raise ValueError("Duplicate parameters")
    if values.get("HttpsMode") not in {"domain", "cloudfront"}:
        raise ValueError("Choose domain or cloudfront explicitly")
    if values.get("AvailabilityZoneA") == values.get("AvailabilityZoneB"):
        raise ValueError("Two distinct available zones are required")
    for key in ["AvailabilityZoneA", "AvailabilityZoneB"]:
        if not isinstance(values.get(key), str) or not re.fullmatch(r"ap-south-1[a-z]", values[key]):
            raise ValueError("Use verified Mumbai zones")
    if values["HttpsMode"] == "domain" and not re.fullmatch(r"arn:aws:acm:ap-south-1:" + ACCOUNT + r":certificate/[a-f0-9-]+", values.get("CertificateArn", "")):
        raise ValueError("Domain mode requires an issued Mumbai certificate in the expected account")
    if values["HttpsMode"] == "cloudfront" and not re.fullmatch(r"pl-[a-f0-9]+", values.get("CloudFrontPrefixListId", "")):
        raise ValueError("Verify the managed CloudFront prefix list first")
    if not re.fullmatch(r"X-Btp-[a-f0-9]{24}", values.get("OriginHeaderName", "")) or not re.fullmatch(r"[a-f0-9]{64}", values.get("OriginHeaderValue", "")):
        raise ValueError("Origin controls require locally generated secrets")
    if values.get("TaskSize") not in {"small", "memory", "cpu"}:
        raise ValueError("Unsupported task size")
    if not 60 <= int(values.get("HealthGraceSeconds", "0")) <= 600:
        raise ValueError("Grace must be between 60 and 600 seconds")
    return values


def prepare(args):
    if PARAMETERS.exists():
        raise ValueError("Parameters already exist; preserve them for updates/rollback, do not silently rotate the origin secret")
    values = {"HttpsMode": args.https, "AvailabilityZoneA": args.zone_a, "AvailabilityZoneB": args.zone_b,
              "CertificateArn": args.certificate or "", "CloudFrontPrefixListId": args.prefix_list or "",
              "OriginHeaderName": "X-Btp-" + secrets.token_hex(12), "OriginHeaderValue": secrets.token_hex(32),
              "TaskSize": "small", "HealthGraceSeconds": "120", "LogRetentionDays": "7"}
    parameters = [{"ParameterKey": key, "ParameterValue": value} for key, value in values.items()]
    validate_parameters(parameters)
    save(PARAMETERS, parameters)
    print("Created ignored local parameter file; do not print, commit or upload it. Restrict its Windows ACL to your account.")


def publish():
    from scripts.package_release import validate_context

    validate_context(CONTEXT, "release", code_version=EXPECTED_CODE, artifact_version=EXPECTED_ARTIFACT)
    local = json.loads(run(["docker", "image", "inspect", "beyond-the-pass:phase5-real"]))[0]
    labels = local["Config"]["Labels"]
    if (local["Id"] != EXPECTED_IMAGE or local["Architecture"] != "amd64" or local["Os"] != "linux"
            or labels["org.opencontainers.image.revision"] != EXPECTED_CODE
            or labels["io.btp.artifact.kind"] != "release" or labels["io.btp.artifact.release"] != EXPECTED_ARTIFACT):
        raise ValueError("Not the verified real image; do not substitute fixture/rebuilt/unverified images")
    storage = outputs(BOOTSTRAP)
    registry = storage["RepositoryUri"].split("/")[0]
    password = aws("ecr", "get-login-password")
    run(["docker", "login", "--username", "AWS", "--password-stdin", registry], input_text=password)
    try:
        tag = storage["RepositoryUri"] + ":" + EXPECTED_CODE
        run(["docker", "tag", EXPECTED_IMAGE, tag])
        run(["docker", "push", tag])
        response = json.loads(aws("ecr", "describe-images", "--repository-name", "btp-demo-app", "--image-ids", "imageTag=" + EXPECTED_CODE, "--output", "json"))
        digest = response["imageDetails"][0]["imageDigest"]
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
            raise ValueError("Invalid ECR digest")
        image = storage["RepositoryUri"] + "@" + digest
        manifest = json.loads(run(["docker", "buildx", "imagetools", "inspect", image, "--raw"]))
        manifests = manifest.get("manifests", [])
        linux = [item["digest"] for item in manifests if item.get("platform", {}).get("architecture") == "amd64" and item.get("platform", {}).get("os") == "linux"]
        if manifests and not linux:
            raise ValueError("Pushed index has no Linux amd64 manifest")
        archive = ROOT / "data/tmp/aws-release.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            bundle.add(CONTEXT / "release", arcname="release", recursive=True)
            bundle.add(CONTEXT / "package-manifest.json", arcname="package-manifest.json")
        release_key = f"releases/{EXPECTED_ARTIFACT}/{EXPECTED_CODE}/"
        record = {**verified_deployment_commit(), "image_uri": image, "platform_digests": linux or [digest], "code_version": EXPECTED_CODE,
                  "artifact_version": EXPECTED_ARTIFACT, "local_image_id": EXPECTED_IMAGE,
                  "bundle_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "storage": storage,
                  "approved_plan_sha256": plan_hash()}
        save(RECORD, record)
        aws("s3", "cp", str(archive), "s3://" + storage["ArtifactBucket"] + "/" + release_key + archive.name, "--sse", "AES256", "--only-show-errors")
        aws("s3", "cp", str(RECORD), "s3://" + storage["ArtifactBucket"] + "/" + release_key + "published.json", "--sse", "AES256", "--only-show-errors")
        print("Published approved release by immutable ECR digest; record: data/tmp/aws-published.json")
    finally:
        run(["docker", "logout", registry])


def deploy(record_path):
    record = json.loads(record_path.read_text())
    parameters = json.loads(PARAMETERS.read_text())
    validate_parameters(parameters)
    if record["artifact_version"] != EXPECTED_ARTIFACT or record["code_version"] != EXPECTED_CODE:
        raise ValueError("Release requires a separately reviewed plan/image")
    image = record["image_uri"]
    if not re.fullmatch(ACCOUNT + r"\.dkr\.ecr\.ap-south-1\.amazonaws\.com/btp-demo-app@sha256:[a-f0-9]{64}", image):
        raise ValueError("Only approved private ECR digests may deploy")
    additions = {"ImageUri": image, "CodeVersion": record["code_version"], "RepositoryArn": record["storage"]["RepositoryArn"]}
    parameters = [item for item in parameters if item["ParameterKey"] not in additions]
    parameters += [{"ParameterKey": key, "ParameterValue": value} for key, value in additions.items()]
    save(PARAMETERS, parameters)
    aws("cloudformation", "deploy", "--stack-name", APP, "--template-file", "infra/application.json", "--parameter-overrides", "file://" + str(PARAMETERS), "--capabilities", "CAPABILITY_NAMED_IAM", "--no-fail-on-empty-changeset", "--tags", "Project=BeyondThePass")
    verify_service(record)


def verify_service(record):
    deployed = outputs(APP)
    aws("ecs", "wait", "services-stable", "--cluster", deployed["Cluster"], "--services", deployed["Service"])
    service = json.loads(aws("ecs", "describe-services", "--cluster", deployed["Cluster"], "--services", deployed["Service"], "--output", "json"))["services"][0]
    if service["taskDefinition"] != deployed["TaskDefinition"] or service["runningCount"] != 1 or service["pendingCount"] != 0:
        raise ValueError("Stable is not sufficient: unexpected task definition/count, possible rollback")
    task_arns = json.loads(aws("ecs", "list-tasks", "--cluster", deployed["Cluster"], "--service-name", deployed["Service"], "--desired-status", "RUNNING", "--output", "json"))["taskArns"]
    tasks = json.loads(aws("ecs", "describe-tasks", "--cluster", deployed["Cluster"], "--tasks", *task_arns, "--output", "json"))["tasks"]
    for task in tasks:
        app = next(container for container in task["containers"] if container["name"] == "app")
        if task["taskDefinitionArn"] != deployed["TaskDefinition"] or app.get("imageDigest") not in record["platform_digests"] or app.get("image") != record["image_uri"] or app.get("healthStatus") != "HEALTHY":
            raise ValueError("Running task does not match intended immutable release/health")
    targets = json.loads(aws("elbv2", "describe-target-health", "--target-group-arn", deployed["TargetGroup"], "--output", "json"))["TargetHealthDescriptions"]
    if not targets or any(target["TargetHealth"]["State"] != "healthy" for target in targets):
        raise ValueError("Wait for healthy targets, including replacement drain, before acceptance")
    print(json.dumps({"service_verified": True, "image_uri": record["image_uri"], "endpoint": deployed.get("CloudFrontUrl", "DNS alias pending to " + deployed["AlbDns"]), "next": "Run HTTPS acceptance and direct-IP checks; this is not complete deployment acceptance."}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["validate", "parameters", "bootstrap", "publish", "deploy", "status", "rollback", "delete-app"])
    parser.add_argument("--approved-plan-sha256")
    parser.add_argument("--https", choices=["domain", "cloudfront"])
    parser.add_argument("--zone-a")
    parser.add_argument("--zone-b")
    parser.add_argument("--certificate")
    parser.add_argument("--prefix-list")
    parser.add_argument("--record", type=Path, default=RECORD)
    args = parser.parse_args()
    if args.action == "validate":
        for path in (ROOT / "infra").glob("*.json"):
            json.loads(path.read_text())
        print("JSON syntax valid; plan SHA256: " + plan_hash())
        return
    if args.action == "parameters":
        prepare(args)
        return
    if args.action in {"bootstrap", "publish", "deploy", "rollback", "delete-app"}:
        require_approval(args.approved_plan_sha256)
        if args.action != "delete-app":
            verified_deployment_commit()
    identity()
    if args.action == "bootstrap":
        aws("cloudformation", "deploy", "--stack-name", BOOTSTRAP, "--template-file", "infra/bootstrap.json", "--no-fail-on-empty-changeset", "--tags", "Project=BeyondThePass")
    elif args.action == "publish":
        publish()
    elif args.action in {"deploy", "rollback"}:
        deploy(args.record)
    elif args.action == "status":
        verify_service(json.loads(args.record.read_text()))
    elif args.action == "delete-app":
        aws("cloudformation", "delete-stack", "--stack-name", APP)
        aws("cloudformation", "wait", "stack-delete-complete", "--stack-name", APP)
        print("Application deleted; retained ECR/S3 and optional certificate/DNS still require explicit cleanup")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as error:
        raise SystemExit(str(error)) from None
