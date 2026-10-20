"""Bounded, read-only Dev_1 console diagnostics; never emit AWS response bodies."""

import argparse
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCOUNT = "044854093109"
PRINCIPAL = f"arn:aws:iam::{ACCOUNT}:user/Dev_1"
CLUSTER = f"arn:aws:ecs:ap-south-1:{ACCOUNT}:cluster/btp-demo-cluster"
BUCKET = "btp-demo-artifacts-044854093109-ap-south-1"
POLICIES = ["BtpDemoOperator", "BtpDemoNetwork", "BtpDemoServices", "BtpDemoRoles",
            "BtpDemoConsoleViewSupplement", "BtpDemoExecutionBoundary", "BtpDemoApplicationBoundary"]
POLICY_FILES = ["operator.json", "network.json", "services.json", "roles.json", "console-view-supplement.json",
                "execution-boundary.json", "application-boundary.json"]


def denial_kind(message):
    lowered = message.lower()
    if "service control policy" in lowered:
        return "service-control-policy mentioned; administrator must inspect Organizations"
    if "permissions boundary" in lowered or "permissions-boundary" in lowered:
        return "permissions-boundary mentioned; administrator must inspect the user boundary"
    if "session policy" in lowered:
        return "session-policy mentioned"
    if "explicit deny" in lowered:
        return "explicit deny; source not established by this diagnostic"
    if "no identity-based policy allows" in lowered:
        return "missing identity-based Allow; does not rule out additional boundary/SCP controls"
    return "not established; do not infer a boundary or SCP from an unspecified denial"


def invoke(profile, service, operation, arguments, query):
    result = subprocess.run(["aws", service, operation, *arguments, "--query", query, "--output", "json",
                             "--profile", profile, "--region", "ap-south-1", "--no-cli-pager"],
                            capture_output=True, text=True, timeout=60, cwd=ROOT)
    if result.returncode:
        match = re.search(r"An error occurred \(([^)]+)\) when calling the (\w+) operation: ([^\r\n]+)", result.stderr)
        if not match:
            return {"status": "failed", "detail": "CLI/authentication failure; raw output deliberately omitted"}, None
        code, api, message = match.groups()
        message = re.split(r" Go to https://|, or call the GetRequestAuthorizationDetails", message)[0]
        message = re.sub(r"https?://\S+", "[URL omitted]", message)
        message = re.sub(r"(?i)X-Btp-[a-f0-9]+|\b[a-f0-9]{64}\b", "[redacted config value]", message)
        return {"status": "denied" if "denied" in code.lower() else "failed", "code": code,
                "api": api, "message": message, "attribution": denial_kind(message)}, None
    return {"status": "allowed"}, json.loads(result.stdout or "null")


