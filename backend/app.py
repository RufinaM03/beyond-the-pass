"""HTTP boundary around trusted Phase 3 inference; no training or source access."""

import json
import logging
import os
import re
from contextlib import asynccontextmanager, closing
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from pipeline.serving import MODEL_FEATURES, load_release, open_snapshot, predict_case


ROOT = Path(__file__).resolve().parents[1]
HISTORY_FIELDS = {"prior_recorded_tests", "prior_brake_advisory_tests", "prior_brake_failure_tests",
                  "observed_history_days", "model_input", "predictive_value", "prior_absence_confirmed", "limitation"}
logger = logging.getLogger(__name__)


class Release:
    def __init__(self, descriptor_path):
        self.descriptor = json.loads(Path(descriptor_path).read_text())
        if self.descriptor.get("fixture", False) and os.environ.get("BTP_ALLOW_FIXTURE") != "1":
            raise ValueError("Synthetic fixture artifacts require explicit BTP_ALLOW_FIXTURE=1")
        base = Path(descriptor_path).resolve().parent if self.descriptor.get("directory_base") == "descriptor" else ROOT
        self.directory = (base / self.descriptor["directory"]).resolve()
        self.bundle, self.manifest = load_release(self.directory, self.descriptor["release_manifest_sha256"])
        schema = self.read("feature-schema.json")
        if schema["features"] != MODEL_FEATURES or schema["version"] != self.bundle["version"]:
            raise ValueError("Feature schema differs from frozen runtime")
        if self.descriptor["version"] != self.bundle["version"] or self.descriptor["data_version"] != self.bundle["data_version"]:
            raise ValueError("Descriptor version differs from bundle")
        self.metrics = self.read("metrics.json")
        self.protocol = self.read("protocol.json")
        with closing(self.connect()) as connection:
            self.metadata = dict(connection.execute("SELECT key,value FROM metadata"))
            rows = connection.execute("SELECT case_id,index_date,inputs_json,prediction_json FROM followup_queue").fetchall()
            if len(rows) != self.descriptor["queue_cases"] or len(rows) > 200:
                raise ValueError("Snapshot case count differs")
            for case_id, index_date, inputs, stored in rows:
                if not re.fullmatch(r"[a-f0-9]{16}", case_id) or date.fromisoformat(index_date) > date.fromisoformat(self.descriptor["queue_as_of"]):
                    raise ValueError("Invalid case identity/date")
                if predict_case(self.bundle, json.loads(inputs)) != json.loads(stored):
                    raise ValueError("Stored prediction differs from frozen inference")
                history = connection.execute("SELECT history_json FROM descriptive_history WHERE case_id=?", (case_id,)).fetchone()
                if not history or set(json.loads(history[0])) != HISTORY_FIELDS:
                    raise ValueError("Unexpected descriptive history schema")
                description = json.loads(history[0])
                if description["model_input"] is not False or description["prior_absence_confirmed"] is not False:
                    raise ValueError("History must remain descriptive and left-truncated")
            if self.metadata["model_version"] != self.bundle["version"] or self.metadata["data_version"] != self.bundle["data_version"]:
                raise ValueError("Snapshot version differs")
        if self.metrics["version"] != self.bundle["version"]:
            raise ValueError("Evaluation version differs")
        self.count = len(rows)

    def read(self, filename):
        return json.loads((self.directory / filename).read_text())

    def connect(self):
        return open_snapshot(self.directory / "snapshot.sqlite3")


