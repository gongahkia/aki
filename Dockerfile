FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir "uv==0.9.21"

COPY pyproject.toml uv.lock README.md ./
COPY config.toml ./
COPY src ./src
COPY scripts/preflight.py scripts/check_retention_manifest.py scripts/demo.py ./scripts/

RUN uv sync --frozen --no-dev --extra server \
    && uv run python -m spacy download en_core_web_sm \
    && uv cache clean

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/ready >/dev/null || exit 1

CMD ["uv", "run", "uvicorn", "junas.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
