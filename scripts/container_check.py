"""Smoke one owned, read-only container; stop it in finally, including failures."""

import argparse
import json
import subprocess
import time
import uuid
from contextlib import closing
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pipeline.serving import open_snapshot
from pipeline.sources import save_json
from scripts.package_release import validate_context


def docker(*arguments):
    return subprocess.check_output(['docker', *arguments], text=True, timeout=60).strip()


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in {'src', 'href'} and value.startswith('/assets/'):
                self.paths.append(value)


def request(base, path, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {'Content-Type': 'application/json'} if body else {}
    try:
        with urlopen(Request(base + path, data=body, headers=headers), timeout=5) as response:
            content = response.read()
            return response.status, content
    except HTTPError as error:
        return error.code, error.read()


def check(image, mode, context, output):
    resource = validate_context(context, mode)
    report = {'mode': mode, 'fixture': mode == 'fixture', 'image': image, 'platform': 'linux/amd64', 'observations_not_capacity_guarantee': True}
    name = 'btp-check-' + uuid.uuid4().hex[:12]
    started = time.perf_counter()
    running = False
    try:
        docker('run', '--detach', '--rm', '--name', name, '--platform', 'linux/amd64', '--read-only',
               '--tmpfs', '/tmp/btp:rw,noexec,nosuid,size=64m,mode=1777', '--cap-drop', 'ALL',
               '--security-opt', 'no-new-privileges', '--pids-limit', '128', '--memory', '512m', '--cpus', '1',
               '--env', 'BTP_ALLOW_FIXTURE=' + ('1' if mode == 'fixture' else '0'), '-p', '127.0.0.1::8000', image)
        running = True
        port = docker('port', name, '8000/tcp').split(':')[-1]
        base = 'http://127.0.0.1:' + port
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                if request(base, '/api/ready')[0] == 200:
                    break
            except (URLError, TimeoutError, ConnectionError):
                pass
            time.sleep(0.5)
        else:
            raise AssertionError('Container did not become artifact-ready within 90 seconds')
        report['start_to_ready_seconds'] = round(time.perf_counter() - started, 3)
        assert request(base, '/api/health')[0] == 200
        versions = json.loads(request(base, '/api/versions')[1])
        assert versions['fixture'] == (mode == 'fixture')
        assert versions['model_version'] == resource.bundle['version']
        assert versions['demo_cases'] == resource.count
        assert versions['evaluation_examples'] == resource.metrics['primary_temporal']['logistic']['examples']
        before = json.loads(request(base, '/api/evaluation')[1])
        assert before == resource.metrics
        rows = []
        for offset in range(0, resource.count, 100):
            queue = json.loads(request(base, f'/api/queue?capacity=500&limit=100&offset={offset}')[1])
            assert queue['selected'] == resource.count and queue['exceeds_available']
            rows.extend(queue['items'])
        assert rows == sorted(rows, key=lambda row: (-row['exploratory_prioritization_score'], row['case_id']))
        assert len({row['case_id'] for row in rows}) == resource.count
        assert request(base, '/api/queue?capacity=501')[0] == 422
        assert request(base, '/api/queue?limit=101')[0] == 422
        assert json.loads(request(base, '/api/queue?capacity=0')[1])['items'] == []
        case_id = rows[0]['case_id']
        detail = json.loads(request(base, '/api/cases/' + case_id)[1])
        actual = json.loads(request(base, '/api/predict', detail['inputs'])[1])
        with closing(open_snapshot(Path(context) / 'release/snapshot.sqlite3')) as connection:
            stored = json.loads(connection.execute('SELECT prediction_json FROM followup_queue WHERE case_id=?', (case_id,)).fetchone()[0])
        assert actual == detail['prediction'] == stored
        assert detail['history_available_through'] == detail['index_date']
        assert detail['history']['model_input'] is False
        assert 'Aggregate prior records only' in detail['history_resolution']
        assert 'dated inspections and item descriptions are not exported' in detail['history_resolution']
        assert request(base, '/api/cases/eeeeeeeeeeeeeeee')[0] == 404
        assert request(base, '/api/predict', {'features': {'future_outcome': 1}})[0] == 422
        missing = json.loads(json.dumps(detail['inputs']))
        missing['features']['mileage'] = None
        missing['features']['vehicle_age_years'] = None
        assert json.loads(request(base, '/api/predict', missing)[1])['status'] == 'insufficient_data'
        assert before == json.loads(request(base, '/api/evaluation')[1])
        for path in ['/', '/queue', '/cases/' + case_id, '/evaluation', '/methodology']:
            status, body = request(base, path)
            assert status == 200 and b'<div id="root">' in body
        parser = Assets()
        parser.feed(request(base, '/')[1].decode())
        assert len(parser.paths) >= 2
        javascript = ''
        for path in parser.paths:
            status, body = request(base, path)
            assert status == 200 and len(body) > 0
            if path.endswith('.js'):
                javascript += body.decode()
        assert 'aggregate prior' in javascript.lower() or 'aggregate history' in javascript.lower()
        assert 'SYNTHETIC CI FIXTURE' in javascript
        for path in ['/api/missing', '/assets/missing.js', '/missing.css']:
            assert request(base, path)[0] == 404
        inspect = json.loads(docker('image', 'inspect', image))[0]
        assert inspect['Architecture'] == 'amd64' and inspect['Os'] == 'linux'
        assert inspect['Config']['User'] == '10001:10001'
        assert inspect['Config']['Labels']['io.btp.artifact.kind'] == mode
        read_only = subprocess.run(['docker', 'exec', name, 'python', '-c',
                                   "import os; from pipeline.serving import open_snapshot; from pathlib import Path; open_snapshot(Path('/app/release/snapshot.sqlite3')).execute('CREATE TABLE must_not_exist(value TEXT)')"], capture_output=True, text=True, timeout=15)
        assert read_only.returncode != 0 and 'readonly' in read_only.stderr.lower()
        report.update({'image_id': inspect['Id'], 'image_size_bytes': inspect['Size'], 'versions': versions,
                       'sample_case_id': case_id, 'score_agrees_with_staged_artifact': True,
                       'deterministic_ranked_cases': len(rows), 'aggregate_only_history': True,
                       'readonly_sqlite': True, 'stats_observation': json.loads(docker('stats', '--no-stream', '--format', '{{json .}}', name)),
                       'checks': 'readiness/version/frontend/assets/case prediction/bounds/errors/scope/history/readonly all passed'})
    except Exception:
        if running:
            print(docker('logs', '--tail', '30', name))
        raise
    finally:
        if running:
            docker('stop', '--time', '25', name)
            report['verification_container_stopped'] = True
        save_json(output, report)
    print(json.dumps(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--mode', choices=['release', 'fixture'], default='release')
    parser.add_argument('--context', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    check(args.image, args.mode, args.context, args.output)


if __name__ == '__main__':
    main()
