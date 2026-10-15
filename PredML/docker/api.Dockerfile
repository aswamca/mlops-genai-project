# Realtime prediction and forecast API.
# Copies requirements-api.txt plus src/config.py, src/mlflow_registry.py,
# src/07_realtime_inference.py, and src/09_forecast.py. Runtime data and model
# state are mounted separately and are not baked into the image....
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/PredML

COPY docker/requirements-api.txt ./requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

RUN mkdir -p src
COPY src/config.py src/mlflow_registry.py src/07_realtime_inference.py src/09_forecast.py ./src/

EXPOSE 8000

CMD ["python", "src/07_realtime_inference.py"]
