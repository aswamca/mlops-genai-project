"""Small, reproducible local model-training example."""

from pathlib import Path

import joblib
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def train_model(output_path: str | Path = "artifacts/iris_model.joblib") -> float:
	"""Train and persist a baseline classifier, returning test accuracy."""
	dataset = load_iris()
	features_train, features_test, labels_train, labels_test = train_test_split(
		dataset.data, dataset.target, test_size=0.2, random_state=42, stratify=dataset.target
	)
	model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, random_state=42))
	model.fit(features_train, labels_train)
	accuracy = accuracy_score(labels_test, model.predict(features_test))
	destination = Path(output_path)
	destination.parent.mkdir(parents=True, exist_ok=True)
	joblib.dump(model, destination)
	return float(accuracy)


if __name__ == "__main__":
	print(f"Test accuracy: {train_model():.3f}")
