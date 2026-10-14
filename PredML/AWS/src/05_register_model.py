from datetime import datetime, timezone

from config import (
    CHAMPION_ALIAS,
    MLFLOW_REGISTERED_MODEL_NAME,
    PREVIOUS_ALIAS,
    REGISTRY_DIR,
    banner,
    ensure_dirs,
    read_text,
    s3_exists,
)
from mlflow_registry import (
    get_champion_version,
    get_version_metrics,
    promote_to_champion,
    tag_version,
)


CHALLENGER_POINTER = f"{REGISTRY_DIR}/challenger_version.txt"


def register_and_evaluate() -> str:
    ensure_dirs()
    banner("STAGE 5 - CHAMPION VS CHALLENGER GATE (MLflow Model Registry)")

    if not s3_exists(CHALLENGER_POINTER):
        raise FileNotFoundError(
            f"No challenger pointer at {CHALLENGER_POINTER}. "
            "Run 04_train_model.py first."
        )

    challenger_version = read_text(CHALLENGER_POINTER).strip()
    if not challenger_version:
        raise ValueError(f"Challenger pointer is empty: {CHALLENGER_POINTER}")

    challenger_metrics = get_version_metrics(challenger_version)
    if "test_mape" not in challenger_metrics:
        raise RuntimeError(
            f"Version {challenger_version} has no test_mape tag. "
            "Train it with 04_train_model.py first."
        )

    challenger_mape = challenger_metrics["test_mape"]
    print(f"Challenger: {MLFLOW_REGISTERED_MODEL_NAME} v{challenger_version}")
    print(f"  test MAPE: {challenger_mape:.4f}")

    champion_version = get_champion_version()
    champion_mape = None
    if champion_version is None:
        print("No existing champion alias; promoting the first registered version.")
        decision = "PROMOTE"
    elif champion_version == challenger_version:
        print("Challenger is already the champion; skipping promotion.")
        decision = "SKIP"
    else:
        champion_metrics = get_version_metrics(champion_version)
        if "test_mape" not in champion_metrics:
            raise RuntimeError(
                f"Champion version {champion_version} has no test_mape tag."
            )
        champion_mape = champion_metrics["test_mape"]
        print(f"Champion: {MLFLOW_REGISTERED_MODEL_NAME} v{champion_version}")
        print(f"  test MAPE: {champion_mape:.4f}")

        if challenger_mape < champion_mape:
            print(f"Challenger improves test MAPE by {champion_mape - challenger_mape:.4f}.")
            decision = "PROMOTE"
        else:
            print(f"Challenger does not improve test MAPE ({challenger_mape - champion_mape:.4f} higher).")
            decision = "REJECT"

    if decision == "PROMOTE":
        promoted_at = datetime.now(timezone.utc).isoformat()
        promote_to_champion(challenger_version, champion_version)
        tag_version(
            challenger_version,
            {
                "role": "champion",
                "promoted_at": promoted_at,
                "promoted_from": champion_version or "none",
            },
        )
        if champion_version is not None:
            tag_version(
                champion_version,
                {
                    "role": "previous",
                    "demoted_at": promoted_at,
                    "demoted_by": challenger_version,
                },
            )
        print(f"Promoted version {challenger_version} to alias '{CHAMPION_ALIAS}'.")
        if champion_version is not None:
            print(f"Previous champion {champion_version} now has alias '{PREVIOUS_ALIAS}'.")
    elif decision == "REJECT":
        print(f"Version {challenger_version} remains registered as a challenger.")

    return decision


if __name__ == "__main__":
    register_and_evaluate()