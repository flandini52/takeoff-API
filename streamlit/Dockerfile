# Build context is the repo root (see docker-compose.yml), not streamlit/,
# so this image can also embed the etl package: the "Aggiorna dati" button
# imports etl.main.run() in-process instead of shelling out (see
# streamlit/app/services/etl.py). etl/ keeps its own separate, minimal-context
# image (etl/Dockerfile) for CLI/scheduled runs — this is the one additional
# place it's also installed.
FROM python:3.11-slim

WORKDIR /app

COPY streamlit/requirements.txt ./streamlit-requirements.txt
COPY etl/requirements.txt ./etl-requirements.txt
RUN pip install --no-cache-dir -r streamlit-requirements.txt -r etl-requirements.txt

COPY streamlit/app/ ./app/
COPY etl/app/ ./etl/

ENV PYTHONPATH=/app

EXPOSE 8501

CMD ["streamlit", "run", "app/main.py", "--server.port=8501", "--server.address=0.0.0.0"]