def create_app(descriptor_path=None, frontend_path=None, release_loader=Release):
    descriptor_path = Path(descriptor_path or os.environ.get("BTP_RELEASE_DESCRIPTOR", ROOT / "docs/serving_release.json"))
    frontend_path = Path(frontend_path or os.environ.get("BTP_FRONTEND_DIR", ROOT / "frontend/dist"))
    @asynccontextmanager
    async def lifespan(application):
        application.state.release = None
        try:
            application.state.release = release_loader(descriptor_path)
        except Exception:
            logger.exception("Trusted release unavailable; API will report not ready")
        yield
        application.state.release = None

    application = FastAPI(title="Beyond the Pass", version="1.0.0", lifespan=lifespan,
                          docs_url=None, redoc_url=None, openapi_url="/api/openapi.json")

    @application.middleware("http")
    async def boundaries(request: Request, call_next):
        if request.url.path.startswith("/api") and request.method == "POST":
            length = request.headers.get("content-length", "0")
            if not length.isdecimal() or int(length) > 16384:
                return JSONResponse({"detail": "Request exceeds 16 KiB limit"}, status_code=413)
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 16384:
                    return JSONResponse({"detail": "Request exceeds 16 KiB limit"}, status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def release():
        resource = getattr(application.state, "release", None)
        if resource is None:
            raise HTTPException(503, "Trusted artifacts unavailable; check local release and runtime versions")
        return resource

    def get_case(case_id):
        resource = release()
        if not re.fullmatch(r"[a-f0-9]{16}", case_id):
            raise HTTPException(404, "Index-inspection case not found")
        with closing(resource.connect()) as connection:
            row = connection.execute("SELECT index_date,inputs_json FROM followup_queue WHERE case_id=?", (case_id,)).fetchone()
            history = connection.execute("SELECT history_json FROM descriptive_history WHERE case_id=?", (case_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Index-inspection case not found")
        inputs = json.loads(row[1])
        return {"case_id": case_id, "index_date": row[0], "inputs": inputs,
                "prediction": predict_case(resource.bundle, inputs), "history": json.loads(history[0]),
                "history_available_through": row[0], "history_starts": resource.metadata["history_starts"],
                "history_resolution": "Aggregate prior records only; dated inspections and item descriptions are not exported",
                "as_of": resource.descriptor["queue_as_of"]}

    @application.get("/api/health")
    def health():
        return {"status": "alive"}

    @application.get("/api/ready")
    def ready():
        resource = release()
        return {"status": "ready", "model_version": resource.bundle["version"], "verified_cases": resource.count}

    @application.get("/api/versions")
    def versions():
        resource = release()
        return {"api_version": "1.0.0", "model_version": resource.bundle["version"],
                "fixture": resource.descriptor.get("fixture", False), "code_version": os.environ.get("BTP_CODE_VERSION", "local-working-tree"),
                "data_version": resource.bundle["data_version"], "manifest_sha256": resource.descriptor["release_manifest_sha256"],
                "demo_cases": resource.count, "evaluation_examples": resource.metrics["primary_temporal"]["logistic"]["examples"],
                "as_of": resource.descriptor["queue_as_of"], "history_starts": resource.metadata["history_starts"],
                "status": resource.descriptor["status"], "recurrence_used_by_model": False}

    @application.get("/api/cases")
    def cases(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0, le=10000),
              date_from: date | None = None, date_to: date | None = None):
        resource = release()
        if date_from and date_to and date_from > date_to:
            raise HTTPException(422, "date_from must not exceed date_to")
        parameters = (date_from.isoformat() if date_from else None, date_to.isoformat() if date_to else None)
        where = "WHERE (?1 IS NULL OR index_date>=?1) AND (?2 IS NULL OR index_date<=?2)"
        with closing(resource.connect()) as connection:
            total = connection.execute("SELECT COUNT(*) FROM followup_queue " + where, parameters).fetchone()[0]
            rows = connection.execute("SELECT case_id,index_date,inputs_json,prediction_json FROM followup_queue " + where +
                                      " ORDER BY index_date DESC,case_id ASC LIMIT ?3 OFFSET ?4", parameters + (limit, offset)).fetchall()
        return {"items": [summary(row) for row in rows], "total": total, "limit": limit, "offset": offset, "scope": "historical demonstration"}

    @application.get("/api/cases/{case_id}")
    def case_detail(case_id: str):
        return get_case(case_id)

    @application.get("/api/cases/{case_id}/prediction")
    def case_prediction(case_id: str):
        return get_case(case_id)["prediction"]

    @application.post("/api/predict")
    async def predict(request: Request):
        resource = release()
        try:
            payload = await request.json()
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(422, "Expected a JSON prediction request")
        try:
            result = predict_case(resource.bundle, payload)
        except (ValueError, OverflowError, TypeError):
            raise HTTPException(422, "Numeric feature values are not representable")
        return JSONResponse(result, status_code=422 if result["status"] in {"invalid_input", "unsupported_scope"} else 200)

    @application.get("/api/queue")
    def queue(capacity: int = Query(40, ge=0, le=500), limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0, le=10000)):
        resource = release()
        condition = "WHERE json_extract(prediction_json,'$.status')='scored'"
        with closing(resource.connect()) as connection:
            eligible = connection.execute("SELECT COUNT(*) FROM followup_queue " + condition).fetchone()[0]
            selected = min(capacity, eligible)
            page_size = max(0, min(limit, selected - offset))
            rows = connection.execute("SELECT case_id,index_date,inputs_json,prediction_json FROM followup_queue " + condition +
                                      " ORDER BY CAST(json_extract(prediction_json,'$.exploratory_prioritization_score') AS REAL) DESC,case_id ASC LIMIT ? OFFSET ?",
                                      (page_size, offset)).fetchall()
        return {"items": [summary(row) | {"rank": offset + index + 1} for index, row in enumerate(rows)],
                "requested_capacity": capacity, "selected": selected, "eligible": eligible, "unscored": resource.count - eligible,
                "exceeds_available": capacity > eligible, "limit": limit, "offset": offset,
                "scope": "200-case historical demonstration only; saved full-cohort evaluation unchanged",
                "tie_break": "score descending, opaque case_id ascending; no outcomes", "as_of": resource.descriptor["queue_as_of"]}

    @application.get("/api/evaluation")
    def evaluation():
        return release().metrics

    @application.get("/api/methodology")
    def methodology():
        resource = release()
        return {"protocol": resource.protocol, "model_card": (resource.directory / "model-card.md").read_text(),
                "feature_schema": resource.read("feature-schema.json")}

    @application.api_route("/api", methods=["GET", "POST"], include_in_schema=False)
    @application.api_route("/api/{unmatched:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"], include_in_schema=False)
    def api_missing(unmatched: str = ""):
        raise HTTPException(404, "API endpoint not found")

    frontend_path = Path(frontend_path)
    if (frontend_path / "assets").is_dir():
        application.mount("/assets", StaticFiles(directory=frontend_path / "assets"), name="assets")

    @application.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path not in {"", "queue", "evaluation", "methodology"} and not re.fullmatch(r"cases/[a-f0-9]{16}", path):
            raise HTTPException(404, "Page or asset not found")
        index = frontend_path / "index.html"
        if not index.is_file():
            raise HTTPException(503, "Frontend build unavailable; run npm ci and npm run build in frontend")
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return application


def summary(row):
    case_id, index_date, inputs, prediction = row
    score = json.loads(prediction)
    return {"case_id": case_id, "index_date": index_date, "features": json.loads(inputs)["features"],
            "status": score["status"], "exploratory_prioritization_score": score["exploratory_prioritization_score"]}


app = create_app()
