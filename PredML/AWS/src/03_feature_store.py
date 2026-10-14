import importlib
import json

import pandas as pd
from config import (
    OFFLINE_FILE,
    ONLINE_FILE,
    PROCESSED_FILE,
    banner,
    ensure_dirs,
    write_text,
)


def _json_value(value):
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if pd.api.types.is_number(value):
        return value.item() if hasattr(value, "item") else value
    return str(value)


def run():
    ensure_dirs()
    banner("STAGE 3 - FEATURE STORE (offline + online)")

    df = pd.read_parquet(PROCESSED_FILE)
    feature_module = importlib.import_module("02_feature_engineering")
    df_features = feature_module.build_features(df)

    df_features.to_parquet(OFFLINE_FILE, index=False)
    print(f"OFFLINE store: {OFFLINE_FILE}")
    print(f"{len(df_features)} rows (full history for training/batch)")

    latest = (
        df_features.sort_values("date")
        .groupby(["product_id", "region"])
        .tail(1)
        .set_index(["product_id", "region"])
    )
    online = {
        f"{product_id}|{region}": {
            column: _json_value(value) for column, value in row.items()
        }
        for (product_id, region), row in latest.iterrows()
    }

    write_text(ONLINE_FILE, json.dumps(online, indent=2))

    print(f"ONLINE store: {ONLINE_FILE}")
    print(f"{len(online)} entries (latest per product-region for real-time)")


if __name__ == "__main__":
    run()