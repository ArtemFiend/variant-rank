"""Probability calibration workflow for persisted baseline estimators."""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import joblib
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator

from variantrank.data.download import file_digest
from variantrank.evaluation import classification_metrics
from variantrank.evaluation.thresholds import select_operating_points
from variantrank.models.training import (
    FeatureSet,
    SplitStrategy,
    _load_features,
    _make_split,
)

CALIBRATION_METHODS = {"platt": "sigmoid", "isotonic": "isotonic"}


@dataclass(frozen=True, slots=True)
class CalibrationExperimentResult:
    """Paths and held-out metrics from a calibration comparison."""

    artifact_dir: Path
    metrics_path: Path
    operating_points_path: Path
    metrics: dict[str, dict[str, float]]


def run_calibration_experiment(
    dataset: Path,
    baseline_artifact_dir: Path,
    *,
    strategy: SplitStrategy,
    feature_set: FeatureSet = "annotated",
    high_confidence_only: bool = False,
    random_seed: int = 42,
    minimum_recall: float = 0.90,
    minimum_precision: float = 0.90,
) -> CalibrationExperimentResult:
    """Calibrate a fitted Random Forest on validation data and evaluate on test data."""
    metadata_path = baseline_artifact_dir / "metadata.json"
    model_path = baseline_artifact_dir / "random_forest.joblib"
    if not metadata_path.is_file() or not model_path.is_file():
        raise FileNotFoundError("baseline metadata.json and random_forest.joblib are required")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    cohort = "high_confidence" if high_confidence_only else "all"
    feature_version = "basic_variant_v1" if feature_set == "basic" else "annotated_vep_v1"
    expected = {
        "dataset_sha256": file_digest(dataset),
        "strategy": strategy,
        "random_seed": random_seed,
        "feature_set": feature_version,
        "cohort": cohort,
    }
    mismatches = [key for key, value in expected.items() if metadata.get(key) != value]
    if mismatches:
        raise ValueError(f"baseline metadata mismatch: {', '.join(mismatches)}")

    variants, features, _, _ = _load_features(
        dataset,
        feature_set=feature_set,
        high_confidence_only=high_confidence_only,
    )
    target = variants["target"].astype("int8")
    split = _make_split(target, variants["gene"], strategy, random_seed)
    validation_features = features.iloc[split.validation]
    validation_target = target.iloc[split.validation].to_numpy()
    test_features = features.iloc[split.test]
    test_target = target.iloc[split.test].to_numpy()
    raw_model = joblib.load(model_path)

    artifact_dir = baseline_artifact_dir / "calibration"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    metrics: dict[str, dict[str, float]] = {
        "raw": classification_metrics(test_target, raw_model.predict_proba(test_features)[:, 1])
    }
    operating_points: dict[str, dict[str, dict[str, Any]]] = {}
    durations: dict[str, float] = {}

    for name, method in CALIBRATION_METHODS.items():
        started = perf_counter()
        calibrated = CalibratedClassifierCV(FrozenEstimator(raw_model), method=method)
        calibrated.fit(validation_features, validation_target)
        durations[name] = perf_counter() - started
        validation_probability = calibrated.predict_proba(validation_features)[:, 1]
        selected = select_operating_points(
            validation_target,
            validation_probability,
            minimum_recall=minimum_recall,
            minimum_precision=minimum_precision,
        )
        test_probability = calibrated.predict_proba(test_features)[:, 1]
        metrics[name] = classification_metrics(test_target, test_probability)
        operating_points[name] = {
            point_name: {
                "validation": asdict(point),
                "test": classification_metrics(
                    test_target,
                    test_probability,
                    threshold=point.threshold,
                ),
            }
            for point_name, point in selected.items()
        }
        joblib.dump(calibrated, artifact_dir / f"random_forest_{name}.joblib")

    metrics_path = artifact_dir / "metrics.json"
    operating_points_path = artifact_dir / "operating_points.json"
    _write_json(metrics_path, metrics)
    _write_json(operating_points_path, operating_points)
    _write_json(
        artifact_dir / "metadata.json",
        {
            "created_at": datetime.now(UTC).isoformat(),
            "source_model": str(model_path),
            "source_metadata": str(metadata_path),
            "dataset": str(dataset),
            "dataset_sha256": expected["dataset_sha256"],
            "dataset_rows": len(variants),
            "strategy": strategy,
            "feature_set": feature_version,
            "cohort": cohort,
            "random_seed": random_seed,
            "calibration_partition_rows": len(split.validation),
            "test_partition_rows": len(split.test),
            "minimum_recall": minimum_recall,
            "minimum_precision": minimum_precision,
            "training_seconds": durations,
        },
    )
    return CalibrationExperimentResult(
        artifact_dir=artifact_dir,
        metrics_path=metrics_path,
        operating_points_path=operating_points_path,
        metrics=metrics,
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
