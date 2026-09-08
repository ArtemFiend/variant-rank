"""Leakage-safe features derived directly from a normalized variant."""

import pandas as pd

BASIC_NUMERIC_FEATURES = [
    "ref_length",
    "alt_length",
    "length_delta",
    "absolute_length_delta",
    "is_snv",
    "is_indel",
    "is_insertion",
    "is_deletion",
    "is_transition",
    "is_transversion",
    "ref_gc_fraction",
    "alt_gc_fraction",
]
BASIC_CATEGORICAL_FEATURES = ["chrom", "variant_type", "substitution"]
BASIC_FEATURES = [*BASIC_NUMERIC_FEATURES, *BASIC_CATEGORICAL_FEATURES]
REQUIRED_COLUMNS = frozenset({"chrom", "ref", "alt", "variant_type"})
TRANSITIONS = frozenset({"A>G", "G>A", "C>T", "T>C"})


class FeatureSchemaError(ValueError):
    """Raised when variants cannot satisfy the basic feature contract."""


def build_basic_features(variants: pd.DataFrame) -> pd.DataFrame:
    """Build the annotation-free feature set used by the first baselines."""
    missing = REQUIRED_COLUMNS - set(variants.columns)
    if missing:
        names = ", ".join(sorted(missing))
        raise FeatureSchemaError(f"missing variant columns: {names}")

    ref = variants["ref"].astype("string").str.upper()
    alt = variants["alt"].astype("string").str.upper()
    ref_length = ref.str.len().astype("int32")
    alt_length = alt.str.len().astype("int32")
    is_snv = ref_length.eq(1) & alt_length.eq(1)
    substitution = (ref + ">" + alt).where(is_snv, "indel")
    transition = substitution.isin(TRANSITIONS)

    features = pd.DataFrame(index=variants.index)
    features["ref_length"] = ref_length
    features["alt_length"] = alt_length
    features["length_delta"] = (alt_length - ref_length).astype("int32")
    features["absolute_length_delta"] = features["length_delta"].abs().astype("int32")
    features["is_snv"] = is_snv.astype("int8")
    features["is_indel"] = (~is_snv).astype("int8")
    features["is_insertion"] = alt_length.gt(ref_length).astype("int8")
    features["is_deletion"] = ref_length.gt(alt_length).astype("int8")
    features["is_transition"] = transition.astype("int8")
    features["is_transversion"] = (is_snv & ~transition).astype("int8")
    features["ref_gc_fraction"] = ref.map(_gc_fraction).astype("float32")
    features["alt_gc_fraction"] = alt.map(_gc_fraction).astype("float32")
    features["chrom"] = variants["chrom"].astype("string")
    features["variant_type"] = variants["variant_type"].astype("string").str.lower()
    features["substitution"] = substitution.astype("string")
    return features.loc[:, BASIC_FEATURES]


def _gc_fraction(allele: str) -> float:
    if not allele:
        return 0.0
    return (allele.count("G") + allele.count("C")) / len(allele)
