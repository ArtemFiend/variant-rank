import json
from pathlib import Path

import pandas as pd
import pytest

from variantrank.data.clinvar import (
    ClinVarSchemaError,
    is_high_confidence_review,
    map_clinical_significance,
    prepare_clinvar_dataset,
)

FIXTURE = Path(__file__).parents[1] / "fixtures" / "clinvar_variant_summary.tsv"


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Pathogenic", 1),
        ("Likely pathogenic", 1),
        ("Pathogenic/Likely pathogenic", 1),
        ("Benign", 0),
        ("Benign/Likely benign", 0),
        ("Uncertain significance", None),
        ("Conflicting classifications of pathogenicity", None),
        ("Pathogenic; risk factor", None),
    ],
)
def test_map_clinical_significance(label: str, expected: int | None) -> None:
    assert map_clinical_significance(label) == expected


def test_high_confidence_review_mapping() -> None:
    assert is_high_confidence_review("reviewed by expert panel")
    assert is_high_confidence_review("criteria_provided,_multiple_submitters,_no_conflicts")
    assert not is_high_confidence_review("criteria provided, single submitter")


def test_prepare_clinvar_dataset_builds_auditable_outputs(tmp_path: Path) -> None:
    result = prepare_clinvar_dataset(FIXTURE, tmp_path, chunk_size=3)

    dataset_a = pd.read_parquet(result.dataset_a)
    dataset_b = pd.read_parquet(result.dataset_b)
    qc = json.loads(result.qc_report.read_text())
    metadata = json.loads(result.source_metadata.read_text())

    assert dataset_a["variant_id"].tolist() == ["1:100:A:G", "2:200:C:T", "4:402:C:T"]
    assert dataset_a["target"].tolist() == [1, 0, 0]
    assert dataset_a.loc[0, "review_status"] == "reviewed by expert panel"
    assert set(dataset_b["variant_id"]) == set(dataset_a["variant_id"])
    assert qc["source_rows"] == 12
    assert qc["excluded_variant_type"] == 1
    assert qc["excluded_noncanonical_chromosome"] == 1
    assert qc["conflicting_variants"] == 1
    assert qc["duplicate_rows_removed"] == 1
    assert qc["dataset_a_rows"] == 3
    assert metadata["assembly"] == "GRCh38"
    assert len(metadata["sha256"]) == 64


def test_prepare_clinvar_dataset_rejects_missing_schema(tmp_path: Path) -> None:
    source = tmp_path / "invalid.tsv"
    source.write_text("#AlleleID\tType\n1\tSNV\n")

    with pytest.raises(ClinVarSchemaError, match="missing required"):
        prepare_clinvar_dataset(source, tmp_path / "output")


def test_prepare_clinvar_dataset_rejects_invalid_chunk_size(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="positive"):
        prepare_clinvar_dataset(FIXTURE, tmp_path, chunk_size=0)
