import json
from pathlib import Path

import pandas as pd

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

    assert set(result.metrics) == {"dummy", "logistic_regression"}
    assert (result.artifact_dir / "dummy.joblib").is_file()
    assert (result.artifact_dir / "logistic_regression.joblib").is_file()
    assert metadata["strategy"] == "gene"
    assert metadata["feature_set"] == "basic_variant_v1"
    assert len(metadata["dataset_sha256"]) == 64
