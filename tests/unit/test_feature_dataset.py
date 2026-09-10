import json
from pathlib import Path

import pandas as pd
import pytest

from variantrank.features import FeatureDatasetError, build_feature_dataset


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    labels = tmp_path / "labels.parquet"
    annotations = tmp_path / "annotations.parquet"
    pd.DataFrame(
        {
            "variant_id": ["17:7674220:C:T", "13:32340301:C:G"],
            "gene": ["TP53", "BRCA2"],
            "target": [1, 0],
            "high_confidence": [True, True],
            "chrom": ["17", "13"],
            "ref": ["C", "C"],
            "alt": ["T", "G"],
            "variant_type": ["single nucleotide variant", "single nucleotide variant"],
            "clinical_significance": ["Pathogenic", "Benign"],
        }
    ).to_parquet(labels, index=False)
    pd.DataFrame(
        {
            "variant": ["17:7674220:C:T", "13:32340301:C:G"],
            "gene": ["VEP_TP53", "VEP_BRCA2"],
            "consequence": ["missense_variant", "synonymous_variant"],
            "impact": ["MODERATE", "LOW"],
            "biotype": ["protein_coding", "protein_coding"],
            "protein_position": [248, 100],
            "allele_frequency": [0.00001, None],
            "population_max_af": [0.00003, None],
            "afr_af": [0.00003, None],
            "amr_af": [None, None],
            "eas_af": [None, None],
            "nfe_af": [0.00001, None],
            "sas_af": [None, None],
            "rare_variant_flag": [True, None],
            "canonical": [True, True],
            "mane_select": ["NM_000546.6", None],
        }
    ).to_parquet(annotations, index=False)
    return labels, annotations


def test_build_feature_dataset_writes_safe_contract_and_reuses_cache(tmp_path: Path) -> None:
    labels, annotations = _write_inputs(tmp_path)
    output = tmp_path / "features.parquet"

    first = build_feature_dataset(labels, annotations, output)
    second = build_feature_dataset(labels, annotations, output)
    frame = pd.read_parquet(output)
    manifest = json.loads(first.manifest.read_text())

    assert first.rows == 2
    assert second.cached is True
    assert frame["variant_id"].tolist() == ["17:7674220:C:T", "13:32340301:C:G"]
    assert frame["gene"].tolist() == ["TP53", "BRCA2"]
    assert frame.loc[0, "is_missense"] == 1
    assert "clinical_significance" not in frame
    assert "review_status" not in frame
    assert manifest["feature_dataset_version"] == 1
    assert manifest["rows"] == 2


def test_build_feature_dataset_requires_identical_key_sets(tmp_path: Path) -> None:
    labels, annotations = _write_inputs(tmp_path)
    frame = pd.read_parquet(annotations).iloc[:1]
    frame.to_parquet(annotations, index=False)

    with pytest.raises(FeatureDatasetError, match="1 missing annotations"):
        build_feature_dataset(labels, annotations, tmp_path / "features.parquet")


def test_build_feature_dataset_rejects_duplicate_annotation_keys(tmp_path: Path) -> None:
    labels, annotations = _write_inputs(tmp_path)
    frame = pd.read_parquet(annotations)
    pd.concat([frame, frame.iloc[[0]]], ignore_index=True).to_parquet(annotations, index=False)

    with pytest.raises(FeatureDatasetError, match="must be unique"):
        build_feature_dataset(labels, annotations, tmp_path / "features.parquet")


def test_build_feature_dataset_requires_both_sources(tmp_path: Path) -> None:
    missing_labels = tmp_path / "missing-labels.parquet"
    missing_annotations = tmp_path / "missing-annotations.parquet"

    with pytest.raises(FileNotFoundError, match="missing-labels"):
        build_feature_dataset(missing_labels, missing_annotations, tmp_path / "features.parquet")

    missing_labels.touch()
    with pytest.raises(FileNotFoundError, match="missing-annotations"):
        build_feature_dataset(missing_labels, missing_annotations, tmp_path / "features.parquet")


def test_build_feature_dataset_validates_source_schemas(tmp_path: Path) -> None:
    labels, annotations = _write_inputs(tmp_path)
    pd.DataFrame({"variant_id": ["1:1:A:G"]}).to_parquet(labels, index=False)

    with pytest.raises(FeatureDatasetError, match="label dataset is missing columns"):
        build_feature_dataset(labels, annotations, tmp_path / "features.parquet")

    labels, annotations = _write_inputs(tmp_path)
    pd.DataFrame({"variant": ["17:7674220:C:T"]}).to_parquet(annotations, index=False)
    with pytest.raises(FeatureDatasetError, match="annotation dataset is missing columns"):
        build_feature_dataset(labels, annotations, tmp_path / "features.parquet")


def test_build_feature_dataset_rejects_empty_and_duplicate_labels(tmp_path: Path) -> None:
    labels, annotations = _write_inputs(tmp_path)
    pd.read_parquet(labels).iloc[:0].to_parquet(labels, index=False)
    pd.read_parquet(annotations).iloc[:0].to_parquet(annotations, index=False)

    with pytest.raises(FeatureDatasetError, match="must not be empty"):
        build_feature_dataset(labels, annotations, tmp_path / "features.parquet")

    labels, annotations = _write_inputs(tmp_path)
    frame = pd.read_parquet(labels)
    pd.concat([frame, frame.iloc[[0]]], ignore_index=True).to_parquet(labels, index=False)
    with pytest.raises(FeatureDatasetError, match="label variant keys must be unique"):
        build_feature_dataset(labels, annotations, tmp_path / "features.parquet")
