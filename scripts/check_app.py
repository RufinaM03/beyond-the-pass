"""Explicit local integration check using the approved real release, never fitting."""

import json
import math
from contextlib import closing

from fastapi.testclient import TestClient

from backend.app import ROOT, app
from pipeline.serving import open_snapshot


def main():
    with TestClient(app) as client:
        assert client.get('/api/ready').status_code == 200
        versions = client.get('/api/versions').json()
        assert versions['demo_cases'] == 200 and versions['evaluation_examples'] == 936
        before = client.get('/api/evaluation').json()
        ranked = client.get('/api/queue?capacity=500&limit=100').json()
        tail = client.get('/api/queue?capacity=500&limit=100&offset=100').json()
        cases = ranked['items'] + tail['items']
        assert ranked['selected'] == 200 and ranked['exceeds_available']
        assert len({row['case_id'] for row in cases}) == 200
        assert cases == sorted(cases, key=lambda row: (-row['exploratory_prioritization_score'], row['case_id']))
        with closing(open_snapshot(ROOT / 'artifacts/releases/btp-exploratory-v1/snapshot.sqlite3')) as connection:
            stored = dict(connection.execute('SELECT case_id,prediction_json FROM followup_queue'))
        for row in cases:
            detail = client.get('/api/cases/' + row['case_id']).json()
            prediction = client.post('/api/predict', json=detail['inputs']).json()
            assert prediction == detail['prediction'] == json.loads(stored[row['case_id']])
            assert prediction['status'] == 'scored'
            assert list(detail['inputs']['features']) == ['vehicle_age_years', 'mileage', 'brake_advisory_count', 'advisory_count']
            assert detail['history_available_through'] == detail['index_date']
            assert detail['history']['model_input'] is False
            explanation = prediction['explanation']
            margin = explanation['intercept_log_odds'] + sum(term['log_odds_contribution'] for term in explanation['terms'])
            assert math.isclose(100 / (1 + math.exp(-margin)), row['exploratory_prioritization_score'], abs_tol=1e-10)
        assert before == client.get('/api/evaluation').json()
        observed = before['primary_temporal']['logistic']
        assert (observed['examples'], observed['positive'], observed['negative']) == (936, 76, 860)
        for method in before['primary_temporal'].values():
            for point in method['capacities']:
                assert point['precision'] == point['true_positives'] / point['selected']
                assert point['recall'] == point['true_positives'] / point['all_positives']
        for path in ['/', '/queue', '/evaluation']:
            response = client.get(path)
            assert response.status_code == 200 and '<div id="root">' in response.text
        for path in ['/api/missing', '/assets/missing.js', '/missing.css']:
            assert client.get(path).status_code == 404
        print('REAL integration: 200 exact prediction/explanation agreements; deterministic ranking; 936-example saved evaluation unchanged; production SPA boundaries passed.')


if __name__ == '__main__':
    main()
