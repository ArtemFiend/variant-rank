import json
from pathlib import Path

import pandas as pd

from variantrank.features import MODEL_CATEGORICAL_FEATURES, MODEL_NUMERIC_FEATURES
from variantrank.models.calibration import run_calibration_experiment
from variantrank.models.catboost import CatBoostConfig
from variantrank.models.training import run_baseline_experiment


def test_baseline_experiment_persists_reproducible_artifacts(tmp_path: Path) -> None:
    rows = 140
    dataset = tmp_path / "clinvar.parquet"
    frame = pd.DataFrame(
        {
            "chrom": [str(index % 22 + 1) for index in range(rows)],
            "ref": ["A", "C"] * (rows // 2),
            "alt": ["G", "T"] * (rows // 2),
            "variant_type": ["single nucleotide variant"] * rows,
            "gene": [f"GENE{index // 2}" for index in range(rows)],
            "target": [0, 1] * (rows // 2),
        }
    )
    frame.to_parquet(dataset, index=False)

    result = run_baseline_experiment(dataset, tmp_path / "artifacts", strategy="gene")
    metadata = json.loads((result.artifact_dir / "metadata.json").read_text())

    assert set(result.metrics) == {"dummy", "logistic_regression", "random_forest"}
    assert (result.artifact_dir / "dummy.joblib").is_file()
    assert (result.artifact_dir / "logistic_regression.joblib").is_file()
    assert (result.artifact_dir / "random_forest.joblib").is_file()
    assert metadata["strategy"] == "gene"
    assert metadata["feature_set"] == "basic_variant_v1"
    assert len(metadata["dataset_sha256"]) == 64


def test_annotated_baselines_use_persisted_feature_contract(tmp_path: Path) -> None:
    rows = 140
    dataset = tmp_path / "features.parquet"
    frame = pd.DataFrame(
        {
            "gene": [f"GENE{index // 2}" for index in range(rows)],
            "target": [0, 1] * (rows // 2),
            "high_confidence": [True] * 120 + [False] * 20,
        }
    )
    for name in MODEL_NUMERIC_FEATURES:
        frame[name] = [float(index % 5) for index in range(rows)]
    for name in MODEL_CATEGORICAL_FEATURES:
        frame[name] = [f"{name}_{index % 3}" for index in range(rows)]
    frame.to_parquet(dataset, index=False)

    result = run_baseline_experiment(
        dataset,
        tmp_path / "artifacts",
        strategy="random",
        feature_set="annotated",
        high_confidence_only=True,
        include_catboost=True,
        catboost_config=CatBoostConfig(iterations=5, depth=3, learning_rate=0.1),
    )
    metadata = json.loads((result.artifact_dir / "metadata.json").read_text())

    assert set(result.metrics) == {
        "catboost",
        "dummy",
        "logistic_regression",
        "random_forest",
    }
    assert (result.artifact_dir / "catboost.joblib").is_file()
    assert metadata["feature_set"] == "annotated_vep_v1"
    assert metadata["cohort"] == "high_confidence"
    assert metadata["dataset_rows"] == 120
    assert metadata["numeric_features"] == MODEL_NUMERIC_FEATURES
    assert metadata["catboost"]["iterations"] == 5

    calibration = run_calibration_experiment(
        dataset,
        result.artifact_dir,
        strategy="random",
        high_confidence_only=True,
        minimum_recall=0.50,
        minimum_precision=0.50,
    )
    calibration_metadata = json.loads((calibration.artifact_dir / "metadata.json").read_text())

    assert set(calibration.metrics) == {"raw", "platt", "isotonic"}
    assert (calibration.artifact_dir / "random_forest_platt.joblib").is_file()
    assert (calibration.artifact_dir / "random_forest_isotonic.joblib").is_file()
    assert calibration.operating_points_path.is_file()
    assert calibration_metadata["dataset_rows"] == 120
    assert calibration_metadata["calibration_partition_rows"] == 18
