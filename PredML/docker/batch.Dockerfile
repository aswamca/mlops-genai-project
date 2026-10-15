# AWS batch image for preprocessing, training, inference, monitoring,
# forecasting, and rollback. Local source under PredML/src is not used here.
# Copies requirements-aws.txt plus src/config.py, src/mlflow_registry.py, and
# src/01_preprocess.py through src/06_batch_inference.py, then
# src/08_model_monitoring.py through src/10_rollback.py. Raw data is uploaded
# to S3 separately; datasets/model/database artifacts are not included....
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/PredML

COPY AWS/src/requirements-aws.txt ./requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

RUN mkdir -p src
COPY AWS/src/config.py AWS/src/mlflow_registry.py \
    AWS/src/01_preprocess.py \
    AWS/src/02_feature_engineering.py \
    AWS/src/03_feature_store.py \
    AWS/src/04_train_model.py \
    AWS/src/05_register_model.py \
    AWS/src/06_batch_inference.py \
    AWS/src/08_model_monitoring.py \
    AWS/src/09_forecast.py \
    AWS/src/10_rollback.py \
    ./src/

ENTRYPOINT ["sh", "-c", \
    "stage=${STAGE:?STAGE is required (for example STAGE=04_train_model)}; \
    case \"$stage\" in \
        01_preprocess|02_feature_engineering|03_feature_store|04_train_model|05_register_model|06_batch_inference|08_model_monitoring|09_forecast|10_rollback) ;; \
        *) echo \"Unsupported STAGE: $stage\" >&2; \
           echo 'Allowed: 01_preprocess, 02_feature_engineering, 03_feature_store, 04_train_model, 05_register_model, 06_batch_inference, 08_model_monitoring, 09_forecast, 10_rollback' >&2; \
           exit 2 ;; \
    esac; \
    exec python \"/app/PredML/src/${stage}.py\" \"$@\"", \
    "predml-batch"]
