import httpx
import pytest

from variantrank.api.app import app


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
