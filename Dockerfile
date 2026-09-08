FROM ghcr.io/astral-sh/uv:0.12.5 AS uv
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN groupadd --system variantrank \
    && useradd --system --gid variantrank --create-home variantrank

WORKDIR /app
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --locked --no-dev

USER variantrank
EXPOSE 8000

CMD ["uvicorn", "variantrank.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
