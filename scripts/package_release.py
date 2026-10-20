"""Explicit bounded staging and fail-closed real/fixture release validation."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from backend.app import HISTORY_FIELDS, Release
from pipeline.serving import MODEL_FEATURES, clean_features, predict_case
from pipeline.sources import ROOT, checksum, save_json


FIXTURE_VERSION = "fixture-ci-v1"
SOURCE_FILES = ["Dockerfile", ".dockerignore", "requirements-app.lock", "requirements-model.lock", "requirements-data.lock",
                "backend/__init__.py", "backend/app.py", "backend/manual.py", "pipeline/__init__.py", "pipeline/serving.py", "pipeline/pilot.py",
                "pipeline/sources.py", "scripts/package_release.py", "frontend/package.json", "frontend/package-lock.json", "frontend/index.html"]
RELEASE_FILES = {"bundle.joblib", "feature-schema.json", "metrics.json", "model-card.md", "protocol.json",
                 "split-audit.json", "release-manifest.json", "snapshot.sqlite3", "descriptor.json"}


def fixture(directory):
    import joblib
    import pandas as pd
    from pipeline.modeling import PACKAGES, evaluate, fixed_pipeline

    directory.mkdir()
    rows = pd.DataFrame([[5, 10000, 1, 2], [10, 20000, 2, 3], [15, None, 3, 3], [20, 40000, 4, 5]], columns=MODEL_FEATURES)
    protocol = {"version": FIXTURE_VERSION, "status": "SYNTHETIC CI FIXTURE; NOT REAL EVALUATION",
                "training_indices": ["2022-01-01", "2022-03-31"], "evaluation_indices": ["2023-07-01", "2023-09-30"],
                "freeze": "2023-07-01T00:00:00Z", "observation_end": "2024-12-31", "capacities": [0.1, 0.2, 0.3],
                "logistic": {"C": 1.0, "solver": "lbfgs", "max_iter": 1000, "tol": 0.0001, "class_weight": None, "random_state": 2026}}
    model = fixed_pipeline(protocol)
    model.fit(clean_features(rows), [0, 0, 1, 1])
    bundle = {"version": FIXTURE_VERSION, "data_version": "synthetic-ci-only", "features": MODEL_FEATURES, "pipeline": model,
              "training_ranges": {column: [float(rows[column].min()), float(rows[column].max())] for column in rows}}
    joblib.dump(bundle, directory / "bundle.joblib")
    save_json(directory / "feature-schema.json", {"version": FIXTURE_VERSION, "features": MODEL_FEATURES, "fixture": True})
    frame = pd.DataFrame({"test_id": [1, 2, 3, 4], "vehicle_id": [1, 2, 3, 4], "label": [0, 0, 1, 1]})
    probabilities = model.predict_proba(clean_features(rows))[:, 1]
    methods = {"training_prevalence": evaluate(frame, [0.5] * 4, [0.5] * 4, protocol["capacities"]),
               "brakes_advisory_count": evaluate(frame, rows.brake_advisory_count.to_numpy(), None, protocol["capacities"]),
               "logistic": evaluate(frame, probabilities, probabilities, protocol["capacities"])}
    save_json(directory / "metrics.json", {"version": FIXTURE_VERSION, "fixture": True, "status": "SYNTHETIC; NO PERFORMANCE EVIDENCE",
              "training": {"examples": 4, "vehicles": 4, "positive": 2, "negative": 2}, "training_prevalence": 0.5,
              "primary_temporal": methods, "primary_seen_vehicle_count": 0, "availability": "Synthetic fixture; no real cohort or temporal validity claim"})
    save_json(directory / "protocol.json", protocol)
    save_json(directory / "split-audit.json", {"fixture": True, "status": "No real data"})
    (directory / "model-card.md").write_text("# SYNTHETIC CI FIXTURE\nFour invented test rows, fitted only for software checks. Never real performance evidence or deployable production artifacts.\n")
    with closing(sqlite3.connect(directory / "snapshot.sqlite3")) as connection:
        connection.executescript("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL); CREATE TABLE followup_queue(case_id TEXT PRIMARY KEY,index_date TEXT NOT NULL,inputs_json TEXT NOT NULL,prediction_json TEXT NOT NULL); CREATE TABLE descriptive_history(case_id TEXT PRIMARY KEY REFERENCES followup_queue,history_json TEXT NOT NULL);")
        connection.executemany("INSERT INTO metadata VALUES(?,?)", [("model_version", FIXTURE_VERSION), ("data_version", "synthetic-ci-only"), ("history_starts", "2022-01-01"), ("status", "SYNTHETIC CI FIXTURE"), ("as_of", "2024-12-31")])
        for index, values in rows.iterrows():
            features = {name: None if pd.isna(value) else float(value) for name, value in values.items()}
            payload = {"vehicle_class": 4, "component_family": "brakes", "test_type": "NT", "test_result": "P", "features": features}
            case_id = f"{index:016x}"
            history = {"prior_recorded_tests": 0, "prior_brake_advisory_tests": 0, "prior_brake_failure_tests": 0,
                       "observed_history_days": 0, "model_input": False, "predictive_value": "unvalidated", "prior_absence_confirmed": False,
                       "limitation": "SYNTHETIC CI FIXTURE; no genuine inspection history"}
            assert set(history) == HISTORY_FIELDS
            connection.execute("INSERT INTO followup_queue VALUES(?,?,?,?)", (case_id, "2024-01-01", json.dumps(payload), json.dumps(predict_case(bundle, payload))))
            connection.execute("INSERT INTO descriptive_history VALUES(?,?)", (case_id, json.dumps(history)))
        connection.commit()
    files = {path.name: {"bytes": path.stat().st_size, "sha256": checksum(path)} for path in directory.iterdir()}
    manifest = {"version": FIXTURE_VERSION, "fixture": True, "python_minor": "3.12", "dependencies": {name: importlib.metadata.version(name) for name in PACKAGES}, "files": files}
    save_json(directory / "release-manifest.json", manifest)
    return {"version": FIXTURE_VERSION, "data_version": "synthetic-ci-only", "fixture": True, "status": "SYNTHETIC CI FIXTURE; NOT REAL PERFORMANCE",
            "directory": ".", "directory_base": "descriptor", "queue_cases": 4, "queue_as_of": "2024-12-31",
            "release_manifest_sha256": checksum(directory / "release-manifest.json")}


def validate_bundle(context, mode, code_version=None, artifact_version=None):
    context = Path(context).resolve()
    descriptor = json.loads((context / "release/descriptor.json").read_text())
    package = json.loads((context / "package-manifest.json").read_text())
    if descriptor.get("directory_base") != "descriptor" or descriptor["directory"] != ".":
        raise ValueError("Packaged release must be descriptor-relative and bounded")
    if {path.name for path in (context / "release").iterdir()} != RELEASE_FILES:
        raise ValueError("Unexpected release file or nested directory")
    if mode == "release":
        trusted = json.loads((context / "tools/trusted-release.json").read_text())
        original = ROOT / "docs/serving_release.json"
        if original.is_file() and trusted != json.loads(original.read_text()):
            raise ValueError("Packaged trust anchor differs from repository")
        if descriptor.get("fixture") is not False or package["mode"] != "release":
            raise ValueError("Production validation rejects synthetic fixtures")
        for key in ["version", "data_version", "release_manifest_sha256", "bundle_sha256", "snapshot_sha256", "queue_cases", "queue_as_of"]:
            if descriptor.get(key) != trusted[key]:
                raise ValueError("Release identity differs from approved production descriptor")
    elif mode == "fixture":
        if descriptor.get("fixture") is not True or descriptor["version"] != FIXTURE_VERSION or package["mode"] != "fixture":
            raise ValueError("Explicit fixture mode requires visibly synthetic artifacts")
    else:
        raise ValueError("Unknown packaging mode")
    if package["artifact_version"] != descriptor["version"]:
        raise ValueError("Artifact version metadata mismatch")
    if code_version is not None and code_version != package["code_version"]:
        raise ValueError("Image revision differs from staged code version")
    if artifact_version is not None and artifact_version != descriptor["version"]:
        raise ValueError("Image artifact label differs from staged release")
    previous = os.environ.get("BTP_ALLOW_FIXTURE")
    try:
        os.environ["BTP_ALLOW_FIXTURE"] = "1" if mode == "fixture" else "0"
        resource = Release(context / "release/descriptor.json")
    finally:
        if previous is None:
            os.environ.pop("BTP_ALLOW_FIXTURE", None)
        else:
            os.environ["BTP_ALLOW_FIXTURE"] = previous
    if mode == "release" and (resource.count != 200 or resource.metrics["primary_temporal"]["logistic"]["examples"] != 936):
        raise ValueError("Approved demo/evaluation population mismatch")
    return resource


def validate_context(context, mode, **kwargs):
    context = Path(context).resolve()
    package = json.loads((context / "package-manifest.json").read_text())
    actual = {path.relative_to(context).as_posix() for path in context.rglob('*') if path.is_file()}
    if actual != set(package["files"]) | {"package-manifest.json"}:
        raise ValueError("Unexpected or missing context files; build only staged allowlisted context")
    allowed = set(SOURCE_FILES) | {"tools/trusted-release.json"} | {"release/" + name for name in RELEASE_FILES}
    allowed |= {path.relative_to(context).as_posix() for path in (context / 'frontend/src').glob('*') if path.suffix in {'.js', '.jsx', '.css'} and not path.name.endswith('.test.js')}
    if not actual <= allowed | {"package-manifest.json"}:
        raise ValueError("Non-serving file in context")
    for filename, expected in package["files"].items():
        target = context / filename
        if target.is_symlink() or target.stat().st_size != expected["bytes"] or checksum(target) != expected["sha256"]:
            raise ValueError("Context identity/checksum mismatch")
    return validate_bundle(context, mode, **kwargs)


def stage(output, mode, code_version=None):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Staging output already exists; validate/reuse it or choose a new output directory")
    if not output.is_relative_to(ROOT / "data/package"):
        raise ValueError("Stage under ignored data/package only")
    if mode == "release":
        trusted = json.loads((ROOT / "docs/serving_release.json").read_text())
        resource = Release(ROOT / "docs/serving_release.json")
        for name, expected in resource.manifest["code_sha256"].items():
            if checksum(ROOT / f"pipeline/{name}.py") != expected:
                raise ValueError("Frozen inference/evaluation source changed")
    output.mkdir(parents=True)
    for name in SOURCE_FILES:
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    for source in (ROOT / "frontend/src").glob('*'):
        if source.suffix in {'.js', '.jsx', '.css'} and not source.name.endswith('.test.js'):
            target = output / 'frontend/src' / source.name
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(source, target)
    (output / "tools").mkdir()
    shutil.copyfile(ROOT / "docs/serving_release.json", output / "tools/trusted-release.json")
    if mode == "release":
        (output / "release").mkdir()
        for filename in resource.manifest["files"]:
            shutil.copyfile(resource.directory / filename, output / "release" / filename)
        shutil.copyfile(resource.directory / "release-manifest.json", output / "release/release-manifest.json")
        descriptor = trusted | {"directory": ".", "directory_base": "descriptor", "fixture": False}
    else:
        descriptor = fixture(output / "release")
    save_json(output / "release/descriptor.json", descriptor)
    files = {path.relative_to(output).as_posix(): {"bytes": path.stat().st_size, "sha256": checksum(path)} for path in sorted(output.rglob('*')) if path.is_file()}
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    save_json(output / "package-manifest.json", {"mode": mode, "artifact_version": descriptor["version"],
              "code_version": code_version or "working-tree-" + digest, "source_digest": digest, "platform": "linux/amd64", "files": files})
    validate_context(output, mode)
    return {"context": str(output), "mode": mode, "files": len(files) + 1, "bytes": sum(path.stat().st_size for path in output.rglob('*') if path.is_file()), "artifact_version": descriptor["version"], "source_digest": digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['stage', 'validate', 'validate-bundle'])
    parser.add_argument('--mode', choices=['release', 'fixture'], default='release')
    parser.add_argument('--context', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--code-version')
    parser.add_argument('--artifact-version')
    arguments = parser.parse_args()
    if arguments.command == 'stage':
        if arguments.output is None:
            parser.error('stage requires --output under data/package')
        print(json.dumps(stage(arguments.output, arguments.mode, arguments.code_version)))
    else:
        if arguments.context is None:
            parser.error('validation requires --context')
        validate = validate_context if arguments.command == 'validate' else validate_bundle
        resource = validate(arguments.context, arguments.mode, code_version=arguments.code_version, artifact_version=arguments.artifact_version)
        print(json.dumps({"validated": arguments.mode, "version": resource.bundle["version"], "cases": resource.count}))


if __name__ == '__main__':
    main()
