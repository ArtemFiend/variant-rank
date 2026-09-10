import json
from pathlib import Path

import pandas as pd
import pytest

import variantrank.api.service
from variantrank.api.service import PredictionService, service_from_environment
from variantrank.inference import PredictionResult


def test_prediction_service_reads_calibration_and_training_metadata(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    calibration_dir = run_dir / "calibration-catboost"
    calibration_dir.mkdir(parents=True)
    model = calibration_dir / "catboost_isotonic.joblib"
    model.touch()
    source_metadata = run_dir / "metadata.json"
    source_metadata.write_text(
        json.dumps(
            {
                "feature_set": "annotated_vep_v1",
                "created_at": "2026-09-10T12:00:00+00:00",
                "numeric_features": ["af", "length"],
                "categorical_features": ["impact"],
            }
        )
    )
    (calibration_dir / "metadata.json").write_text(
        json.dumps(
            {
                "model_name": "catboost",
                "source_metadata": str(source_metadata),
                "feature_set": "annotated_vep_v1",
            }
        )
    )

    service = PredictionService(model, threshold=0.47)

    assert service.descriptor.model == "catboost"
    assert service.descriptor.features == 3
    assert service.descriptor.training_date == "2026-09-10T12:00:00+00:00"


def test_service_from_environment_builds_configured_service(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    model = tmp_path / "model.joblib"
    model.touch()
    monkeypatch.setenv("VARIANTRANK_MODEL_PATH", str(model))
    monkeypatch.setenv("VARIANTRANK_THRESHOLD", "0.61")
    monkeypatch.setenv("VARIANTRANK_VEP_SERVER", "https://vep.example.test")

    service = service_from_environment()

    assert service is not None
    assert service.threshold == pytest.approx(0.61)
    assert service.vep_client.server == "https://vep.example.test"


def test_prediction_service_coordinates_annotation_and_inference(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    model = tmp_path / "model.joblib"
    vcf = tmp_path / "variants.vcf"
    model.touch()
    vcf.touch()
    annotations = tmp_path / "variants.vep.parquet"
    expected = PredictionResult(tmp_path / "predictions.json", 1, pd.DataFrame())

    def fake_annotate(*_args, **_kwargs):
        return annotations, tmp_path / "metadata.json"

    def fake_predict(*_args, **_kwargs):
        return expected

    monkeypatch.setattr(variantrank.api.service, "annotate_vcf", fake_annotate)
    monkeypatch.setattr(variantrank.api.service, "predict_annotated_vcf", fake_predict)
    service = PredictionService(model, threshold=0.5)

    assert service.predict(vcf, tmp_path) is expected


def test_prediction_service_validates_configuration(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        PredictionService(tmp_path / "missing.joblib", threshold=0.5)

    model = tmp_path / "model.joblib"
    model.touch()
    with pytest.raises(ValueError, match="between 0 and 1"):
        PredictionService(model, threshold=2.0)
