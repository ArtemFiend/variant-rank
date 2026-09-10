"""Construction of the leakage-safe, model-ready feature dataset."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from variantrank.data.download import file_digest
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

FEATURE_DATASET_VERSION = 1
METADATA_COLUMNS = ["variant_id", "gene", "target", "high_confidence"]
LABEL_COLUMNS = [
    *METADATA_COLUMNS,
    "chrom",
    "ref",
    "alt",
    "variant_type",
]
ANNOTATION_COLUMNS = [
    "variant",
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
]
MODEL_NUMERIC_FEATURES = [*BASIC_NUMERIC_FEATURES, *ANNOTATION_NUMERIC_FEATURES]
MODEL_CATEGORICAL_FEATURES = [*BASIC_CATEGORICAL_FEATURES, *ANNOTATION_CATEGORICAL_FEATURES]
MODEL_FEATURES = [*MODEL_NUMERIC_FEATURES, *MODEL_CATEGORICAL_FEATURES]


class FeatureDatasetError(ValueError):
    """Raised when labels and annotations cannot form a safe feature dataset."""


@dataclass(frozen=True, slots=True)
class FeatureDatasetResult:
    """Paths and row count produced by a feature-dataset build."""

    output: Path
    manifest: Path
    rows: int
    cached: bool


def build_feature_dataset(
    labels: Path,
    annotations: Path,
    output: Path,
    *,
    force: bool = False,
) -> FeatureDatasetResult:
    """Join curated labels to VEP annotations and persist model-ready features."""
    if not labels.is_file():
        raise FileNotFoundError(labels)
    if not annotations.is_file():
        raise FileNotFoundError(annotations)

    labels_checksum = file_digest(labels)
    annotations_checksum = file_digest(annotations)
    manifest = output.with_suffix(output.suffix + ".manifest.json")
    cached_rows = _cached_rows(
        output,
        manifest,
        labels_checksum=labels_checksum,
        annotations_checksum=annotations_checksum,
    )
    if not force and cached_rows is not None:
        return FeatureDatasetResult(output, manifest, cached_rows, cached=True)

    label_frame = _read_labels(labels)
    annotation_frame = _read_annotations(annotations)
    _validate_keys(label_frame, annotation_frame)

    merged = label_frame.merge(
        annotation_frame,
        how="inner",
        left_on="variant_id",
        right_on="variant",
        validate="one_to_one",
        sort=False,
    )
    model_features = build_model_features(merged)
    feature_frame = pd.concat(
        [merged.loc[:, METADATA_COLUMNS].reset_index(drop=True), model_features],
        axis=1,
    ).loc[:, [*METADATA_COLUMNS, *MODEL_FEATURES]]

    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + ".partial")
    partial.unlink(missing_ok=True)
    try:
        feature_frame.to_parquet(partial, index=False, compression="zstd")
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    partial.replace(output)

    payload = {
        "annotations": str(annotations),
        "annotations_sha256": annotations_checksum,
        "categorical_features": MODEL_CATEGORICAL_FEATURES,
        "created_at": datetime.now(UTC).isoformat(),
        "feature_dataset_version": FEATURE_DATASET_VERSION,
        "labels": str(labels),
        "labels_sha256": labels_checksum,
        "metadata_columns": METADATA_COLUMNS,
        "numeric_features": MODEL_NUMERIC_FEATURES,
        "output": str(output),
        "output_sha256": file_digest(output),
        "rows": len(feature_frame),
        "schema": {name: str(dtype) for name, dtype in feature_frame.dtypes.items()},
    }
    manifest.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return FeatureDatasetResult(output, manifest, len(feature_frame), cached=False)


def build_model_features(variants_with_annotations: pd.DataFrame) -> pd.DataFrame:
    """Build the ordered feature contract shared by training and inference."""
    basic = build_basic_features(variants_with_annotations).reset_index(drop=True)
    annotated = build_annotation_features(variants_with_annotations).reset_index(drop=True)
    return pd.concat([basic, annotated], axis=1).loc[:, MODEL_FEATURES]


def normalize_model_features(features: pd.DataFrame) -> pd.DataFrame:
    """Normalize nullable pandas dtypes for persisted scikit-learn pipelines."""
    normalized = features.copy()
    normalized[MODEL_NUMERIC_FEATURES] = normalized[MODEL_NUMERIC_FEATURES].astype("float64")
    for name in MODEL_CATEGORICAL_FEATURES:
        column = normalized[name].astype("object")
        normalized[name] = column.where(column.notna(), None)
    return normalized


def _read_labels(path: Path) -> pd.DataFrame:
    missing = set(LABEL_COLUMNS) - set(pq.ParquetFile(path).schema.names)
    if missing:
        names = ", ".join(sorted(missing))
        raise FeatureDatasetError(f"label dataset is missing columns: {names}")
    return pd.read_parquet(path, columns=LABEL_COLUMNS)


def _read_annotations(path: Path) -> pd.DataFrame:
    schema = set(pq.ParquetFile(path).schema.names)
    missing = set(ANNOTATION_COLUMNS) - schema
    if missing:
        names = ", ".join(sorted(missing))
        raise FeatureDatasetError(f"annotation dataset is missing columns: {names}")
    return pd.read_parquet(path, columns=ANNOTATION_COLUMNS)


def _validate_keys(labels: pd.DataFrame, annotations: pd.DataFrame) -> None:
    if labels.empty or annotations.empty:
        raise FeatureDatasetError("labels and annotations must not be empty")
    if labels["variant_id"].duplicated().any():
        raise FeatureDatasetError("label variant keys must be unique")
    if annotations["variant"].duplicated().any():
        raise FeatureDatasetError("annotation variant keys must be unique")

    label_keys = pd.Index(labels["variant_id"])
    annotation_keys = pd.Index(annotations["variant"])
    missing = label_keys.difference(annotation_keys)
    unexpected = annotation_keys.difference(label_keys)
    if len(missing) or len(unexpected):
        raise FeatureDatasetError(
            "label and annotation keys differ: "
            f"{len(missing)} missing annotations, {len(unexpected)} unexpected annotations"
        )


def _cached_rows(
    output: Path,
    manifest: Path,
    *,
    labels_checksum: str,
    annotations_checksum: str,
) -> int | None:
    if not output.is_file() or output.stat().st_size == 0 or not manifest.is_file():
        return None
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        if (
            payload.get("feature_dataset_version") == FEATURE_DATASET_VERSION
            and payload.get("labels_sha256") == labels_checksum
            and payload.get("annotations_sha256") == annotations_checksum
            and payload.get("output_sha256") == file_digest(output)
        ):
            return int(payload["rows"])
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError):
        return None
    return None
