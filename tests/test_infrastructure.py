"""Offline infrastructure invariants and invented parameters; no AWS resources."""

import json
import unittest
from unittest.mock import patch

from scripts import aws_release


class InfrastructureTests(unittest.TestCase):
    def setUp(self):
        self.template = json.loads((aws_release.ROOT / "infra/application.json").read_text())
        self.resources = self.template["Resources"]

    def parameters(self, **changes):
        values = {"HttpsMode": "cloudfront", "AvailabilityZoneA": "ap-south-1a", "AvailabilityZoneB": "ap-south-1b",
                  "CloudFrontPrefixListId": "pl-0123456789", "CertificateArn": "", "OriginHeaderName": "X-Btp-" + "a" * 24,
                  "OriginHeaderValue": "b" * 64, "TaskSize": "small", "HealthGraceSeconds": "120"}
        values.update(changes)
        return [{"ParameterKey": key, "ParameterValue": value} for key, value in values.items()]

    def test_approval_gate_fails_closed_without_network(self):
        with patch.object(aws_release, "plan_hash", return_value="approved-plan"):
            for supplied in [None, "", "different-plan"]:
                with self.assertRaisesRegex(ValueError, "STOP"):
                    aws_release.require_approval(supplied)
            aws_release.require_approval("approved-plan")

    def test_deployment_requires_committed_configuration(self):
        with patch.object(aws_release, "run", return_value=" M infra/application.json"):
            with self.assertRaisesRegex(ValueError, "must be committed"):
                aws_release.verified_deployment_commit()

    def test_deployment_requires_success_for_exact_commit(self):
        revision = "a" * 40
        for result in [[], [{"headSha": "b" * 40, "status": "completed", "conclusion": "success", "url": "synthetic"}],
                       [{"headSha": revision, "status": "queued", "conclusion": "", "url": "synthetic"}],
                       [{"headSha": revision, "status": "completed", "conclusion": "failure", "url": "synthetic"}]]:
            with patch.object(aws_release, "run", side_effect=["", revision, json.dumps(result)]):
                with self.assertRaisesRegex(ValueError, "successful CI"):
                    aws_release.verified_deployment_commit()
        success = [{"headSha": revision, "status": "completed", "conclusion": "success", "url": "synthetic"}]
        with patch.object(aws_release, "run", side_effect=["", revision, json.dumps(success)]):
            self.assertEqual(aws_release.verified_deployment_commit(), {"deployment_commit": revision, "ci_url": "synthetic"})

    def test_https_and_input_requirements(self):
        aws_release.validate_parameters(self.parameters())
        for changes in [{"HttpsMode": "http"}, {"HttpsMode": "domain"}, {"AvailabilityZoneB": "ap-south-1a"},
                        {"AvailabilityZoneA": "us-east-1a"}, {"OriginHeaderValue": "demo"}, {"TaskSize": "large"},
                        {"HealthGraceSeconds": "0"}, {"CloudFrontPrefixListId": ""}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                aws_release.validate_parameters(self.parameters(**changes))

    def test_digest_only_and_valid_fargate_sizes(self):
        pattern = self.template["Parameters"]["ImageUri"]["AllowedPattern"]
        self.assertRegex("044854093109.dkr.ecr.ap-south-1.amazonaws.com/btp-demo-app@sha256:" + "a" * 64, "^" + pattern + "$")
        self.assertNotRegex("044854093109.dkr.ecr.ap-south-1.amazonaws.com/btp-demo-app:latest", pattern)
        self.assertEqual(self.template["Mappings"]["Sizes"], {"small": {"Cpu": "256", "Memory": "512"}, "memory": {"Cpu": "256", "Memory": "1024"}, "cpu": {"Cpu": "512", "Memory": "1024"}})
        task = self.resources["Task"]["Properties"]
        self.assertEqual(task["RuntimePlatform"], {"CpuArchitecture": "X86_64", "OperatingSystemFamily": "LINUX"})
        self.assertEqual(task["RequiresCompatibilities"], ["FARGATE"])

    def test_no_direct_task_ingress_or_nat(self):
        ingress = self.resources["TaskGroup"]["Properties"]["SecurityGroupIngress"]
        self.assertEqual(ingress, [{"IpProtocol": "tcp", "FromPort": 8000, "ToPort": 8000, "SourceSecurityGroupId": {"Ref": "AlbGroup"}}])
        self.assertNotIn("AWS::EC2::NatGateway", [resource["Type"] for resource in self.resources.values()])
        self.assertEqual(self.resources["Service"]["Properties"]["NetworkConfiguration"]["AwsvpcConfiguration"]["AssignPublicIp"], "ENABLED")

    def test_health_rollback_and_readonly_runtime(self):
        service = self.resources["Service"]["Properties"]
        self.assertEqual(service["DesiredCount"], 1)
        self.assertEqual(service["DeploymentConfiguration"], {"MinimumHealthyPercent": 100, "MaximumPercent": 200, "DeploymentCircuitBreaker": {"Enable": True, "Rollback": True}})
        app = self.resources["Task"]["Properties"]["ContainerDefinitions"][1]
        self.assertTrue(app["ReadonlyRootFilesystem"])
        self.assertEqual(app["User"], "10001:10001")
        self.assertIn("/api/health", app["HealthCheck"]["Command"][-1])
        self.assertEqual(self.resources["Targets"]["Properties"]["HealthCheckPath"], "/api/ready")
        self.assertIn({"Name": "BTP_ALLOW_FIXTURE", "Value": "0"}, app["Environment"])
        self.assertEqual(app["DependsOn"], [{"ContainerName": "scratch-init", "Condition": "SUCCESS"}])

    def test_application_role_has_no_aws_permissions(self):
        role = self.resources["ApplicationRole"]["Properties"]
        self.assertNotIn("Policies", role)
        self.assertNotIn("ManagedPolicyArns", role)
        execution = json.dumps(self.resources["ExecutionRole"])
        self.assertNotIn("AdministratorAccess", execution)
        self.assertNotIn("s3:", execution)

    def test_iam_policy_sizes_and_no_wildcard_allows(self):
        for path in (aws_release.ROOT / "infra/iam").glob("*.json"):
            policy = json.loads(path.read_text())
            self.assertLessEqual(len(json.dumps(policy, separators=(",", ":"))), 6144)
            for statement in policy["Statement"]:
                if statement["Effect"] == "Allow":
                    self.assertIsInstance(statement["Action"], list)
                    self.assertTrue(all("*" not in action for action in statement["Action"]))

    def test_iam_role_boundaries_and_passrole_scope(self):
        role_policy = json.loads((aws_release.ROOT / "infra/iam/roles.json").read_text())
        statements = {statement["Sid"]: statement for statement in role_policy["Statement"]}
        role_arns = [f"arn:aws:iam::044854093109:role/btp-demo-{name}" for name in ["execution", "application"]]
        passed = statements["PassOnlyTwoBoundedRolesToEcs"]
        self.assertEqual(passed["Resource"], role_arns)
        self.assertEqual(passed["Condition"]["StringEquals"]["iam:PassedToService"], "ecs-tasks.amazonaws.com")
        for logical, suffix in [("ExecutionRole", "Execution"), ("ApplicationRole", "Application")]:
            resource = self.resources[logical]["Properties"]
            self.assertIn("arn:aws:iam::044854093109:role/" + resource["RoleName"], role_arns)
            self.assertEqual(resource["PermissionsBoundary"], f"arn:aws:iam::044854093109:policy/BtpDemo{suffix}Boundary")
            self.assertEqual(statements[f"Create{suffix}RoleOnlyWithFixedBoundary"]["Condition"]["StringEquals"]["iam:PermissionsBoundary"], resource["PermissionsBoundary"])
        self.assertEqual(statements["NeverRemoveOrReplaceBoundaries"]["Effect"], "Deny")

    def test_fixed_resource_names_match_permission_scope(self):
        self.assertEqual(self.resources["Cluster"]["Properties"]["ClusterName"], "btp-demo-cluster")
        self.assertEqual(self.resources["Service"]["Properties"]["ServiceName"], "btp-demo-app")
        self.assertEqual(self.resources["Alb"]["Properties"]["Name"], "btp-demo-alb")
        self.assertEqual(self.resources["Targets"]["Properties"]["Name"], "btp-demo-targets")
        storage = json.loads((aws_release.ROOT / "infra/bootstrap.json").read_text())
        self.assertEqual(storage["Resources"]["Artifacts"]["Properties"]["BucketName"], "btp-demo-artifacts-044854093109-ap-south-1")

    def test_infrastructure_writes_require_cloudformation_forwarding(self):
        for name in ["network", "services"]:
            policy = json.loads((aws_release.ROOT / f"infra/iam/{name}.json").read_text())
            for statement in policy["Statement"]:
                self.assertEqual(statement["Condition"]["ForAnyValue:StringEquals"]["aws:CalledVia"], ["cloudformation.amazonaws.com"])

    def test_cloudfront_origin_and_api_forwarding(self):
        distribution = self.resources["Distribution"]["Properties"]["DistributionConfig"]
        behavior = distribution["DefaultCacheBehavior"]
        self.assertEqual(behavior["CachePolicyId"], "4135ea2d-6df8-44a3-9df3-4b5a84be39ad")
        self.assertEqual(behavior["OriginRequestPolicyId"], "b689b0a8-53d0-40ab-baf2-68738e2966ac")
        self.assertIn("POST", behavior["AllowedMethods"])
        self.assertEqual(behavior["ViewerProtocolPolicy"], "redirect-to-https")
        self.assertEqual(distribution["Origins"][0]["CustomOriginConfig"]["OriginProtocolPolicy"], "http-only")
        self.assertTrue(self.template["Parameters"]["OriginHeaderValue"]["NoEcho"])
        self.assertEqual(self.resources["Http"]["Properties"]["DefaultActions"]["Fn::If"][2][0]["FixedResponseConfig"]["StatusCode"], "403")

    def test_private_retained_artifact_storage(self):
        storage = json.loads((aws_release.ROOT / "infra/bootstrap.json").read_text())["Resources"]
        self.assertEqual(storage["Repository"]["Properties"]["ImageTagMutability"], "IMMUTABLE")
        bucket = storage["Artifacts"]
        self.assertEqual(bucket["DeletionPolicy"], "Retain")
        self.assertTrue(all(bucket["Properties"]["PublicAccessBlockConfiguration"].values()))
        self.assertEqual(bucket["Properties"]["VersioningConfiguration"]["Status"], "Enabled")
        self.assertIn("aws:SecureTransport", json.dumps(storage["ArtifactsPolicy"]))

    def test_stable_service_with_rolled_back_definition_is_rejected(self):
        deployed = {"Cluster": "synthetic-cluster", "Service": "synthetic-service", "TaskDefinition": "expected-definition"}
        service = {"taskDefinition": "older-definition", "runningCount": 1, "pendingCount": 0}
        with patch.object(aws_release, "outputs", return_value=deployed), patch.object(aws_release, "aws", side_effect=["", json.dumps({"services": [service]})]):
            with self.assertRaisesRegex(ValueError, "possible rollback"):
                aws_release.verify_service({"image_uri": "synthetic-expected", "platform_digests": ["synthetic-new"]})

    def test_healthy_service_with_wrong_running_digest_is_rejected(self):
        deployed = {"Cluster": "synthetic-cluster", "Service": "synthetic-service", "TaskDefinition": "expected-definition"}
        service = {"taskDefinition": "expected-definition", "runningCount": 1, "pendingCount": 0}
        task = {"taskDefinitionArn": "expected-definition", "containers": [{"name": "app", "imageDigest": "synthetic-old", "image": "synthetic-expected", "healthStatus": "HEALTHY"}]}
        responses = ["", json.dumps({"services": [service]}), json.dumps({"taskArns": ["synthetic-task"]}), json.dumps({"tasks": [task]})]
        with patch.object(aws_release, "outputs", return_value=deployed), patch.object(aws_release, "aws", side_effect=responses):
            with self.assertRaisesRegex(ValueError, "intended immutable release"):
                aws_release.verify_service({"image_uri": "synthetic-expected", "platform_digests": ["synthetic-new"]})


if __name__ == "__main__":
    unittest.main()
