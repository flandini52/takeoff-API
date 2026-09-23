# Build context is the repo root (see docker-compose.yml): this image
# needs pyproject.toml/uv.lock and src/landini_etl from the root, not just
# etl/. Installs from the same lockfile Streamlit and native Windows use —
# no separate requirements.txt, no PYTHONPATH tricks.
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src/ ./src/

RUN uv sync --frozen --no-dev

CMD ["uv", "run", "python", "-m", "landini_etl.main", "--help"]