def check(profile, output):
    checks = []
    policy_matches = {}

    def call(name, service, operation, arguments=(), query="null"):
        result, data = invoke(profile, service, operation, list(arguments), query)
        checks.append({"check": name, "operation": f"{service}:{operation}", **result})
        return data

    identity = call("identity", "sts", "get-caller-identity", query="{Account:Account,Arn:Arn}")
    if identity != {"Account": ACCOUNT, "Arn": PRINCIPAL}:
        raise ValueError("STOP: profile does not resolve to the expected account and Dev_1; no other checks run")
    user = call("Dev1 boundary metadata", "iam", "get-user", ["--user-name", "Dev_1"], "User.{Arn:Arn,Boundary:PermissionsBoundary}")
    attached = call("Dev1 attached policy metadata", "iam", "list-attached-user-policies", ["--user-name", "Dev_1"], "AttachedPolicies[].{Name:PolicyName,Arn:PolicyArn}")
    inline_count = call("Dev1 inline policy names", "iam", "list-user-policies", ["--user-name", "Dev_1"], "length(PolicyNames)")
    groups = call("Dev1 group membership metadata", "iam", "list-groups-for-user", ["--user-name", "Dev_1"], "Groups[].Arn")
    for name, filename in zip(POLICIES, POLICY_FILES):
        arn = f"arn:aws:iam::{ACCOUNT}:policy/{name}"
        policy = call(name, "iam", "get-policy", ["--policy-arn", arn], "Policy.{Arn:Arn,Version:DefaultVersionId}")
        if policy:
            document = call(name + " version", "iam", "get-policy-version", ["--policy-arn", arn, "--version-id", policy["Version"]], "PolicyVersion.Document")
            if isinstance(document, dict):
                policy_matches[name] = {"default_version": policy["Version"], "matches_local_json": document == json.loads((ROOT / "infra/iam" / filename).read_text())}
            call(name + " version history", "iam", "list-policy-versions", ["--policy-arn", arn], "length(Versions)")
    call("stack console list", "cloudformation", "list-stacks", query="length(StackSummaries)")
    physical = {}
    for stack in ["btp-demo-app", "btp-demo-storage"]:
        call(stack + " status and output names", "cloudformation", "describe-stacks", ["--stack-name", stack], "Stacks[0].{Status:StackStatus,OutputNames:Outputs[].OutputKey}")
        call(stack + " resource detail", "cloudformation", "describe-stack-resources", ["--stack-name", stack], "length(StackResources)")
        call(stack + " events", "cloudformation", "describe-stack-events", ["--stack-name", stack], "length(StackEvents)")
        resources = call(stack + " resource inventory", "cloudformation", "list-stack-resources", ["--stack-name", stack], "StackResourceSummaries[].{Name:LogicalResourceId,Id:PhysicalResourceId}")
        if resources and stack == "btp-demo-app":
            physical = {item["Name"]: item.get("Id") for item in resources}
    call("ECS console clusters", "ecs", "list-clusters", query="length(clusterArns)")
    call("ECS project cluster", "ecs", "describe-clusters", ["--clusters", CLUSTER], "clusters[].status")
    call("ECS project services", "ecs", "list-services", ["--cluster", CLUSTER], "length(serviceArns)")
    call("ECS project service detail", "ecs", "describe-services", ["--cluster", CLUSTER, "--services", "btp-demo-app"], "services[].{Status:status,Running:runningCount}")
    call("ECS task definitions", "ecs", "list-task-definitions", ["--family-prefix", "btp-demo-app-app", "--max-items", "5"], "length(taskDefinitionArns)")
    call("ECS task families", "ecs", "list-task-definition-families", ["--family-prefix", "btp-demo-app-app", "--max-items", "5"], "length(families)")
    if physical.get("Task"):
        call("ECS project task-definition detail", "ecs", "describe-task-definition", ["--task-definition", physical["Task"]], "taskDefinition.{Arn:taskDefinitionArn,Cpu:cpu,Memory:memory}")
    tasks = call("ECS project task list", "ecs", "list-tasks", ["--cluster", CLUSTER, "--service-name", "btp-demo-app"], "taskArns")
    if tasks:
        task = call("ECS project task detail", "ecs", "describe-tasks", ["--cluster", CLUSTER, "--tasks", *tasks], "tasks[].{Health:healthStatus,Attachments:attachments}")
        if task:
            enis = [detail["value"] for current in task for attachment in current["Attachments"] for detail in attachment.get("details", []) if detail["name"] == "networkInterfaceId"]
            if enis:
                call("project task network interface", "ec2", "describe-network-interfaces", ["--network-interface-ids", *enis], "length(NetworkInterfaces)")
    call("project ECR repository", "ecr", "describe-repositories", ["--repository-names", "btp-demo-app"], "repositories[].repositoryArn")
    call("project ECR image metadata", "ecr", "describe-images", ["--repository-name", "btp-demo-app"], "length(imageDetails)")
    call("project ECR image list", "ecr", "list-images", ["--repository-name", "btp-demo-app"], "length(imageIds)")
    call("CloudFront console list (secret fields excluded)", "cloudfront", "list-distributions", query="DistributionList.Items[].{Id:Id,Domain:DomainName}")
    if physical.get("Distribution"):
        call("project CloudFront status", "cloudfront", "get-distribution", ["--id", physical["Distribution"]], "Distribution.Status")
        call("project CloudFront configuration (origins excluded)", "cloudfront", "get-distribution-config", ["--id", physical["Distribution"]], "{Enabled:DistributionConfig.Enabled,ViewerProtocol:DistributionConfig.DefaultCacheBehavior.ViewerProtocolPolicy}")
    if physical.get("Alb"):
        call("project ALB", "elbv2", "describe-load-balancers", ["--load-balancer-arns", physical["Alb"]], "LoadBalancers[].State.Code")
        call("project listener", "elbv2", "describe-listeners", ["--load-balancer-arn", physical["Alb"]], "Listeners[].Port")
    if physical.get("Http"):
        call("project ALB rules (header conditions excluded)", "elbv2", "describe-rules", ["--listener-arn", physical["Http"]], "Rules[].{Priority:Priority,Actions:Actions[].Type}")
    if physical.get("Targets"):
        call("project target group", "elbv2", "describe-target-groups", ["--target-group-arns", physical["Targets"]], "TargetGroups[].Protocol")
        call("project target health", "elbv2", "describe-target-health", ["--target-group-arn", physical["Targets"]], "TargetHealthDescriptions[].TargetHealth.State")
    for name, operation, parameter, ids, query in [
        ("project VPC", "describe-vpcs", "--vpc-ids", [physical.get("Vpc")], "length(Vpcs)"),
        ("project subnets", "describe-subnets", "--subnet-ids", [physical.get("SubnetA"), physical.get("SubnetB")], "length(Subnets)"),
        ("project routes", "describe-route-tables", "--route-table-ids", [physical.get("Routes")], "length(RouteTables)"),
        ("project security groups", "describe-security-groups", "--group-ids", [physical.get("AlbGroup"), physical.get("TaskGroup")], "length(SecurityGroups)")]:
        if all(ids):
            call(name, "ec2", operation, [parameter, *ids], query)
    call("project metric discovery", "cloudwatch", "list-metrics", ["--namespace", "AWS/ECS", "--dimensions", "Name=ClusterName,Value=btp-demo-cluster", "--max-items", "5"], "length(Metrics)")
    end = datetime.now(timezone.utc)
    metric = [{"Id": "memory", "MetricStat": {"Metric": {"Namespace": "AWS/ECS", "MetricName": "MemoryUtilization", "Dimensions": [{"Name": "ClusterName", "Value": "btp-demo-cluster"}, {"Name": "ServiceName", "Value": "btp-demo-app"}]}, "Period": 60, "Stat": "Average"}}]
    call("project metric graph read", "cloudwatch", "get-metric-data", ["--metric-data-queries", json.dumps(metric), "--start-time", (end-timedelta(minutes=10)).isoformat(), "--end-time", end.isoformat()], "MetricDataResults[].StatusCode")
    call("log-group discovery", "logs", "describe-log-groups", ["--log-group-name-prefix", "/btp/btp-demo-app"], "length(logGroups)")
    streams = call("project log streams", "logs", "describe-log-streams", ["--log-group-name", "/btp/btp-demo-app", "--order-by", "LastEventTime", "--descending", "--limit", "1"], "logStreams[].logStreamName")
    if streams:
        call("project application log read (messages excluded)", "logs", "get-log-events", ["--log-group-name", "/btp/btp-demo-app", "--log-stream-name", streams[0], "--limit", "3"], "length(events)")
    call("project log filter (messages excluded)", "logs", "filter-log-events", ["--log-group-name", "/btp/btp-demo-app", "--limit", "1"], "length(events)")
    call("project log field metadata", "logs", "get-log-group-fields", ["--log-group-name", "/btp/btp-demo-app"], "length(logGroupFields)")
    for role in ["btp-demo-execution", "btp-demo-application"]:
        call(role, "iam", "get-role", ["--role-name", role], "Role.{Arn:Arn,Boundary:PermissionsBoundary}")
        policies = call(role + " inline policy list", "iam", "list-role-policies", ["--role-name", role], "PolicyNames")
        for policy in policies or []:
            call(role + " inline policy configuration", "iam", "get-role-policy", ["--role-name", role, "--policy-name", policy], "length(PolicyDocument.Statement)")
        call(role + " attached policy list", "iam", "list-attached-role-policies", ["--role-name", role], "length(AttachedPolicies)")
    call("S3 console bucket discovery", "s3api", "list-buckets", query="length(Buckets)")
    for name, operation, query in [
        ("location", "get-bucket-location", "LocationConstraint"),
        ("versioning", "get-bucket-versioning", "Status"),
        ("public access block", "get-public-access-block", "PublicAccessBlockConfiguration"),
        ("encryption metadata", "get-bucket-encryption", "length(ServerSideEncryptionConfiguration.Rules)"),
        ("policy public status", "get-bucket-policy-status", "PolicyStatus.IsPublic"),
        ("ACL metadata", "get-bucket-acl", "length(Grants)"),
        ("bucket policy metadata", "get-bucket-policy", "length(Policy)"),
        ("ownership controls", "get-bucket-ownership-controls", "OwnershipControls.Rules[].ObjectOwnership"),
        ("tag metadata", "get-bucket-tagging", "length(TagSet)"),
        ("object listing without content", "list-objects-v2", "KeyCount")]:
        call("project bucket " + name, "s3api", operation, ["--bucket", BUCKET], query)
    report = {"recorded_at": datetime.now(timezone.utc).isoformat(), "profile": profile, "identity": identity,
              "user_boundary_metadata": user, "attached_policy_metadata": attached, "inline_policy_count": inline_count,
              "group_membership_metadata": groups, "project_policy_matches_repository": policy_matches, "checks": checks,
              "summary": {status: sum(item["status"] == status for item in checks) for status in ["allowed", "denied", "failed"]},
              "limitations": "Allowed reads do not prove absence of other effective grants. Unreadable SCP/group/inline/boundary contents remain administrator checks; no account-control inference from an unspecified denial. No raw service/config/log/object bodies recorded."}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"identity": identity, "summary": report["summary"], "report": str(output)}))
    for item in checks:
        if item["status"] != "allowed":
            print(json.dumps(item))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="beyond-the-pass")
    parser.add_argument("--output", type=Path, default=ROOT / "data/tmp/console-access-check.json")
    args = parser.parse_args()
    check(args.profile, args.output)


if __name__ == "__main__":
    main()
