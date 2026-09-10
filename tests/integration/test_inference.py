import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from variantrank.inference import InferenceError, predict_annotated_vcf

VCF_FIXTURE = Path(__file__).parents[1] / "fixtures" / "example.vep.vcf"


class FrequencyModel:
    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        score = 1.0 - features["population_max_af"].fillna(0.5).to_numpy()
        return np.column_stack([1.0 - score, score])


def test_predict_annotated_vcf_ranks_and_persists_variants(tmp_path: Path) -> None:
    annotations = tmp_path / "annotations.parquet"
    model = tmp_path / "model.joblib"
    output = tmp_path / "ranked.csv"
    _annotations().to_parquet(annotations, index=False)
    joblib.dump(FrequencyModel(), model)

    result = predict_annotated_vcf(
        VCF_FIXTURE,
        annotations,
        model,
        output,
        threshold=0.90,
    )

    persisted = pd.read_csv(output)
    assert result.rows == 3
    assert persisted["gene"].tolist() == ["BRCA2", "BARD1", "TP53"]
    assert persisted["score"].tolist() == pytest.approx([0.999, 0.95, 0.8])
    assert persisted["prediction"].tolist() == ["pathogenic", "pathogenic", "benign"]


def test_predict_rejects_annotation_key_mismatch(tmp_path: Path) -> None:
    annotations = tmp_path / "annotations.parquet"
    model = tmp_path / "model.joblib"
    output = tmp_path / "ranked.json"
    _annotations().iloc[:2].to_parquet(annotations, index=False)
    joblib.dump(FrequencyModel(), model)

    with pytest.raises(InferenceError, match="keys differ"):
        predict_annotated_vcf(VCF_FIXTURE, annotations, model, output)


def test_predict_writes_equivalent_json_output(tmp_path: Path) -> None:
    annotations = tmp_path / "annotations.parquet"
    model = tmp_path / "model.joblib"
    output = tmp_path / "nested" / "ranked.json"
    _annotations().to_parquet(annotations, index=False)
    joblib.dump(FrequencyModel(), model)

    predict_annotated_vcf(VCF_FIXTURE, annotations, model, output)

    records = json.loads(output.read_text())
    assert [record["rank"] for record in records] == [1, 2, 3]
    assert records[0]["gene"] == "BRCA2"


def test_predict_rejects_invalid_threshold(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        predict_annotated_vcf(
            VCF_FIXTURE,
            tmp_path / "annotations.parquet",
            tmp_path / "model.joblib",
            tmp_path / "ranked.csv",
            threshold=1.1,
        )


def _annotations() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "variant": ["17:7674220:C:T", "13:32340301:C:T", "13:32340301:C:G"],
            "gene": ["TP53", "BRCA2", "BARD1"],
            "consequence": ["missense_variant", "stop_gained", "frameshift_variant"],
            "impact": ["MODERATE", "HIGH", "HIGH"],
            "biotype": ["protein_coding"] * 3,
            "protein_position": [200, 1000, 500],
            "allele_frequency": [0.2, 0.001, 0.05],
            "population_max_af": [0.2, 0.001, 0.05],
            "afr_af": [0.2, 0.001, 0.05],
            "amr_af": [0.2, 0.001, 0.05],
            "eas_af": [0.2, 0.001, 0.05],
            "nfe_af": [0.2, 0.001, 0.05],
            "sas_af": [0.2, 0.001, 0.05],
            "rare_variant_flag": [False, True, False],
            "canonical": [True] * 3,
            "mane_select": ["NM_000546.6", "NM_000059.4", None],
        }
    )
