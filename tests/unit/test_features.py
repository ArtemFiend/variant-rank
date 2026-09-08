import pandas as pd
import pytest

from variantrank.features.variant import FeatureSchemaError, build_basic_features


def test_build_basic_features_distinguishes_substitutions_and_indels() -> None:
    variants = pd.DataFrame(
        {
            "chrom": ["1", "2", "3"],
            "ref": ["A", "C", "AT"],
            "alt": ["G", "A", "A"],
            "variant_type": ["single nucleotide variant", "single nucleotide variant", "Deletion"],
        }
    )

    features = build_basic_features(variants)

    assert features["substitution"].tolist() == ["A>G", "C>A", "indel"]
    assert features["is_transition"].tolist() == [1, 0, 0]
    assert features["is_transversion"].tolist() == [0, 1, 0]
    assert features["is_deletion"].tolist() == [0, 0, 1]
    assert features["length_delta"].tolist() == [0, 0, -1]


def test_build_basic_features_requires_normalized_alleles() -> None:
    with pytest.raises(FeatureSchemaError, match="alt"):
        build_basic_features(pd.DataFrame({"chrom": ["1"], "ref": ["A"], "variant_type": ["SNV"]}))
