"""Strict manual scenarios around the unchanged trusted prediction implementation."""

from calendar import monthrange
from datetime import date
import math

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from pipeline.serving import MODEL_FEATURES, predict_case

LIMITS = {"vehicle_age_years": 1000, "mileage": 1_000_000_000, "brake_advisory_count": 10_000, "advisory_count": 10_000}
MILEAGE_NOTE = "Miles: the DVSA guide documents kilometre-to-mile correction for the 2022 training source. This pipeline does not convert units. Exact correction semantics in later evaluation/demo releases remain unverified."


class ManualFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    vehicle_age_years: float | None = Field(ge=0, le=LIMITS["vehicle_age_years"])
    mileage: float | None = Field(gt=0, le=LIMITS["mileage"])
    brake_advisory_count: int = Field(ge=1, le=LIMITS["brake_advisory_count"])
    advisory_count: int = Field(ge=1, le=LIMITS["advisory_count"])

    @field_validator("brake_advisory_count", "advisory_count", mode="before")
    @classmethod
    def integral_json_numbers(cls, value):
        if type(value) is float and math.isfinite(value) and value.is_integer():
            return int(value)
        return value

    @model_validator(mode="after")
    def consistent_counts(self):
        if self.advisory_count < self.brake_advisory_count:
            raise ValueError("Total advisories must include all brake advisories")
        return self


class ManualRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    eligibility_confirmed: StrictBool
    features: ManualFeatures
    inspection_date: str | None = None

    @field_validator("eligibility_confirmed")
    @classmethod
    def eligible(cls, value):
        if not value:
            raise ValueError("Outside intended scope unless Class 4, normal inspection, strict pass and at least one brake advisory are confirmed")
        return value

    @field_validator("inspection_date")
    @classmethod
    def context_date(cls, value):
        if value is not None:
            parsed = date.fromisoformat(value)
            if parsed.isoformat() != value or not 1900 <= parsed.year <= 2100:
                raise ValueError("Use an ISO YYYY-MM-DD context date between 1900 and 2100")
        return value


def calendar_months(value, months):
    year, month = divmod(value.year * 12 + value.month - 1 + months, 12)
    month += 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def prediction_info(bundle):
    medians = dict(zip(MODEL_FEATURES, bundle["pipeline"]["impute"].statistics_.tolist()))
    return {"model_version": bundle["version"], "data_version": bundle["data_version"], "mileage_unit": "miles",
            "mileage_note": MILEAGE_NOTE, "technical_maximums": LIMITS,
            "training_ranges": bundle["training_ranges"],
            "imputation_medians": {key: medians[key] for key in ["vehicle_age_years", "mileage"]},
            "scope": "Class 4 / brakes / normal (NT) / strict pass (P) / at least one current brake advisory"}


def predict_manual(bundle, request):
    features = request.features.model_dump()
    prediction = predict_case(bundle, {"vehicle_class": 4, "component_family": "brakes", "test_type": "NT", "test_result": "P", "features": features})
    window = None
    if request.inspection_date:
        inspected = date.fromisoformat(request.inspection_date)
        window = {"start": calendar_months(inspected, 9).isoformat(), "end": calendar_months(inspected, 15).isoformat()}
    medians = prediction_info(bundle)["imputation_medians"]
    return {"prediction": prediction, "submitted_features": features,
            "imputed_values": {key: medians[key] for key in prediction.get("imputed_features", [])},
            "inspection_date": request.inspection_date, "nominal_followup_window": window,
            "date_used_by_model": False, "stored": False, "ranked_against_historical_queue": False,
            "context_note": "Nominal cohort observation window only, not a predicted failure date or time to failure. A new prediction is not an observed outcome or evaluation result."}
