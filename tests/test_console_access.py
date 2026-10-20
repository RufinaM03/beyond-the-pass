"""Offline policy guards and explicitly synthetic diagnostic responses."""

import json
import subprocess
import unittest
from unittest.mock import patch

from scripts import check_console_access as viewer


class ConsoleAccessTests(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads((viewer.ROOT / "infra/iam/console-view-supplement.json").read_text())

    def test_supplement_is_bounded_and_only_named_view_actions(self):
        self.assertLessEqual(len(json.dumps(self.policy, separators=(",", ":"))), 6144)
        for statement in self.policy["Statement"]:
            self.assertEqual(statement["Effect"], "Allow")
            for action in statement["Action"]:
                service, operation = action.split(":")
                self.assertNotIn("*", action)
                self.assertIn(service, {"cloudformation", "ecs", "cloudfront", "cloudwatch", "ecr", "logs", "s3", "iam"})
                self.assertTrue(operation.startswith(("Get", "Describe", "List", "Filter")))
                self.assertNotIn(action, {"s3:GetObject", "s3:GetObjectVersion", "ecr:GetAuthorizationToken", "ecr:GetDownloadUrlForLayer"})

    def test_regional_and_cluster_scope_and_actual_stack_ids(self):
        statements = {statement["Sid"]: statement for statement in self.policy["Statement"]}
        regional = statements["RegionalConsoleDiscoveryAndClassicMetricReads"]
        self.assertEqual(regional["Resource"], "*")
        self.assertEqual(regional["Condition"]["StringEquals"]["aws:RequestedRegion"], "ap-south-1")
        services = statements["ListServicesOnlyForProjectCluster"]
        self.assertEqual(services["Condition"]["ArnEquals"]["ecs:cluster"], viewer.CLUSTER)
        stack_resources = statements["DescribeActualProjectStackResources"]["Resource"]
        self.assertEqual(len(stack_resources), 2)
        self.assertTrue(all("*" not in resource and ":044854093109:stack/btp-demo-" in resource for resource in stack_resources))
        self.assertEqual(statements["ProjectBucketConfigurationWithoutObjectContent"]["Resource"], "arn:aws:s3:::" + viewer.BUCKET)
        self.assertEqual(statements["InspectOnlyDev1AccessMetadata"]["Resource"], viewer.PRINCIPAL)

    def test_denial_attribution_does_not_invent_account_controls(self):
        self.assertIn("missing identity-based", viewer.denial_kind("because no identity-based policy allows the action"))
        self.assertIn("service-control-policy", viewer.denial_kind("explicit deny in a service control policy"))
        self.assertIn("permissions-boundary", viewer.denial_kind("no permissions boundary allows this action"))
        self.assertIn("not established", viewer.denial_kind("Access denied"))

    def test_synthetic_error_redacts_origin_fields_and_never_emits_bodies(self):
        name = "X-Btp-" + "a" * 24
        secret = "b" * 64
        error = f"An error occurred (AccessDenied) when calling the GetDistributionConfig operation: denied {name} {secret}"
        with patch.object(viewer.subprocess, "run", return_value=subprocess.CompletedProcess([], 254, "synthetic raw body", error)):
            result, body = viewer.invoke("synthetic", "cloudfront", "get-distribution-config", [], "DistributionConfig.Enabled")
        self.assertEqual(result["status"], "denied")
        self.assertIsNone(body)
        self.assertNotIn(name, json.dumps(result))
        self.assertNotIn(secret, json.dumps(result))
        self.assertNotIn("synthetic raw body", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
