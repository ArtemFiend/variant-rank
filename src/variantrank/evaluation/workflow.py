"""Persisted-model ranking evaluation workflow."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from variantrank.data.download import file_digest
from variantrank.evaluation.ranking import ranking_metrics, simulate_patient_rankings
from variantrank.models.training import FeatureSet, SplitStrategy, _load_features, _make_split


@dataclass(frozen=True, slots=True)
class RankingEvaluationResult:
    """Ranking metrics and their persisted JSON artifact."""

    output: Path
    global_metrics: dict[str, float]
    simulated_patient_metrics: dict[str, float]


def run_ranking_evaluation(
    dataset: Path,
    model_path: Path,
    output: Path,
    *,
    strategy: SplitStrategy = "gene",
    feature_set: FeatureSet = "annotated",
    high_confidence_only: bool = False,
    random_seed: int = 42,
    patients: int = 1000,
    variants_per_patient: int = 50,
) -> RankingEvaluationResult:
    """Evaluate global and simulated-patient ranking on the held-out test split."""
    if not dataset.is_file() or not model_path.is_file():
        raise FileNotFoundError("ranking evaluation requires dataset and model files")
    variants, features, _, _ = _load_features(
        dataset,
        feature_set=feature_set,
        high_confidence_only=high_confidence_only,
    )
    target = variants["target"].astype("int8")
    split = _make_split(target, variants["gene"], strategy, random_seed)
    test_target = target.iloc[split.test].to_numpy()
    model: Any = joblib.load(model_path)
    probability = np.asarray(model.predict_proba(features.iloc[split.test]))[:, 1]

    global_cutoffs = tuple(cutoff for cutoff in (10, 100, 1000) if cutoff <= len(test_target))
    global_metrics = ranking_metrics(test_target, probability, cutoffs=global_cutoffs)
    patient_cutoffs = tuple(cutoff for cutoff in (1, 5, 10) if cutoff <= variants_per_patient)
    simulated = simulate_patient_rankings(
        test_target,
        probability,
        patients=patients,
        variants_per_patient=variants_per_patient,
        cutoffs=patient_cutoffs,
        random_seed=random_seed,
    )
    payload = {
        "dataset": str(dataset),
        "dataset_sha256": file_digest(dataset),
        "model": str(model_path),
        "model_sha256": file_digest(model_path),
        "strategy": strategy,
        "cohort": "high_confidence" if high_confidence_only else "all",
        "feature_set": feature_set,
        "random_seed": random_seed,
        "test_rows": len(test_target),
        "test_pathogenic": int(test_target.sum()),
        "global": global_metrics,
        "simulation": {
            "patients": patients,
            "variants_per_patient": variants_per_patient,
            "pathogenic_per_patient": 1,
            "metrics": simulated,
        },
    }
    _write_json(output, payload)
    return RankingEvaluationResult(output, global_metrics, simulated)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".partial")
    partial.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    partial.replace(path)
