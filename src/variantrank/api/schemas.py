"""REST response schemas."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ModelInfoResponse(BaseModel):
    package_version: str
    model_status: Literal["not_loaded"] = "not_loaded"
    research_use_only: bool = True
