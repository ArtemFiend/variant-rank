"""FastAPI application factory."""

from fastapi import FastAPI

from variantrank import __version__
from variantrank.api.schemas import HealthResponse, ModelInfoResponse

DISCLAIMER = (
    "Research and educational use only. Not intended for diagnosis, "
    "treatment decisions, or other clinical use."
)


def create_app() -> FastAPI:
    application = FastAPI(
        title="VariantRank API",
        version=__version__,
        description=DISCLAIMER,
    )

    @application.get("/health", response_model=HealthResponse, tags=["service"])
    def health() -> HealthResponse:
        return HealthResponse()

    @application.get("/model/info", response_model=ModelInfoResponse, tags=["model"])
    def model_info() -> ModelInfoResponse:
        return ModelInfoResponse(package_version=__version__)

    return application


app = create_app()
