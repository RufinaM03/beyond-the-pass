"""Synthetic update guards; no AWS calls or real artifact requirements."""

from datetime import timedelta
import hashlib
import unittest

from scripts import aws_app_update as update


class AppUpdateTests(unittest.TestCase):
    def test_plan_and_original_deadline_are_required(self):
        approved = hashlib.sha256(update.PLAN.read_bytes()).hexdigest()
        update.require_update_approval(approved, update.DEADLINE - timedelta(seconds=1))
        for digest, moment in [(None, update.DEADLINE - timedelta(seconds=1)), (approved, update.DEADLINE),
                               (approved, update.DEADLINE + timedelta(seconds=1))]:
            with self.assertRaises(ValueError):
                update.require_update_approval(digest, moment)

    def test_only_image_and_code_values_sent_all_other_parameters_preserved(self):
        parameters = [{"ParameterKey": name, "ParameterValue": "synthetic-private-marker"}
                      for name in ["ImageUri", "CodeVersion", "OriginHeaderValue", "OriginHeaderName", "TaskSize"]]
        result = update.parameter_update(parameters, "synthetic-image", "synthetic-code")
        self.assertNotIn("synthetic-private-marker", str(result))
        self.assertTrue(all(entry.get("UsePreviousValue") for entry in result[2:]))
        self.assertEqual(result[0], {"ParameterKey": "ImageUri", "ParameterValue": "synthetic-image"})
        with self.assertRaises(ValueError):
            update.parameter_update(parameters + [parameters[0]], "image", "code")

    def test_changeset_cannot_add_infrastructure_or_replace_service(self):
        changes = [{"ResourceChange": {"LogicalResourceId": name, "ResourceType": kind, "Action": "Modify", "Replacement": replacement}}
                   for name, kind, replacement in [("Task", "AWS::ECS::TaskDefinition", "True"), ("Service", "AWS::ECS::Service", "False")]]
        update.validate_changes(changes)
        for changed in [changes[:1], changes + [{"ResourceChange": {"LogicalResourceId": "Extra"}}],
                        [changes[0], {"ResourceChange": {**changes[1]["ResourceChange"], "Replacement": "True"}}],
                        [changes[0], changes[0]]]:
            with self.assertRaises(ValueError):
                update.validate_changes(changed)
