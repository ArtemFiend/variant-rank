"""FastAPI application factory and inference routes."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Protocol

from fastapi import FastAPI, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from variantrank import __version__
from variantrank.annotation import VEPRequestError
from variantrank.api.schemas import HealthResponse, ModelInfoResponse, PredictionResponse
from variantrank.api.service import ModelDescriptor, service_from_environment
from variantrank.data import VCFFormatError
from variantrank.inference import InferenceError, PredictionResult

DISCLAIMER = "Research use only. Not intended for diagnosis, treatment decisions, or clinical use."
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024


class PredictionBackend(Protocol):
    """Interface accepted by the API application factory."""

    descriptor: ModelDescriptor

    def predict(self, vcf: Path, work_dir: Path) -> PredictionResult: ...


def create_app(*, prediction_service: PredictionBackend | None = None) -> FastAPI:
    selected_service = prediction_service or service_from_environment()
    application = FastAPI(
        title="VariantRank API",
        version=__version__,
        description=DISCLAIMER,
    )

    @application.get("/health", response_model=HealthResponse, tags=["service"])
    def health() -> HealthResponse:
        return HealthResponse()

    @application.get(
        "/model/info",
        response_model=ModelInfoResponse,
        response_model_exclude_none=True,
        tags=["model"],
    )
    def model_info() -> ModelInfoResponse:
        if selected_service is None:
            return ModelInfoResponse(package_version=__version__)
        descriptor = selected_service.descriptor
        return ModelInfoResponse(
            package_version=__version__,
            model_status="loaded",
            model=descriptor.model,
            feature_set=descriptor.feature_set,
            features=descriptor.features,
            training_date=descriptor.training_date,
            threshold=descriptor.threshold,
        )

    @application.post("/predict", response_model=PredictionResponse, tags=["model"])
    async def predict(
        file: Annotated[UploadFile, File(description="Normalized GRCh38 VCF or VCF.GZ")],
    ) -> PredictionResponse:
        if selected_service is None:
            raise HTTPException(status_code=503, detail="model is not configured")
        filename = Path(file.filename or "variants.vcf").name
        if not (filename.endswith(".vcf") or filename.endswith(".vcf.gz")):
            raise HTTPException(status_code=415, detail="file must use .vcf or .vcf.gz")

        try:
            with TemporaryDirectory(prefix="variantrank-api-") as temporary:
                work_dir = Path(temporary)
                input_path = work_dir / filename
                await _save_upload(file, input_path)
                result = await run_in_threadpool(selected_service.predict, input_path, work_dir)
                records = json.loads(result.predictions.to_json(orient="records"))
        except HTTPException:
            raise
        except (InferenceError, VCFFormatError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except VEPRequestError as error:
            raise HTTPException(status_code=502, detail="VEP annotation failed") from error
        finally:
            await file.close()

        return PredictionResponse(
            model=selected_service.descriptor.model,
            threshold=selected_service.descriptor.threshold,
            variants=records,
        )

    return application


async def _save_upload(upload: UploadFile, destination: Path) -> None:
    size = 0
    with destination.open("wb") as handle:
        while chunk := await upload.read(UPLOAD_CHUNK_BYTES):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="VCF exceeds 10 MiB upload limit")
            handle.write(chunk)
    if size == 0:
        raise HTTPException(status_code=422, detail="VCF upload is empty")


app = create_app()
