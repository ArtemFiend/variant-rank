"""Configured inference service used by CLI-independent API routes."""

import json
import os
from dataclasses import dataclass
from pathlib import Path

from variantrank.annotation import VEPClient, annotate_vcf
from variantrank.inference import PredictionResult, predict_annotated_vcf


@dataclass(frozen=True, slots=True)
class ModelDescriptor:
    """Public, non-sensitive metadata for a loaded inference artifact."""

    model: str
    feature_set: str | None
    features: int | None
    training_date: str | None
    threshold: float


class PredictionService:
    """Coordinate VEP annotation and persisted-model inference."""

    def __init__(
        self,
        model_path: Path,
        *,
        threshold: float,
        vep_client: VEPClient | None = None,
    ) -> None:
        if not model_path.is_file():
            raise FileNotFoundError(model_path)
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")
        self.model_path = model_path
        self.threshold = threshold
        self.vep_client = vep_client or VEPClient()
        self.descriptor = _model_descriptor(model_path, threshold)

    def predict(self, vcf: Path, work_dir: Path) -> PredictionResult:
        """Annotate, score, and rank one uploaded VCF."""
        annotations, _ = annotate_vcf(vcf, work_dir, client=self.vep_client)
        return predict_annotated_vcf(
            vcf,
            annotations,
            self.model_path,
            work_dir / "predictions.json",
            threshold=self.threshold,
        )


def service_from_environment() -> PredictionService | None:
    """Construct an API service when VARIANTRANK_MODEL_PATH is configured."""
    configured_path = os.getenv("VARIANTRANK_MODEL_PATH")
    if not configured_path:
        return None
    threshold = float(os.getenv("VARIANTRANK_THRESHOLD", "0.5"))
    server = os.getenv("VARIANTRANK_VEP_SERVER", "https://rest.ensembl.org")
    return PredictionService(
        Path(configured_path), threshold=threshold, vep_client=VEPClient(server=server)
    )


def _model_descriptor(model_path: Path, threshold: float) -> ModelDescriptor:
    metadata_path = model_path.parent / "metadata.json"
    metadata: dict[str, object] = {}
    if metadata_path.is_file():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    model = str(metadata.get("model_name") or model_path.stem)
    feature_set = _optional_string(metadata.get("feature_set"))
    training_date = _optional_string(metadata.get("created_at"))
    features: int | None = None

    source_metadata = metadata.get("source_metadata")
    if isinstance(source_metadata, str):
        source_path = Path(source_metadata)
        if source_path.is_file():
            source = json.loads(source_path.read_text(encoding="utf-8"))
            numeric = source.get("numeric_features", [])
            categorical = source.get("categorical_features", [])
            if isinstance(numeric, list) and isinstance(categorical, list):
                features = len(numeric) + len(categorical)
            feature_set = _optional_string(source.get("feature_set")) or feature_set
            training_date = _optional_string(source.get("created_at")) or training_date
    return ModelDescriptor(model, feature_set, features, training_date, threshold)


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None
