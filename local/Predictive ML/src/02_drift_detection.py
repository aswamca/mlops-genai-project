"""Lightweight population stability index drift detection."""

import numpy as np


def population_stability_index(
	reference: np.ndarray, current: np.ndarray, bins: int = 10
) -> float:
	"""Calculate PSI for numeric reference and current samples."""
	reference = np.asarray(reference, dtype=float)
	current = np.asarray(current, dtype=float)
	if reference.size == 0 or current.size == 0:
		raise ValueError("Both reference and current samples must contain values")
	if bins < 2:
		raise ValueError("bins must be at least 2")

	edges = np.unique(np.quantile(reference, np.linspace(0, 1, bins + 1)))
	if edges.size < 2:
		return 0.0
	reference_counts, _ = np.histogram(reference, bins=edges)
	current_counts, _ = np.histogram(current, bins=edges)
	reference_rates = np.clip(reference_counts / reference.size, 1e-6, None)
	current_rates = np.clip(current_counts / current.size, 1e-6, None)
	return float(np.sum((current_rates - reference_rates) * np.log(current_rates / reference_rates)))


def drift_status(psi: float, warning_threshold: float = 0.1, alert_threshold: float = 0.25) -> str:
	"""Classify PSI using common warning and alert thresholds."""
	if psi >= alert_threshold:
		return "alert"
	if psi >= warning_threshold:
		return "warning"
	return "stable"


if __name__ == "__main__":
	baseline = np.random.default_rng(7).normal(0, 1, 1_000)
	current = np.random.default_rng(8).normal(0.2, 1, 1_000)
	psi = population_stability_index(baseline, current)
	print({"psi": round(psi, 4), "status": drift_status(psi)})
