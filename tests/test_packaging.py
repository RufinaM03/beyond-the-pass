"""Synthetic-only packaging fixtures; never real model/evaluation evidence."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app import Release
from pipeline.sources import ROOT
from scripts.package_release import stage, validate_bundle, validate_context


class PackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = ROOT / 'data/package'
        cls.parent.mkdir(parents=True, exist_ok=True)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=self.parent)
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name) / 'fixture'
        self.report = stage(self.output, 'fixture', 'synthetic-test-revision')

    def test_fixture_is_bounded_visibly_synthetic_and_compatible(self):
        resource = validate_context(self.output, 'fixture', code_version='synthetic-test-revision', artifact_version='fixture-ci-v1')
        self.assertEqual(resource.count, 4)
        self.assertTrue(resource.metrics['fixture'])
        self.assertLess(self.report['bytes'], 1024 * 1024)
        self.assertEqual(resource.bundle['data_version'], 'synthetic-ci-only')
        with patch.dict('os.environ', {'BTP_ALLOW_FIXTURE': '0'}):
            with self.assertRaisesRegex(ValueError, 'explicit'):
                Release(self.output / 'release/descriptor.json')

    def test_production_gate_rejects_fixture_before_unpickling_even_if_opted_in(self):
        with patch.dict('os.environ', {'BTP_ALLOW_FIXTURE': '1'}), patch('pipeline.serving.joblib.load') as unpickle:
            with self.assertRaisesRegex(ValueError, 'rejects synthetic'):
                validate_bundle(self.output, 'release')
            unpickle.assert_not_called()

    def test_context_tampering_and_unrelated_files_are_rejected(self):
        extra = self.output / '.env'
        extra.write_text('SYNTHETIC_NOT_A_SECRET=fixture')
        with self.assertRaisesRegex(ValueError, 'context files'):
            validate_context(self.output, 'fixture')
        extra.unlink()
        target = self.output / 'frontend/src/main.jsx'
        target.write_bytes(target.read_bytes() + b'\nsynthetic modification')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            validate_context(self.output, 'fixture')

    def test_relabelled_fixture_and_wrong_image_metadata_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Image revision'):
            validate_bundle(self.output, 'fixture', code_version='incorrect')
        descriptor = self.output / 'release/descriptor.json'
        payload = json.loads(descriptor.read_text())
        payload['fixture'] = False
        descriptor.write_text(json.dumps(payload))
        package = self.output / 'package-manifest.json'
        payload = json.loads(package.read_text())
        payload['mode'] = 'release'
        package.write_text(json.dumps(payload))
        with patch('pipeline.serving.joblib.load') as unpickle:
            with self.assertRaisesRegex(ValueError, 'approved production'):
                validate_bundle(self.output, 'release')
            unpickle.assert_not_called()

    def test_stage_refuses_overwrite_and_paths_outside_ignored_package_area(self):
        with self.assertRaisesRegex(ValueError, 'already exists'):
            stage(self.output, 'fixture')
        with self.assertRaisesRegex(ValueError, 'ignored'):
            stage(ROOT / 'fixture-must-not-be-created', 'fixture')
