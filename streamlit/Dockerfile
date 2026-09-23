# Build context is the repo root (see docker-compose.yml): installs from
# the same pyproject.toml/uv.lock as etl/Dockerfile and native Windows, so
# landini_etl (needed in-process by the "Aggiorna dati" button, see
# streamlit/app/services/etl.py) is on sys.path the same way everywhere —
# no PYTHONPATH, no per-environment special case.
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY streamlit/app/ ./streamlit/app/

RUN uv sync --frozen --no-dev

EXPOSE 8501

# Same invocation as native Windows (see DEPLOY_WINDOWS.md): only the
# working directory (repo root) differs, never the command.
CMD ["uv", "run", "streamlit", "run", "streamlit/app/main.py", "--server.port=8501", "--server.address=0.0.0.0"]
