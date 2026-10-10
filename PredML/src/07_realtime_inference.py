from __future__ import annotations

import importlib
import json
import math
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

import mlflow
import numpy as np
import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from config import (
    CHAMPION_ALIAS,
    FEATURE_COLUMNS,
    MLFLOW_REGISTERED_MODEL_NAME,
    ONLINE_FILE,
    PRODUCT_MASTER_FILE,
    REGIONS,
)
from mlflow_registry import load_champion_model


class RuntimeArtifacts:
    def __init__(
        self,
        version: str,
        model: mlflow.pyfunc.PyFuncModel,
        feature_columns: list[str],
        online_features: dict[str, dict[str, object]],
        product_master: dict[str, dict[str, object]],
    ) -> None:
        self.version = version
        self.model = model
        self.feature_columns = feature_columns
        self.online_features = online_features
        self.product_master = product_master


def _read_json_file(path: Path, description: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not load {description} from {path}: {error}") from error


def _load_runtime_artifacts() -> RuntimeArtifacts:
    """Load the champion model and point-in-time lookup data once at startup."""
    model_version = load_champion_model()
    feature_columns_raw = model_version.tags.get("feature_columns")
    if not feature_columns_raw:
        raise RuntimeError(
            f"Champion version {model_version.version} has no feature_columns tag. "
            "Run 04_train_model.py and 05_register_model.py again."
        )
    try:
        feature_columns = json.loads(feature_columns_raw)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Champion version {model_version.version} has invalid feature_columns JSON."
        ) from error
    if (
        not isinstance(feature_columns, list)
        or not feature_columns
        or any(not isinstance(column, str) for column in feature_columns)
    ):
        raise RuntimeError(
            f"Champion version {model_version.version} has an invalid feature_columns tag."
        )

    unsupported_features = [
        column for column in feature_columns if column not in FEATURE_COLUMNS
    ]
    if unsupported_features:
        raise RuntimeError(
            "Champion model requires features not configured by this project: "
            f"{unsupported_features}"
        )

    online_data = _read_json_file(ONLINE_FILE, "online feature store")
    if not isinstance(online_data, dict) or not online_data:
        raise RuntimeError(f"Online feature store is empty or invalid: {ONLINE_FILE}")
    online_features = {
        key: value
        for key, value in online_data.items()
        if isinstance(key, str) and isinstance(value, dict)
    }
    if len(online_features) != len(online_data):
        raise RuntimeError(
            f"Online feature store contains invalid product-region entries: {ONLINE_FILE}"
        )

    product_master: dict[str, dict[str, object]] = {}
    if PRODUCT_MASTER_FILE.exists():
        master_data = _read_json_file(PRODUCT_MASTER_FILE, "product master")
        if not isinstance(master_data, dict):
            raise RuntimeError(f"Product master must contain a JSON object: {PRODUCT_MASTER_FILE}")
        for product_id, details in master_data.items():
            if isinstance(product_id, str) and product_id.startswith("_"):
                continue
            if not isinstance(product_id, str) or not isinstance(details, dict):
                raise RuntimeError(
                    f"Product master contains an invalid entry: {PRODUCT_MASTER_FILE}"
                )
            product_master[product_id] = details

    model_uri = (
        f"models:/{MLFLOW_REGISTERED_MODEL_NAME}@{CHAMPION_ALIAS}"
    )
    model = mlflow.pyfunc.load_model(model_uri)
    return RuntimeArtifacts(
        version=str(model_version.version),
        model=model,
        feature_columns=feature_columns,
        online_features=online_features,
        product_master=product_master,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.runtime = _load_runtime_artifacts()
    runtime = app.state.runtime
    print(
        f"Realtime inference ready: {MLFLOW_REGISTERED_MODEL_NAME} "
        f"v{runtime.version}; {len(runtime.online_features)} online entries"
    )
    yield


app = FastAPI(
    title="Pharma Cost Forecaster",
    description="Realtime cost predictions using the champion model and latest online features.",
    lifespan=lifespan,
)


class PredictRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "product_id": "PRD001",
                "region": "NA",
                "sales": 190000.0,
            }
        }
    )

    product_id: str = Field(min_length=1, description="Product SKU, for example PRD001")
    region: str = Field(description="Sales region")
    sales: float = Field(ge=0, allow_inf_nan=False, description="Current sales value")

    @field_validator("region")
    @classmethod
    def validate_region(cls, value: str) -> str:
        if value not in REGIONS:
            raise ValueError(f"region must be one of {REGIONS}")
        return value


class PredictResponse(BaseModel):
    predicted_cost: float
    model_version: str
    product_id: str
    region: str
    feature_as_of: str
    served_at: str
    confidence: Literal["high", "low"]
    feature_source: str


