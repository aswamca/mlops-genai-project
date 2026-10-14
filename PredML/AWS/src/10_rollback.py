from __future__ import annotations

import argparse
from datetime import datetime, timezone

import mlflow
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient

from config import (
    CHAMPION_ALIAS,
    MLFLOW_REGISTERED_MODEL_NAME,
    MLFLOW_URI,
    PREVIOUS_ALIAS,
)
from mlflow_registry import get_champion_version, promote_to_champion, tag_version


def _client() -> MlflowClient:
    mlflow.set_tracking_uri(MLFLOW_URI)
    return MlflowClient(tracking_uri=MLFLOW_URI)


def _alias_is_missing(error: MlflowException) -> bool:
    error_code = getattr(error, "error_code", None)
    message = str(error).lower()
    return (
        error_code in {"RESOURCE_DOES_NOT_EXIST", "INVALID_PARAMETER_VALUE"}
        or ("alias" in message and "not found" in message)
    )


def _version_for_alias(client: MlflowClient, alias: str) -> str | None:
    try:
        version = client.get_model_version_by_alias(
            MLFLOW_REGISTERED_MODEL_NAME,
            alias,
        )
    except MlflowException as error:
        if _alias_is_missing(error):
            return None
        raise
    return str(version.version)


def list_versions() -> None:
    """Print registered versions, their metrics, and the current champion."""
    versions = _client().search_model_versions(
        filter_string=f"name='{MLFLOW_REGISTERED_MODEL_NAME}'"
    )
    if not versions:
        print(
            f"No versions registered for '{MLFLOW_REGISTERED_MODEL_NAME}'. "
            "Run stages 4 and 5 first."
        )
        return

    client = _client()
    champion = get_champion_version()
    previous = _version_for_alias(client, PREVIOUS_ALIAS)
    print(f"\n{MLFLOW_REGISTERED_MODEL_NAME} - registered versions")
    print("-" * 72)
    print(
        f"{'VERSION':<10} {'ROLE TAG':<12} {'TEST MAPE':<14} "
        f"{'RUN ID':<20} {'ACTIVE ALIAS':<14}"
    )
    for version in sorted(versions, key=lambda item: int(item.version), reverse=True):
        tags = version.tags or {}
        assigned_aliases = [
            alias
            for alias, assigned_version in (
                (CHAMPION_ALIAS, champion),
                (PREVIOUS_ALIAS, previous),
            )
            if assigned_version == str(version.version)
        ]
        role_tag = tags.get("role", "-")
        active_aliases = ",".join(assigned_aliases) or "-"
        test_mape = tags.get("test_mape", "-")
        run_id = tags.get("run_id", "-")
        champion_mark = "  <-- champion" if str(version.version) == champion else ""
        print(
            f"{str(version.version):<10} {role_tag:<12} {test_mape:<14} "
            f"{run_id[:18]:<20} {active_aliases:<14}{champion_mark}"
        )


def sync_role_tags(dry_run: bool = False) -> None:
    """Correct stale champion/previous tags using MLflow aliases as authority."""
    client = _client()
    versions = client.search_model_versions(
        filter_string=f"name='{MLFLOW_REGISTERED_MODEL_NAME}'"
    )
    champion = get_champion_version()
    previous = _version_for_alias(client, PREVIOUS_ALIAS)
    updates: list[tuple[str, str]] = []

    for version in versions:
        version_id = str(version.version)
        current_role = (version.tags or {}).get("role")
        if version_id == champion:
            expected_role = "champion"
        elif version_id == previous:
            expected_role = "previous"
        elif current_role in {"champion", "previous"}:
            expected_role = "challenger"
        else:
            continue
        if current_role != expected_role:
            updates.append((version_id, expected_role))

    if not updates:
        print("All model role tags already match the active aliases.")
        return
    for version_id, expected_role in updates:
        print(f"Version {version_id}: role {expected_role!r}")
    if dry_run:
        print("Dry run: no model tags were changed.")
        return

    for version_id, expected_role in updates:
        tag_version(version_id, {"role": expected_role})
    print("Role tags synchronized with the active champion/previous aliases.")


def rollback(target_version: str, dry_run: bool = False) -> None:
    """Move the champion alias to a registered version, preserving the former champion."""
    target = str(target_version).strip()
    if not target.isdigit():
        raise ValueError(f"MLflow model version must be a positive integer: {target!r}")
    target = str(int(target))

    client = _client()
    versions = client.search_model_versions(
        filter_string=f"name='{MLFLOW_REGISTERED_MODEL_NAME}'"
    )
    available = {str(version.version) for version in versions}
    if target not in available:
        raise ValueError(
            f"Version {target} does not exist for '{MLFLOW_REGISTERED_MODEL_NAME}'. "
            f"Available versions: {sorted(available, key=int)}"
        )

    current = get_champion_version()
    if current == target:
        print(f"'{CHAMPION_ALIAS}' already points to version {target}; no change needed.")
        return

    print(f"{CHAMPION_ALIAS} currently points to: {current or 'no version'}")
    print(f"{CHAMPION_ALIAS} will point to:     {target}")
    if current is not None:
        print(f"{PREVIOUS_ALIAS} will point to:    {current}")

    if dry_run:
        print("\nDry run: no aliases or model tags were changed.")
        return

    rolled_back_at = datetime.now(timezone.utc).isoformat()
    promote_to_champion(target, current)
    tag_version(
        target,
        {
            "role": "champion",
            "rollback_at": rolled_back_at,
            "rollback_from": current or "none",
        },
    )
    if current is not None:
        tag_version(
            current,
            {
                "role": "previous",
                "demoted_at": rolled_back_at,
                "demoted_by": target,
            },
        )

    print(
        f"\nRollback complete: '{CHAMPION_ALIAS}' now points to version {target}. "
        "Restart the realtime inference service to load it."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List registered models or roll the champion alias back."
    )
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument(
        "--list",
        action="store_true",
        help="List registered model versions and identify the current champion.",
    )
    actions.add_argument(
        "--to-version",
        metavar="VERSION",
        help="Roll the champion alias back to a specific registered version.",
    )
    actions.add_argument(
        "--to-previous",
        action="store_true",
        help=f"Roll back to the version currently assigned to '{PREVIOUS_ALIAS}'.",
    )
    actions.add_argument(
        "--sync-roles",
        action="store_true",
        help="Correct stale role tags to match the active aliases.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the intended alias change without changing the registry.",
    )
    args = parser.parse_args()

    if args.list:
        list_versions()
        return

    if args.sync_roles:
        sync_role_tags(dry_run=args.dry_run)
        return

    if args.to_previous:
        previous_version = _version_for_alias(_client(), PREVIOUS_ALIAS)
        if previous_version is None:
            raise SystemExit(
                f"No '{PREVIOUS_ALIAS}' alias is set; there is no previous version to roll back to."
            )
        rollback(previous_version, dry_run=args.dry_run)
        return

    rollback(args.to_version, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
