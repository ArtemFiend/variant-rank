"""Feature engineering contracts."""

from variantrank.features.annotation import (
    ANNOTATION_CATEGORICAL_FEATURES,
    ANNOTATION_NUMERIC_FEATURES,
    build_annotation_features,
)
from variantrank.features.variant import (
    BASIC_CATEGORICAL_FEATURES,
    BASIC_NUMERIC_FEATURES,
    build_basic_features,
)

__all__ = [
    "ANNOTATION_CATEGORICAL_FEATURES",
    "ANNOTATION_NUMERIC_FEATURES",
    "BASIC_CATEGORICAL_FEATURES",
    "BASIC_NUMERIC_FEATURES",
    "build_annotation_features",
    "build_basic_features",
]
