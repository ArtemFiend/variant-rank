"""Ranked inference for annotated variant inputs."""

from variantrank.inference.predictor import (
    InferenceError,
    PredictionResult,
    predict_annotated_vcf,
)

__all__ = ["InferenceError", "PredictionResult", "predict_annotated_vcf"]
