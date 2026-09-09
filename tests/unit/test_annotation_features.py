import pandas as pd
import pytest

from variantrank.features import build_annotation_features


def test_build_annotation_features_creates_biological_indicators() -> None:
    annotations = pd.DataFrame(
        {
            "consequence": ["missense_variant&splice_region_variant"],
            "impact": ["MODERATE"],
            "biotype": ["protein_coding"],
            "protein_position": [273],
            "allele_frequency": [0.00001],
            "population_max_af": [0.00003],
            "afr_af": [0.00003],
            "amr_af": [None],
            "eas_af": [None],
            "nfe_af": [0.00001],
            "sas_af": [None],
            "rare_variant_flag": [True],
            "canonical": [True],
            "mane_select": ["ENST00000269305.9"],
        }
    )

    features = build_annotation_features(annotations)

    assert features.loc[0, "is_missense"] == 1
    assert features.loc[0, "is_splice"] == 1
    assert features.loc[0, "is_synonymous"] == 0
    assert features.loc[0, "rare_variant_flag"] == 1
    assert features.loc[0, "mane_select_flag"] == 1


def test_build_annotation_features_validates_schema() -> None:
    with pytest.raises(ValueError, match="missing annotation columns"):
        build_annotation_features(pd.DataFrame({"consequence": ["intron_variant"]}))
