from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime

import numpy as np
import pandas as pd

from config import (
    BASELINE_DIR,
    DRIFT_THRESHOLDS,
    FEATURE_COLUMNS,
    OFFLINE_FILE,
    PREDICTIONS_DIR,
    REPORTS_DIR,
    TARGET_COLUMN,
    TEST_DAYS,
    banner,
    ensure_dirs,
    read_text,
    s3_exists,
    s3_glob,
    s3_path,
    write_text,
)


BASELINE_STATS = f"{BASELINE_DIR}/statistics.json"
BASELINE_CONSTRAINTS = f"{BASELINE_DIR}/constraints.json"
CATEGORICAL_COLUMNS = ["product_id", "region", "category"]
PREDICTION_PATTERN = "predictions_*.csv"
DEFAULT_MAPE_DEGRADATION_PCT = 0.25

VIOLATION_CATEGORY = {
    "SCHEMA": "SCHEMA",
    "DATA_QUALITY": "DATA_QUALITY",
    "FEATURE_DRIFT_MEAN": "DATA_DRIFT",
    "FEATURE_DRIFT_STD": "DATA_DRIFT",
    "PSI_DRIFT": "DATA_DRIFT",
    "NEW_CATEGORY": "DATA_DRIFT",
    "PREDICTION_DRIFT": "MODEL_DRIFT",
    "MAPE_DEGRADATION": "MODEL_DRIFT",
}

CATEGORY_DESCRIPTION = {
    "SCHEMA": "SCHEMA - required columns are missing (hard failure)",
    "DATA_QUALITY": "DATA QUALITY - input data has gaps/nulls beyond thresholds",
    "DATA_DRIFT": "DATA DRIFT - input feature distribution changed vs training",
    "MODEL_DRIFT": "MODEL DRIFT - predictions shifted or observed accuracy degraded",
}


def _numeric_stats(series: pd.Series) -> dict[str, float]:
    values = pd.to_numeric(series, errors="coerce")
    finite_mask = np.isfinite(values.to_numpy(dtype=float))
    finite = values[finite_mask]
    if finite.empty:
        raise ValueError(f"Cannot baseline numeric column '{series.name}': no finite values.")
    return {
        "mean": float(finite.mean()),
        "std": float(finite.std(ddof=0)),
        "min": float(finite.min()),
        "max": float(finite.max()),
        "p05": float(finite.quantile(0.05)),
        "p50": float(finite.quantile(0.50)),
        "p95": float(finite.quantile(0.95)),
        "missing_rate": float(1.0 - finite_mask.mean()),
    }


def create_baseline() -> dict[str, object]:
    """Create reference statistics and categorical constraints from training history."""
    ensure_dirs()
    banner("MODEL MONITOR - CREATE BASELINE (one-time)")
    if not s3_exists(OFFLINE_FILE):
        raise FileNotFoundError(
            f"Offline feature store is missing: {OFFLINE_FILE}. "
            "Run 03_feature_store.py first."
        )

    offline = pd.read_parquet(OFFLINE_FILE)
    required = {"date", *FEATURE_COLUMNS, TARGET_COLUMN, *CATEGORICAL_COLUMNS}
    missing = sorted(required.difference(offline.columns))
    if missing:
        raise ValueError(f"Offline feature store is missing baseline columns: {missing}")
    offline["date"] = pd.to_datetime(offline["date"], errors="coerce")
    if offline["date"].isna().any():
        raise ValueError("Offline feature store contains invalid dates.")

    latest_date = offline["date"].max()
    cutoff = latest_date - pd.Timedelta(days=TEST_DAYS)
    baseline = offline.loc[offline["date"] <= cutoff].copy()
    if baseline.empty:
        raise ValueError(
            f"No training rows before {cutoff.date()} are available for the baseline."
        )
    print(f"Baseline rows: {len(baseline):,} | training through {cutoff.date()}")

    numeric_columns = list(dict.fromkeys([*FEATURE_COLUMNS, TARGET_COLUMN]))
    statistics = {
        column: _numeric_stats(baseline[column])
        for column in numeric_columns
    }
    constraints = {
        "num_rows_baseline": int(len(baseline)),
        "date_min": baseline["date"].min().isoformat(),
        "date_max": baseline["date"].max().isoformat(),
        "numeric_columns": numeric_columns,
        "categorical_columns": {
            column: sorted(baseline[column].dropna().astype(str).unique().tolist())
            for column in CATEGORICAL_COLUMNS
        },
        "thresholds": dict(DRIFT_THRESHOLDS),
    }
    baseline_payload = {
        "created_at": datetime.now().astimezone().isoformat(),
        "baseline_rows": int(len(baseline)),
        "training_cutoff": cutoff.isoformat(),
        "numeric_stats": statistics,
    }
    prediction_files = s3_glob(PREDICTIONS_DIR, PREDICTION_PATTERN)
    if prediction_files:
        reference_predictions = pd.read_csv(prediction_files[-1])
        if "abs_pct_error" in reference_predictions.columns:
            reference_mape_values = _finite_values(reference_predictions["abs_pct_error"])
            if reference_mape_values.size:
                baseline_payload["test_mape"] = float(reference_mape_values.mean())
                baseline_payload["test_mape_source"] = prediction_files[-1].rsplit("/", 1)[-1]
    constraints["thresholds"]["mape_degradation_pct"] = float(
        DRIFT_THRESHOLDS.get(
            "mape_degradation_pct",
            DEFAULT_MAPE_DEGRADATION_PCT,
        )
    )

    write_text(BASELINE_STATS, json.dumps(baseline_payload, indent=2))
    write_text(BASELINE_CONSTRAINTS, json.dumps(constraints, indent=2))
    print(f"Baseline statistics: {BASELINE_STATS}")
    print(f"Baseline constraints: {BASELINE_CONSTRAINTS}")
    print(f"Numeric columns: {len(numeric_columns)} | categorical columns: {len(CATEGORICAL_COLUMNS)}")
    return baseline_payload


