"""Model-ready features derived from the stable VEP annotation contract."""

import pandas as pd

CONSEQUENCE_FLAGS = {
    "is_missense": "missense_variant",
    "is_synonymous": "synonymous_variant",
    "is_stop_gained": "stop_gained",
    "is_frameshift": "frameshift_variant",
    "is_splice": "splice_",
    "is_start_lost": "start_lost",
    "is_stop_lost": "stop_lost",
}
ANNOTATION_NUMERIC_FEATURES = [
    "protein_position",
    "allele_frequency",
    "population_max_af",
    "afr_af",
    "amr_af",
    "eas_af",
    "nfe_af",
    "sas_af",
    "rare_variant_flag",
    "canonical",
    "mane_select_flag",
    *CONSEQUENCE_FLAGS,
]
ANNOTATION_CATEGORICAL_FEATURES = ["consequence", "impact", "biotype"]
REQUIRED_ANNOTATION_COLUMNS = frozenset(
    {
        "consequence",
        "impact",
        "biotype",
        "protein_position",
        "allele_frequency",
        "population_max_af",
        "afr_af",
        "amr_af",
        "eas_af",
        "nfe_af",
        "sas_af",
        "rare_variant_flag",
        "canonical",
        "mane_select",
    }
)


def build_annotation_features(annotations: pd.DataFrame) -> pd.DataFrame:
    """Build leakage-safe functional and population model features."""
    missing = REQUIRED_ANNOTATION_COLUMNS - set(annotations.columns)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"missing annotation columns: {names}")

    features = annotations[
        [
            "protein_position",
            "allele_frequency",
            "population_max_af",
            "afr_af",
            "amr_af",
            "eas_af",
            "nfe_af",
            "sas_af",
        ]
    ].apply(pd.to_numeric, errors="coerce")
    features["rare_variant_flag"] = annotations["rare_variant_flag"].astype("Int8")
    features["canonical"] = annotations["canonical"].astype("int8")
    features["mane_select_flag"] = annotations["mane_select"].notna().astype("int8")

    consequence = annotations["consequence"].fillna("").astype("string")
    for feature, term in CONSEQUENCE_FLAGS.items():
        features[feature] = consequence.str.contains(term, regex=False).astype("int8")
    for name in ANNOTATION_CATEGORICAL_FEATURES:
        features[name] = annotations[name].astype("string")
    ordered = [*ANNOTATION_NUMERIC_FEATURES, *ANNOTATION_CATEGORICAL_FEATURES]
    return pd.DataFrame(features, columns=ordered, index=annotations.index)
