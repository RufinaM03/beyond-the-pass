"""Synthetic CD security/failure fixtures, never real model performance."""

import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from scripts import cd_release as cd


class CdReleaseTests(unittest.TestCase):
    def test_actual_immutable_subject_contract_rejects_legacy_or_customized_trust(self):
        trust = json.loads((cd.ROOT / "infra/iam/github-deploy-trust.json").read_text())
        settings = {"use_default": True, "use_immutable_subject": True,
                    "sub_claim_prefix": "repo:RufinaM03@162699034/beyond-the-pass@1425804589"}
        self.assertEqual(cd.verify_oidc_subject(settings, trust), settings["sub_claim_prefix"] + ":ref:refs/heads/main")
        for changed in [{**settings, "use_default": False}, {**settings, "sub_claim_prefix": "repo:other@1/repository@2"}]:
            with self.assertRaises(ValueError):
                cd.verify_oidc_subject(changed, trust)
        legacy = json.loads(json.dumps(trust))
        legacy["Statement"][0]["Condition"]["StringEquals"]["token.actions.githubusercontent.com:sub"] = "repo:RufinaM03/beyond-the-pass:ref:refs/heads/main"
        with self.assertRaises(ValueError):
            cd.verify_oidc_subject(settings, legacy)

    def test_untrusted_archive_rejected_before_any_extraction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "untrusted.tar.gz"
            archive.write_bytes(b"synthetic not a trusted archive")
            with self.assertRaises(ValueError):
                cd.restore_archive(archive, root / "release")
            self.assertFalse((root / "release").exists())

    def test_even_checksum_matched_archive_cannot_traverse_or_link(self):
        for name, link in [("../escape", False), ("release/bundle.joblib", True)]:
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                archive = root / "synthetic.tar.gz"
                with tarfile.open(archive, "w:gz") as bundle:
                    entry = tarfile.TarInfo(name)
                    if link:
                        entry.type = tarfile.SYMTYPE
                        entry.linkname = "../../escape"
                        bundle.addfile(entry)
                    else:
                        entry.size = 4
                        bundle.addfile(entry, io.BytesIO(b"fake"))
                approved = {**cd.ARTIFACTS, "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}
                with patch.dict(cd.ARTIFACTS, approved):
                    with self.assertRaises(ValueError):
                        cd.restore_archive(archive, root / "release")
                self.assertFalse((root / "release").exists())

    def test_gate_requires_full_sha_and_exact_head(self):
        with self.assertRaises(ValueError):
            cd.gate("main")
        with patch.object(cd, "run", return_value="b" * 40):
            with self.assertRaises(ValueError):
                cd.gate("a" * 40)

    def test_gate_rejects_failed_or_pull_request_only_ci(self):
        sha = "a" * 40
        for event, conclusion in [("pull_request", "success"), ("push", "failure")]:
            responses = [sha, "", json.dumps({"sha": sha}), json.dumps([{"headSha": sha, "headBranch": "main", "event": event,
                          "status": "completed", "conclusion": conclusion}])]
            with patch.object(cd, "run", side_effect=responses):
                with self.assertRaises(ValueError):
                    cd.gate(sha)

    def test_proposed_oidc_is_only_main_and_no_new_admin_or_s3_writes(self):
        trust = json.loads((cd.ROOT / "infra/iam/github-deploy-trust.json").read_text())
        condition = trust["Statement"][0]["Condition"]["StringEquals"]
        self.assertEqual(condition["token.actions.githubusercontent.com:sub"], "repo:RufinaM03@162699034/beyond-the-pass@1425804589:ref:refs/heads/main")
        self.assertEqual(condition["token.actions.githubusercontent.com:aud"], "sts.amazonaws.com")
        policy = json.loads((cd.ROOT / "infra/iam/github-deploy-permissions.json").read_text())
        actions = {action for entry in policy["Statement"] for action in ([entry["Action"]] if isinstance(entry["Action"], str) else entry["Action"])}
        self.assertNotIn("*", actions)
        self.assertEqual({action for action in actions if action.startswith("s3:")}, {"s3:GetObject"})
        self.assertEqual({action for action in actions if action.startswith("iam:")}, {"iam:PassRole", "iam:GetRole", "iam:GetRolePolicy"})
        self.assertFalse({"cloudformation:DeleteStack", "ecs:CreateService", "ecs:DeleteService"} & actions)

    def test_obsolete_automatic_commit_is_not_deployed(self):
        sha = "a" * 40
        with patch.object(cd, "run", side_effect=[sha, "", json.dumps({"sha": "b" * 40})]):
            with self.assertRaisesRegex(ValueError, "Obsolete"):
                cd.gate(sha)

    def test_manual_commit_must_be_on_main_history(self):
        sha = "a" * 40
        with patch.object(cd, "run", side_effect=[sha, "", json.dumps({"sha": "b" * 40}), json.dumps({"status": "diverged"})]):
            with self.assertRaisesRegex(ValueError, "main history"):
                cd.gate(sha, allow_older=True)

    def test_workflow_never_runs_pr_cd_or_cancels_active_rollout(self):
        workflow = (cd.ROOT / ".github/workflows/deploy.yml").read_text()
        for required in ["workflow_run:", "workflow_dispatch:", "head_repository.full_name == github.repository",
                         "head_branch == 'main'", "conclusion == 'success'", "cancel-in-progress: false",
                         "id-token: write", "scripts.cd_release gate", "scripts.cd_release verify"]:
            self.assertIn(required, workflow)
        self.assertNotIn("continue-on-error", workflow)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", workflow)
        self.assertNotIn("pull_request:", workflow)