def _psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Calculate population stability index using baseline quantiles as bin edges."""
    expected = expected[np.isfinite(expected)]
    actual = actual[np.isfinite(actual)]
    if expected.size < 2 or actual.size < 2:
        return 0.0

    edges = np.unique(np.quantile(expected, np.linspace(0, 1, bins + 1)))
    if edges.size < 3:
        return 0.0
    edges[0] = -np.inf
    edges[-1] = np.inf
    expected_counts = np.histogram(expected, bins=edges)[0].astype(float)
    actual_counts = np.histogram(actual, bins=edges)[0].astype(float)
    expected_pct = expected_counts / expected_counts.sum()
    actual_pct = actual_counts / actual_counts.sum()
    epsilon = 1e-6
    expected_pct = np.clip(expected_pct, epsilon, None)
    actual_pct = np.clip(actual_pct, epsilon, None)
    return float(np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct)))


def _load_json(path, description: str) -> dict[str, object]:
    try:
        data = json.loads(read_text(path))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not load {description} {path}: {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"{description} must contain a JSON object: {path}")
    return data


def _load_latest_predictions() -> pd.DataFrame:
    prediction_files = s3_glob(PREDICTIONS_DIR, PREDICTION_PATTERN)
    if not prediction_files:
        raise FileNotFoundError(
            f"No batch prediction CSV found in {PREDICTIONS_DIR}. "
            "Run 06_batch_inference.py first."
        )
    latest_file = prediction_files[-1]
    predictions = pd.read_csv(latest_file)
    required = {"date", "product_id", "region", "predicted_cost"}
    missing = sorted(required.difference(predictions.columns))
    if missing:
        raise ValueError(f"Prediction file {latest_file} is missing columns: {missing}")
    predictions["date"] = pd.to_datetime(predictions["date"], errors="coerce").dt.normalize()
    if predictions["date"].isna().any():
        raise ValueError(f"Prediction file {latest_file} contains invalid dates.")
    print(f"Monitoring prediction file: {latest_file}")
    return predictions


def _finite_values(series: pd.Series) -> np.ndarray:
    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    return values[np.isfinite(values)]


def monitor() -> dict[str, object]:
    """Compare the latest prediction window with the saved training baseline."""
    ensure_dirs()
    banner("MODEL MONITOR - DAILY DRIFT CHECK")
    if not s3_exists(BASELINE_STATS) or not s3_exists(BASELINE_CONSTRAINTS):
        raise FileNotFoundError(
            f"Baseline missing. Run `python 08_model_monitoring.py baseline` first."
        )
    if not s3_exists(OFFLINE_FILE):
        raise FileNotFoundError(
            f"Offline feature store is missing: {OFFLINE_FILE}. "
            "Run 03_feature_store.py first."
        )

    baseline_data = _load_json(BASELINE_STATS, "baseline statistics")
    constraints = _load_json(BASELINE_CONSTRAINTS, "baseline constraints")
    stats = baseline_data.get("numeric_stats")
    thresholds = constraints.get("thresholds")
    categorical = constraints.get("categorical_columns")
    if not isinstance(stats, dict) or not isinstance(thresholds, dict) or not isinstance(categorical, dict):
        raise ValueError("Baseline files are missing numeric statistics or constraint sections.")
    if not isinstance(constraints.get("num_rows_baseline"), int):
        raise ValueError("Baseline constraints have no valid num_rows_baseline value.")

    predictions = _load_latest_predictions()
    offline = pd.read_parquet(OFFLINE_FILE)
    required_offline = {"date", "product_id", "region"}
    missing_offline = sorted(required_offline.difference(offline.columns))
    if missing_offline:
        raise ValueError(f"Offline feature store is missing monitor columns: {missing_offline}")
    offline["date"] = pd.to_datetime(offline["date"], errors="coerce").dt.normalize()
    if offline["date"].isna().any():
        raise ValueError("Offline feature store contains invalid dates.")

    start_date = predictions["date"].min()
    end_date = predictions["date"].max()
    today = offline.loc[offline["date"].between(start_date, end_date)].copy()
    today = today.merge(
        predictions[["date", "product_id", "region", "predicted_cost", *(
            ["actual_cost", "abs_pct_error"]
            if "actual_cost" in predictions.columns and "abs_pct_error" in predictions.columns
            else []
        )]],
        on=["date", "product_id", "region"],
        how="inner",
        suffixes=("", "_prediction"),
    )
    if today.empty:
        raise ValueError(
            "The latest prediction dates did not match any rows in the offline feature store."
        )
    print(
        f"Current feature rows: {len(today):,} | "
        f"{start_date.date()} through {end_date.date()}"
    )

    violations: list[dict[str, object]] = []
    required_today = set(stats).union(CATEGORICAL_COLUMNS)
    missing_columns = sorted(required_today.difference(today.columns))
    for column in missing_columns:
        violations.append(
            {
                "type": "SCHEMA",
                "feature": column,
                "detail": "required column missing from current feature data",
            }
        )

    missing_rate_threshold = float(thresholds["missing_rate_max"])
    for column in stats:
        if column not in today.columns:
            continue
        values = pd.to_numeric(today[column], errors="coerce")
        missing_rate = float(1.0 - np.isfinite(values.to_numpy(dtype=float)).mean())
        if missing_rate > missing_rate_threshold:
            violations.append(
                {
                    "type": "DATA_QUALITY",
                    "feature": column,
                    "missing_rate": round(missing_rate, 4),
                    "threshold": missing_rate_threshold,
                }
            )
        current_values = _finite_values(values)
        baseline_stats = stats[column]
        if current_values.size == 0:
            violations.append(
                {
                    "type": "DATA_QUALITY",
                    "feature": column,
                    "detail": "no finite numeric values in current window",
                }
            )
            continue

        baseline_mean = float(baseline_stats["mean"])
        baseline_std = float(baseline_stats["std"])
        relative_mean_shift = abs(float(current_values.mean()) - baseline_mean) / max(
            abs(baseline_mean), 1e-9
        )
        if relative_mean_shift > float(thresholds["mean_shift_pct"]):
            violations.append(
                {
                    "type": "FEATURE_DRIFT_MEAN",
                    "feature": column,
                    "baseline_mean": baseline_mean,
                    "current_mean": float(current_values.mean()),
                    "shift_pct": round(relative_mean_shift, 4),
                    "threshold": float(thresholds["mean_shift_pct"]),
                }
            )

        relative_std_shift = abs(float(current_values.std()) - baseline_std) / max(
            abs(baseline_std), 1e-9
        )
        if relative_std_shift > float(thresholds["std_shift_pct"]):
            violations.append(
                {
                    "type": "FEATURE_DRIFT_STD",
                    "feature": column,
                    "baseline_std": baseline_std,
                    "current_std": float(current_values.std()),
                    "shift_pct": round(relative_std_shift, 4),
                    "threshold": float(thresholds["std_shift_pct"]),
                }
            )

        baseline_rows = offline.loc[
            offline["date"] <= pd.to_datetime(constraints["date_max"]),
            column,
        ] if column in offline.columns else pd.Series(dtype=float)
        expected_values = _finite_values(baseline_rows)
        psi_value = _psi(expected_values, current_values)
        if psi_value > float(thresholds["psi_threshold"]):
            violations.append(
                {
                    "type": "PSI_DRIFT",
                    "feature": column,
                    "psi": round(psi_value, 4),
                    "threshold": float(thresholds["psi_threshold"]),
                }
            )

    for column, allowed_values in categorical.items():
        if column not in today.columns:
            continue
        if not isinstance(allowed_values, list):
            raise ValueError(f"Categorical baseline values for {column} must be a list.")
        unseen = sorted(set(today[column].dropna().astype(str)).difference(map(str, allowed_values)))
        if unseen and bool(thresholds.get("new_category_alert", True)):
            violations.append(
                {
                    "type": "NEW_CATEGORY",
                    "feature": column,
                    "new_values": unseen,
                }
            )

    prediction_values = _finite_values(today["predicted_cost"])
    if prediction_values.size == 0:
        violations.append(
            {"type": "DATA_QUALITY", "feature": "predicted_cost", "detail": "no finite predictions"}
        )
        today_prediction_mean = None
    else:
        today_prediction_mean = float(prediction_values.mean())
        target_stats = stats.get(TARGET_COLUMN)
        if isinstance(target_stats, dict):
            baseline_target_mean = float(target_stats["mean"])
            prediction_shift = abs(today_prediction_mean - baseline_target_mean) / max(
                abs(baseline_target_mean), 1e-9
            )
            if prediction_shift > float(thresholds["prediction_shift_pct"]):
                violations.append(
                    {
                        "type": "PREDICTION_DRIFT",
                        "baseline_target_mean": baseline_target_mean,
                        "current_prediction_mean": today_prediction_mean,
                        "shift_pct": round(prediction_shift, 4),
                        "threshold": float(thresholds["prediction_shift_pct"]),
                    }
                )

    today_mape: float | None = None
    if "abs_pct_error" in today.columns:
        mape_values = _finite_values(today["abs_pct_error"])
        if mape_values.size:
            today_mape = float(mape_values.mean())
    baseline_mape = baseline_data.get("test_mape")
    if today_mape is not None and isinstance(baseline_mape, (int, float)):
        mape_degradation = (today_mape - float(baseline_mape)) / max(
            abs(float(baseline_mape)), 1e-9
        )
        mape_threshold = float(
            thresholds.get("mape_degradation_pct", DEFAULT_MAPE_DEGRADATION_PCT)
        )
        if mape_degradation > mape_threshold:
            violations.append(
                {
                    "type": "MAPE_DEGRADATION",
                    "baseline_mape": float(baseline_mape),
                    "current_mape": today_mape,
                    "degradation_pct": round(mape_degradation, 4),
                    "threshold": mape_threshold,
                }
            )

    for violation in violations:
        violation["category"] = VIOLATION_CATEGORY.get(str(violation["type"]), "UNION")

    counts = Counter(str(item["category"]) for item in violations)
    report = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "baseline_rows": constraints["num_rows_baseline"],
        "current_rows": int(len(today)),
        "window_start": start_date.isoformat(),
        "window_end": end_date.isoformat(),
        "today_prediction_mean": today_prediction_mean,
        "today_mape": today_mape,
        "violation_count": len(violations),
        "violations_by_category": dict(counts),
        "violations": violations,
    }
    report_path = s3_path(
        "monitoring", "reports", f"model_monitor_{datetime.now():%Y%m%d_%H%M%S}.json"
    )
    write_text(report_path, json.dumps(report, indent=2))

    print(f"Report: {report_path}")
    print(f"Violations: {len(violations)}")
    if violations:
        print("ALERT: Drift / data quality violations detected.")
        print("SUMMARY BY CATEGORY:")
        for category, count in sorted(counts.items()):
            print(f"  {CATEGORY_DESCRIPTION.get(category, category)}: {count} violation(s)")
        print("\nVIOLATION DETAILS:")
        for category in sorted(counts):
            category_violations = [
                item for item in violations if item["category"] == category
            ]
            print(f"\n[{category}] {len(category_violations)} violation(s)")
            for violation in category_violations:
                details = ", ".join(
                    f"{key}={value}"
                    for key, value in violation.items()
                    if key not in {"category", "type"}
                )
                print(f"  {violation['type']}: {details}")
        print("\nRECOMMENDED ACTIONS:")
        if counts.get("SCHEMA"):
            print("  - Schema breach: fix the feature pipeline before relying on this report.")
        if counts.get("DATA_QUALITY"):
            print("  - Data quality breach: check upstream sources for missing values or outages.")
        if counts.get("DATA_DRIFT"):
            print("  - Data drift: investigate new products, regions, seasonality, or market changes.")
        if counts.get("MODEL_DRIFT"):
            print("  - Model drift: review prediction quality and consider retraining (stages 4-5).")
    else:
        print("No violations. Model and feature data are within configured thresholds.")
    return report


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "monitor"
    if command == "baseline":
        create_baseline()
    elif command == "monitor":
        monitor()
    else:
        raise SystemExit("Usage: python 08_model_monitoring.py [baseline|monitor]")


if __name__ == "__main__":
    main()
