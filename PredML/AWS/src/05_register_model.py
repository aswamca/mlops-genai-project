import json
from datetime import datetime, timezone

from config import (
    CHAMPION_PROMOTION_FILE,
    CHAMPION_ALIAS,
    MLFLOW_REGISTERED_MODEL_NAME,
    PREVIOUS_ALIAS,
    banner,
    ensure_dirs,
    write_text,
)
from mlflow_registry import (
    get_champion_version,
    get_latest_challenger_version,
    get_version_metrics,
    promote_to_champion,
    tag_version,
)


def register_and_evaluate() -> str:
    ensure_dirs()
    banner("STAGE 5 - CHAMPION VS CHALLENGER GATE (MLflow Model Registry)")

    challenger_version = get_latest_challenger_version()

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
        write_text(
            CHAMPION_PROMOTION_FILE,
            json.dumps(
                {
                    "model_name": MLFLOW_REGISTERED_MODEL_NAME,
                    "champion_version": challenger_version,
                    "previous_version": champion_version,
                    "promoted_at": promoted_at,
                }
            ),
        )
        print(f"Promoted version {challenger_version} to alias '{CHAMPION_ALIAS}'.")
        if champion_version is not None:
            print(f"Previous champion {champion_version} now has alias '{PREVIOUS_ALIAS}'.")
    elif decision == "REJECT":
        print(f"Version {challenger_version} remains registered as a challenger.")

    return decision


if __name__ == "__main__":
    register_and_evaluate()