class ForecastRequest(BaseModel):
    frequency: Literal["daily", "weekly", "monthly", "quarterly", "half", "yearly"]
    start: date
    end: date
    products: list[str] | None = None
    regions: list[str] | None = None


@app.get("/")
def root(request: Request) -> dict[str, object]:
    runtime: RuntimeArtifacts = request.app.state.runtime
    return {
        "service": "pharma-cost-forecaster",
        "model_version": runtime.version,
        "online_entries": len(runtime.online_features),
        "product_master_entries": len(runtime.product_master),
        "docs": "/docs",
    }


@app.get("/health")
def health(request: Request) -> dict[str, str]:
    runtime: RuntimeArtifacts = request.app.state.runtime
    return {"status": "ok", "model_version": runtime.version}


@app.post("/forecast")
def forecast(payload: ForecastRequest) -> dict[str, object]:
    forecast_module = importlib.import_module("09_forecast")
    try:
        result = forecast_module.forecast(
            frequency=payload.frequency,
            start=payload.start.isoformat(),
            end=payload.end.isoformat(),
            products=payload.products,
            regions=payload.regions,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    rows = json.loads(result.to_json(orient="records", date_format="iso"))
    return {
        "frequency": payload.frequency,
        "row_count": len(rows),
        "forecasts": rows,
    }


@app.post("/predict", response_model=PredictResponse)
def predict(payload: PredictRequest, request: Request) -> PredictResponse:
    runtime: RuntimeArtifacts = request.app.state.runtime
    product_id = payload.product_id.strip()
    if not product_id:
        raise HTTPException(status_code=422, detail="product_id must not be blank")

    product = runtime.product_master.get(product_id)
    confidence: Literal["high", "low"] = "high"
    feature_source = "online_feature_store"
    lookup_product_id = product_id

    if runtime.product_master and product is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown product_id '{product_id}' in product master.",
        )
    if product is not None:
        status = product.get("status", "active")
        if status == "retired":
            raise HTTPException(status_code=410, detail=f"Product '{product_id}' is retired.")
        if status == "launch":
            analog_sku = product.get("analog_sku")
            if not isinstance(analog_sku, str) or not analog_sku:
                raise HTTPException(
                    status_code=503,
                    detail=f"Launch product '{product_id}' has no configured analog_sku.",
                )
            lookup_product_id = analog_sku
            confidence = "low"
            feature_source = f"analog:{analog_sku}"
        elif status != "active":
            raise HTTPException(
                status_code=409,
                detail=f"Product '{product_id}' has unsupported status '{status}'.",
            )

    key = f"{lookup_product_id}|{payload.region}"
    online_row = runtime.online_features.get(key)
    if online_row is None:
        raise HTTPException(
            status_code=503,
            detail=(
                f"No online features for {key}. Run 03_feature_store.py "
                "to refresh the online feature store."
            ),
        )

    row = dict(online_row)
    feature_as_of = row.get("date")
    if not isinstance(feature_as_of, str):
        raise HTTPException(
            status_code=503,
            detail=f"Online feature row for {key} has no valid feature date.",
        )
    row["sales"] = payload.sales
    today = date.today()
    row.update(
        {
            "month": today.month,
            "quater": (today.month - 1) // 3 + 1,
            "day_of_week": today.weekday(),
            "is_q4": int(today.month in (10, 11, 12)),
            "is_weekend": int(today.weekday() >= 5),
            "is_month_end": int(pd.Timestamp(today).is_month_end),
        }
    )
    missing_features = [
        column for column in runtime.feature_columns if column not in row
    ]
    if missing_features:
        raise HTTPException(
            status_code=503,
            detail=f"Online row is missing required model features: {missing_features}",
        )

    model_input = pd.DataFrame(
        [{column: row[column] for column in runtime.feature_columns}],
        columns=runtime.feature_columns,
    )
    try:
        numeric_features = model_input.to_numpy(dtype=float)
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail=f"Online feature row contains non-numeric model inputs: {error}",
        ) from error
    if not np.isfinite(numeric_features).all():
        raise HTTPException(
            status_code=503,
            detail="Online feature row contains missing or non-finite model inputs.",
        )
    model_input = pd.DataFrame(numeric_features, columns=runtime.feature_columns)
    try:
        prediction = float(runtime.model.predict(model_input)[0])
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=500,
            detail=f"Champion model could not score the online features: {error}",
        ) from error
    if not math.isfinite(prediction):
        raise HTTPException(
            status_code=500,
            detail="Champion model returned a non-finite prediction.",
        )

    return PredictResponse(
        predicted_cost=round(prediction, 2),
        model_version=runtime.version,
        product_id=product_id,
        region=payload.region,
        feature_as_of=feature_as_of,
        served_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        confidence=confidence,
        feature_source=feature_source,
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
