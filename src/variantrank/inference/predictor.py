"""Model loading, feature construction, scoring, and variant ranking."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from variantrank.data import read_vcf
from variantrank.features import build_model_features, normalize_model_features


class InferenceError(ValueError):
    """Raised when inference inputs do not satisfy the model contract."""


@dataclass(frozen=True, slots=True)
class PredictionResult:
    """Ranked predictions and their persisted output path."""

    output: Path
    rows: int
    predictions: pd.DataFrame


def predict_annotated_vcf(
    vcf: Path,
    annotations: Path,
    model_path: Path,
    output: Path,
    *,
    threshold: float = 0.5,
) -> PredictionResult:
    """Score and rank a VCF using its matching typed VEP annotation dataset."""
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0 and 1")
    for path in (vcf, annotations, model_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    variant_records = list(read_vcf(vcf))
    if not variant_records:
        raise InferenceError("VCF contains no variants")
    variants = pd.DataFrame(
        {
            "variant_id": [variant.key for variant in variant_records],
            "chrom": [variant.chrom for variant in variant_records],
            "pos": [variant.pos for variant in variant_records],
            "ref": [variant.ref for variant in variant_records],
            "alt": [variant.alt for variant in variant_records],
            "variant_type": [
                _variant_type(variant.ref, variant.alt) for variant in variant_records
            ],
            "input_order": range(len(variant_records)),
        }
    )
    annotation_frame = pd.read_parquet(annotations)
    _validate_annotation_keys(variants["variant_id"], annotation_frame)
    merged = variants.merge(
        annotation_frame,
        how="left",
        left_on="variant_id",
        right_on="variant",
        validate="one_to_one",
        sort=False,
    )
    features = normalize_model_features(build_model_features(merged))
    model: Any = joblib.load(model_path)
    probability = np.asarray(model.predict_proba(features))[:, 1]

    predictions = merged.loc[
        :, ["variant_id", "chrom", "pos", "ref", "alt", "gene", "consequence", "input_order"]
    ].copy()
    predictions["score"] = probability
    predictions["prediction"] = np.where(probability >= threshold, "pathogenic", "benign")
    predictions = predictions.sort_values(
        ["score", "input_order"], ascending=[False, True], kind="stable"
    ).reset_index(drop=True)
    predictions.insert(0, "rank", np.arange(1, len(predictions) + 1))
    predictions = predictions.drop(columns="input_order")
    _write_predictions(predictions, output)
    return PredictionResult(output=output, rows=len(predictions), predictions=predictions)


def _validate_annotation_keys(variant_keys: pd.Series, annotations: pd.DataFrame) -> None:
    if "variant" not in annotations:
        raise InferenceError("annotation dataset is missing column: variant")
    if annotations["variant"].duplicated().any():
        raise InferenceError("annotation variant keys must be unique")
    expected = pd.Index(variant_keys)
    observed = pd.Index(annotations["variant"])
    missing = expected.difference(observed)
    unexpected = observed.difference(expected)
    if len(missing) or len(unexpected):
        raise InferenceError(
            "VCF and annotation keys differ: "
            f"{len(missing)} missing annotations, {len(unexpected)} unexpected annotations"
        )


def _variant_type(ref: str, alt: str) -> str:
    if len(ref) == len(alt) == 1:
        return "single nucleotide variant"
    if len(ref) > len(alt):
        return "deletion"
    if len(ref) < len(alt):
        return "insertion"
    return "multiple nucleotide variant"


def _write_predictions(predictions: pd.DataFrame, output: Path) -> None:
    if output.suffix not in {".csv", ".json"}:
        raise InferenceError("prediction output must use .csv or .json")
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + ".partial")
    if output.suffix == ".csv":
        predictions.to_csv(partial, index=False)
    else:
        records = predictions.where(predictions.notna(), None).to_dict(orient="records")
        partial.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    partial.replace(output)
