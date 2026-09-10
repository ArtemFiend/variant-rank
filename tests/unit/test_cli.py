import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from typer.testing import CliRunner

import variantrank.cli
from variantrank.cli import app

FIXTURE = Path(__file__).parents[1] / "fixtures" / "example.vcf"
VEP_FIXTURE = Path(__file__).parents[1] / "fixtures" / "example.vep.vcf"
CLINVAR_FIXTURE = Path(__file__).parents[1] / "fixtures" / "clinvar_variant_summary.tsv"
runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "variantrank 0.1.0" in result.stdout


def test_validate_vcf_command() -> None:
    result = runner.invoke(app, ["validate-vcf", str(FIXTURE)])

    assert result.exit_code == 0
    assert "2 records, 3 alleles" in result.stdout


def test_prepare_data_command_with_local_source(tmp_path: Path) -> None:
    output_dir = tmp_path / "processed"

    result = runner.invoke(
        app,
        [
            "prepare-data",
            "--source",
            str(CLINVAR_FIXTURE),
            "--output-dir",
            str(output_dir),
            "--chunk-size",
            "3",
        ],
    )

    assert result.exit_code == 0
    assert "Dataset A: 3 variants" in result.stdout
    assert "Dataset B: 3 high-confidence variants" in result.stdout
    assert (output_dir / "clinvar.parquet").is_file()
    assert (output_dir / "clinvar_qc.json").is_file()


def test_annotate_vcf_command(monkeypatch, tmp_path: Path) -> None:
    annotations = tmp_path / "example.vep.parquet"
    metadata = tmp_path / "example.vep.metadata.json"

    def fake_annotate(*_args, **_kwargs):
        return annotations, metadata

    monkeypatch.setattr(variantrank.cli, "annotate_vcf", fake_annotate)
    result = runner.invoke(app, ["annotate-vcf", str(FIXTURE), "--output-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert str(annotations) in result.stdout
    assert str(metadata) in result.stdout


def test_annotate_local_dry_run_command(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "annotate-local",
            str(VEP_FIXTURE),
            "--output-path",
            str(tmp_path / "vep.jsonl"),
            "--cache-dir",
            str(tmp_path / "cache"),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert "docker run" in result.stdout
    assert "--offline" in result.stdout


def test_export_vep_input_command(tmp_path: Path) -> None:
    dataset = tmp_path / "variants.parquet"
    output = tmp_path / "variants.vcf.gz"
    pd.DataFrame({"chrom": ["1"], "pos": [100], "ref": ["A"], "alt": ["G"]}).to_parquet(
        dataset, index=False
    )

    result = runner.invoke(
        app,
        ["export-vep-input", str(dataset), "--output-path", str(output)],
    )

    assert result.exit_code == 0
    assert "1 variants" in result.stdout
    assert output.is_file()


def test_parse_vep_output_command(tmp_path: Path) -> None:
    payload = json.loads((FIXTURE.parent / "vep_response.json").read_text())[0]
    source = tmp_path / "vep.jsonl"
    output = tmp_path / "annotations.parquet"
    source.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["parse-vep-output", str(source), "--output-path", str(output)],
    )

    assert result.exit_code == 0
    assert "1 variants" in result.stdout
    assert output.is_file()


def test_build_features_command(monkeypatch, tmp_path: Path) -> None:
    labels = tmp_path / "labels.parquet"
    annotations = tmp_path / "annotations.parquet"
    output = tmp_path / "features.parquet"
    labels.touch()
    annotations.touch()

    def fake_build(*_args, **_kwargs):
        return SimpleNamespace(
            output=output,
            manifest=output.with_suffix(".parquet.manifest.json"),
            rows=2,
            cached=False,
        )

    monkeypatch.setattr(variantrank.cli, "build_feature_dataset", fake_build)
    result = runner.invoke(
        app,
        [
            "build-features",
            "--labels",
            str(labels),
            "--annotations",
            str(annotations),
            "--output-path",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert "2 variants" in result.stdout
