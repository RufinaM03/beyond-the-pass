"""Isolated synthetic HTTP fixtures; these are not evaluation evidence."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from backend.app import ROOT, Release, create_app
from pipeline.serving import open_snapshot, predict_case
from test_modeling import payload, synthetic_bundle


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = synthetic_bundle()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / "data/tmp")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.snapshot = self.directory / "synthetic.sqlite3"
        self.frontend = self.directory / "dist"
        (self.frontend / "assets").mkdir(parents=True)
        (self.frontend / "index.html").write_text('<html><div id="root">Synthetic production build</div></html>')
        self.request = payload()
        with closing(sqlite3.connect(self.snapshot)) as connection:
            connection.executescript("CREATE TABLE followup_queue(case_id TEXT PRIMARY KEY,index_date TEXT,inputs_json TEXT,prediction_json TEXT); CREATE TABLE descriptive_history(case_id TEXT PRIMARY KEY,history_json TEXT)")
            for index in range(3):
                case_id = f"{index:016x}"
                connection.execute("INSERT INTO followup_queue VALUES(?,?,?,?)", (case_id, f"2024-01-0{index + 1}", json.dumps(self.request), json.dumps(predict_case(self.bundle, self.request))))
                connection.execute("INSERT INTO descriptive_history VALUES(?,?)", (case_id, json.dumps({"prior_recorded_tests": index, "prior_brake_advisory_tests": index, "model_input": False})))
            insufficient = payload()
            insufficient["features"]["mileage"] = None
            insufficient["features"]["vehicle_age_years"] = None
            connection.execute("INSERT INTO followup_queue VALUES(?,?,?,?)", ("f" * 16, "2024-01-04", json.dumps(insufficient), json.dumps(predict_case(self.bundle, insufficient))))
            connection.execute("INSERT INTO descriptive_history VALUES(?,?)", ("f" * 16, '{}'))
            connection.commit()
        self.metrics = {"version": "synthetic", "primary_temporal": {"logistic": {"examples": 8, "positive": 2, "negative": 6}}}
        self.resource = SimpleNamespace(bundle=self.bundle, count=4, connect=lambda: open_snapshot(self.snapshot),
                                        descriptor={"queue_as_of": "2024-12-31", "release_manifest_sha256": "synthetic", "status": "synthetic"},
                                        metadata={"history_starts": "2022-01-01"}, metrics=self.metrics)
        self.loader = Mock(return_value=self.resource)
        self.client = TestClient(create_app(frontend_path=self.frontend, release_loader=self.loader))
        self.client.__enter__()
        self.addCleanup(lambda: self.client.__exit__(None, None, None))

    def test_health_versions_and_one_load(self):
        self.assertEqual(self.client.get('/api/health').json(), {"status": "alive"})
        self.assertEqual(self.client.get('/api/ready').status_code, 200)
        versions = self.client.get('/api/versions').json()
        self.assertEqual((versions['demo_cases'], versions['evaluation_examples']), (4, 8))
        self.client.get('/api/queue')
        self.loader.assert_called_once()

    def test_public_surface_has_no_artifact_admin_or_write_endpoints(self):
        for path in ['/release/bundle.joblib', '/release/descriptor.json', '/artifacts/releases/btp-exploratory-v1/snapshot.sqlite3',
                     '/.env', '/.aws/credentials', '/admin', '/docs', '/redoc', '/api/upload', '/api/train', '/api/deploy']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)
        for path in ['/api/upload', '/api/train', '/api/deploy', '/api/cases', '/api/queue']:
            self.assertIn(self.client.post(path, json={}).status_code, {404, 405})
        for path in ['/api/queue?capacity=1', '/api/evaluation', '/api/cases?limit=1']:
            self.assertEqual(self.client.get(path).headers['cache-control'], 'no-store')
        self.assertEqual(self.client.post('/api/predict', json={'model_path': '/tmp/untrusted.joblib', 'code': 'print(1)'}).status_code, 422)

    def test_case_pagination_and_dates(self):
        first = self.client.get('/api/cases?limit=2').json()
        second = self.client.get('/api/cases?limit=2&offset=2').json()
        self.assertEqual(first['total'], 4)
        self.assertFalse({row['case_id'] for row in first['items']} & {row['case_id'] for row in second['items']})
        self.assertEqual(self.client.get('/api/cases?date_from=2024-01-02&date_to=2024-01-03').json()['total'], 2)
        self.assertEqual(self.client.get('/api/cases?offset=100').json()['items'], [])

    def test_input_bounds_and_unknown_case(self):
        for query in ['limit=0', 'limit=101', 'offset=-1', 'offset=10001', 'date_from=no', 'date_from=2024-02-01&date_to=2024-01-01']:
            self.assertEqual(self.client.get('/api/cases?' + query).status_code, 422)
        for query in ['capacity=-1', 'capacity=501', 'capacity=1.5', 'limit=101']:
            self.assertEqual(self.client.get('/api/queue?' + query).status_code, 422)
        for case_id in ['unknown', 'e' * 16, "' OR 1=1--"]:
            self.assertEqual(self.client.get('/api/cases/' + case_id).status_code, 404)

    def test_agreement_and_prediction_states(self):
        expected = predict_case(self.bundle, self.request)
        self.assertEqual(self.client.post('/api/predict', json=self.request).json(), expected)
        self.assertEqual(self.client.get('/api/cases/' + '0' * 16 + '/prediction').json(), expected)
        insufficient = self.client.get('/api/cases/' + 'f' * 16 + '/prediction')
        self.assertEqual(insufficient.status_code, 200)
        self.assertEqual(insufficient.json()['status'], 'insufficient_data')
        self.assertIsNone(insufficient.json()['exploratory_prioritization_score'])
        self.assertEqual(self.client.post('/api/predict', json={}).status_code, 422)
        self.assertEqual(self.client.post('/api/predict', content='{bad').status_code, 422)
        self.assertEqual(self.client.post('/api/predict', content='x' * 16385).status_code, 413)

    def test_deterministic_outcome_independent_ties_and_overcapacity(self):
        first = self.client.get('/api/queue?capacity=500').json()
        second = self.client.get('/api/queue?capacity=500').json()
        self.assertEqual(first, second)
        self.assertEqual(first['selected'], 3)
        self.assertEqual(first['unscored'], 1)
        self.assertTrue(first['exceeds_available'])
        self.assertEqual([row['case_id'] for row in first['items']], [f'{index:016x}' for index in range(3)])
        self.assertEqual(self.client.get('/api/queue?capacity=0').json()['items'], [])
        self.assertEqual(self.client.get('/api/queue?capacity=2&offset=2').json()['items'], [])

    def test_future_outcomes_rejected_and_descriptive_history_not_scored(self):
        before = self.client.get('/api/cases/' + '0' * 16).json()
        for forbidden in ['label', 'next_test_result', 'postcode', 'vehicle_id', 'recurrence']:
            changed = payload()
            changed['features'][forbidden] = 1
            self.assertEqual(self.client.post('/api/predict', json=changed).status_code, 422)
        with closing(sqlite3.connect(self.snapshot)) as connection:
            connection.execute('UPDATE descriptive_history SET history_json=? WHERE case_id=?', (json.dumps({'prior_brake_advisory_tests': 99, 'model_input': False}), '0' * 16))
            connection.commit()
        after = self.client.get('/api/cases/' + '0' * 16).json()
        self.assertEqual(before['prediction'], after['prediction'])
        self.assertEqual(after['history_available_through'], after['index_date'])
        queue = self.client.get('/api/queue').text
        for forbidden in ['next_test', 'label', 'history_json']:
            self.assertNotIn(forbidden, queue)

    def test_evaluation_unchanged_by_demo_capacity(self):
        before = self.client.get('/api/evaluation').json()
        self.client.get('/api/queue?capacity=1')
        self.client.get('/api/queue?capacity=500')
        self.assertEqual(before, self.client.get('/api/evaluation').json())
        self.assertEqual(before, self.metrics)

    def test_production_spa_does_not_swallow_api_or_asset_errors(self):
        for path in ['/', '/queue', '/evaluation', '/methodology', '/cases/' + '0' * 16]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn('Synthetic production build', response.text)
        for path in ['/api', '/api/unknown', '/assets/unknown.js', '/unknown.css', '/unknown']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 404)
            self.assertNotIn('Synthetic production build', response.text)

    def test_unavailable_artifacts_fail_closed_but_health_remains_live(self):
        with self.assertLogs('backend.app', level='ERROR'):
            with TestClient(create_app(release_loader=Mock(side_effect=ValueError('synthetic checksum mismatch')))) as client:
                self.assertEqual(client.get('/api/health').status_code, 200)
                for path in ['/api/ready', '/api/versions', '/api/queue', '/api/evaluation']:
                    self.assertEqual(client.get(path).status_code, 503)
                self.assertEqual(client.post('/api/predict', json=self.request).status_code, 503)

    def test_feature_schema_mismatch_refused_before_snapshot_use(self):
        descriptor = self.directory / 'descriptor.json'
        descriptor.write_text(json.dumps({'directory': str(self.directory), 'release_manifest_sha256': 'synthetic'}))
        (self.directory / 'feature-schema.json').write_text(json.dumps({'version': 'synthetic', 'features': ['future_label']}))
        with patch('backend.app.load_release', return_value=(self.bundle, {})):
            with self.assertRaisesRegex(ValueError, 'Feature schema'):
                Release(descriptor)

    def test_missing_frontend_build_and_offline_api_schema(self):
        with TestClient(create_app(frontend_path=self.directory / 'missing', release_loader=self.loader)) as client:
            self.assertEqual(client.get('/').status_code, 503)
            self.assertEqual(client.get('/assets/missing.js').status_code, 404)
            schema = client.get('/api/openapi.json')
            self.assertEqual(schema.status_code, 200)
            self.assertIn('/api/predict', schema.json()['paths'])
