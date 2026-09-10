from pathlib import Path

import httpx
import pandas as pd
import pytest

from variantrank.api.app import app, create_app
from variantrank.api.service import ModelDescriptor
from variantrank.inference import PredictionResult

VCF_FIXTURE = Path(__file__).parents[1] / "fixtures" / "example.vcf"


class FakePredictionService:
    descriptor = ModelDescriptor(
        model="catboost",
        feature_set="annotated_vep_v1",
        features=36,
        training_date="2026-09-10T12:00:00+00:00",
        threshold=0.4761,
    )

    def predict(self, _vcf: Path, work_dir: Path) -> PredictionResult:
        predictions = pd.DataFrame(
            [
                {
                    "rank": 1,
                    "variant_id": "17:7674220:C:T",
                    "chrom": "17",
                    "pos": 7674220,
                    "ref": "C",
                    "alt": "T",
                    "gene": "TP53",
                    "consequence": "missense_variant",
                    "score": 0.947,
                    "prediction": "pathogenic",
                }
            ]
        )
        return PredictionResult(work_dir / "predictions.json", 1, predictions)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_health() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_model_info_is_honest_before_training() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/model/info")

    assert response.status_code == 200
    assert response.json() == {
        "package_version": "0.1.0",
        "model_status": "not_loaded",
        "research_use_only": True,
    }


@pytest.mark.anyio
async def test_model_info_describes_loaded_model() -> None:
    loaded_app = create_app(prediction_service=FakePredictionService())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=loaded_app), base_url="http://test"
    ) as client:
        response = await client.get("/model/info")

    assert response.status_code == 200
    assert response.json()["model"] == "catboost"
    assert response.json()["features"] == 36
    assert response.json()["threshold"] == pytest.approx(0.4761)


@pytest.mark.anyio
async def test_predict_accepts_vcf_multipart_and_returns_ranked_variants() -> None:
    loaded_app = create_app(prediction_service=FakePredictionService())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=loaded_app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/predict",
            files={"file": ("variants.vcf", VCF_FIXTURE.read_bytes(), "text/plain")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "catboost"
    assert payload["variants"][0]["variant_id"] == "17:7674220:C:T"
    assert payload["variants"][0]["score"] == pytest.approx(0.947)


@pytest.mark.anyio
async def test_predict_requires_configured_model() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/predict",
            files={"file": ("variants.vcf", VCF_FIXTURE.read_bytes(), "text/plain")},
        )

    assert response.status_code == 503
