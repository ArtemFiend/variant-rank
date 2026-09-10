"""REST response schemas."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ModelInfoResponse(BaseModel):
    package_version: str
    model_status: Literal["loaded", "not_loaded"] = "not_loaded"
    research_use_only: bool = True
    model: str | None = None
    feature_set: str | None = None
    features: int | None = None
    training_date: str | None = None
    threshold: float | None = None


class VariantPrediction(BaseModel):
    rank: int
    variant_id: str
    chrom: str
    pos: int
    ref: str
    alt: str
    gene: str | None
    consequence: str
    score: float
    prediction: Literal["pathogenic", "benign"]


class PredictionResponse(BaseModel):
    model: str
    threshold: float
    variants: list[VariantPrediction]
