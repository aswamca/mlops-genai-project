# MLflow tracking server and model registry UI.
# Installs MLflow and copies no application files. Tracking metadata and model
# artifacts are persisted in the mounted mlruns directory; no generated data
# or PredML source code is copied.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN python -m pip install --upgrade pip \
    && python -m pip install "mlflow==2.22.2"

WORKDIR /app/PredML
RUN mkdir -p /app/PredML/mlruns

EXPOSE 5000

# Accept the Compose service hostname and local UI/healthcheck requests.
CMD ["mlflow", "server", \
    "--backend-store-uri", "sqlite:////app/PredML/mlruns/mlruns.db", \
    "--default-artifact-root", "mlflow-artifacts:/", \
    "--artifacts-destination", "/app/PredML/mlruns/artifacts", \
    "--serve-artifacts", \
    "--workers", "1", \
    "--host", "0.0.0.0", \
    "--port", "5000", \
    "--allowed-hosts", "mlflow:5000,localhost:5000,127.0.0.1:5000"]
