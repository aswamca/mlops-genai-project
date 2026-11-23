import importlib.util
import sys

import pandas as pd


def _load_preprocessor():
    source = (
        __file__.replace("\\tests\\test_preprocesssing.py", "")
        + "\\PredML\\src\\01_preprocess.py"
    )
    spec = importlib.util.spec_from_file_location("preprocess_stage", source)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, source.rsplit("\\", 2)[0])
    spec.loader.exec_module(module)
    return module


def test_missing_actual_cost_is_reported_and_not_imputed(tmp_path, monkeypatch):
    module = _load_preprocessor()
    raw_file = tmp_path / "raw.csv"
    processed_file = tmp_path / "processed.parquet"
    ops_review_file = tmp_path / "ops_review.csv"

    pd.DataFrame(
        [
            {
                "date": "2025-01-01",
                "product_id": "P1",
                "product_name": "Product 1",
                "category": "Category",
                "region": "NA",
                "sales": 100.0,
                "actual_cost": 25.0,
            },
            {
                "date": "2025-01-02",
                "product_id": "P1",
                "product_name": "Product 1",
                "category": "Category",
                "region": "NA",
                "sales": 110.0,
                "actual_cost": None,
            },
        ]
    ).to_csv(raw_file, index=False)

    monkeypatch.setattr(module, "RAW_FILE", raw_file)
    monkeypatch.setattr(module, "PROCESSED_FILE", processed_file)
    monkeypatch.setattr(module, "OPS_REVIEW_FILE", ops_review_file)
    monkeypatch.setattr(module, "ensure_dirs", lambda: None)

    module.preprocess_data()

    clean = pd.read_parquet(processed_file)
    review = pd.read_csv(ops_review_file)
    assert len(clean) == 1
    assert clean["actual_cost"].notna().all()
    assert review["issue_type"].tolist() == ["missing_actual_cost"]