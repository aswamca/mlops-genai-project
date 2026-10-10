# On-demand preprocessing, feature engineering, training/registration,
# inference, monitoring, forecasting, and rollback image.
# Copies requirements-batch.txt plus src/config.py, src/mlflow_registry.py, and
# src/01_preprocess.py through src/06_batch_inference.py, then
# src/08_model_monitoring.py through src/10_rollback.py. Deliberately excludes
# src/00_generate_raw_data.py and all datasets/model/database artifacts.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/PredML

COPY docker/requirements-batch.txt ./requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

RUN mkdir -p src
COPY src/config.py src/mlflow_registry.py \
    src/01_preprocess.py \
    src/02_feature_engineering.py \
    src/03_feature_store.py \
    src/04_train_model.py \
    src/05_register_model.py \
    src/06_batch_inference.py \
    src/08_model_monitoring.py \
    src/09_forecast.py \
    src/10_rollback.py \
    ./src/

ENTRYPOINT ["sh", "-c", \
    "stage=${STAGE:?STAGE is required (for example STAGE=04_train_model)}; \
    if [ \"$stage\" = \"00_generate_raw_data\" ]; then \
        echo '00_generate_raw_data is a local data seeder and is not included in this image.' >&2; \
        echo 'Run on the host from PredML: python src/00_generate_raw_data.py' >&2; \
        exit 2; \
    fi; \
    case \"$stage\" in \
        01_preprocess|02_feature_engineering|03_feature_store|04_train_model|05_register_model|06_batch_inference|08_model_monitoring|09_forecast|10_rollback) ;; \
        *) echo \"Unsupported STAGE: $stage\" >&2; \
           echo 'Allowed: 01_preprocess, 02_feature_engineering, 03_feature_store, 04_train_model, 05_register_model, 06_batch_inference, 08_model_monitoring, 09_forecast, 10_rollback' >&2; \
           exit 2 ;; \
    esac; \
    exec python \"/app/PredML/src/${stage}.py\" \"$@\"", \
    "predml-batch"]
