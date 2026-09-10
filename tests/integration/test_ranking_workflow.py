import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from variantrank.evaluation.workflow import run_ranking_evaluation
from variantrank.features import MODEL_CATEGORICAL_FEATURES, MODEL_NUMERIC_FEATURES


class SignalModel:
    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        score = features["allele_frequency"].to_numpy()
        return np.column_stack([1.0 - score, score])


def test_ranking_workflow_persists_reproducible_metrics(tmp_path: Path) -> None:
    rows = 140
    dataset = tmp_path / "features.parquet"
    model = tmp_path / "model.joblib"
    output = tmp_path / "evaluation" / "ranking.json"
    target = [0, 1] * (rows // 2)
    frame = pd.DataFrame(
        {
            "gene": [f"GENE{index // 2}" for index in range(rows)],
            "target": target,
            "high_confidence": [True] * rows,
        }
    )
    for name in MODEL_NUMERIC_FEATURES:
        frame[name] = [float(value) for value in target]
    for name in MODEL_CATEGORICAL_FEATURES:
        frame[name] = [f"{name}_{value}" for value in target]
    frame.to_parquet(dataset, index=False)
    joblib.dump(SignalModel(), model)

    result = run_ranking_evaluation(
        dataset,
        model,
        output,
        patients=10,
        variants_per_patient=10,
    )
    persisted = json.loads(output.read_text())

    assert result.simulated_patient_metrics["mrr"] == 1.0
    assert result.simulated_patient_metrics["recall_at_1"] == 1.0
    assert persisted["model_sha256"]
    assert persisted["simulation"]["patients"] == 10
