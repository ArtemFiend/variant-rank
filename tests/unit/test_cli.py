from pathlib import Path

from typer.testing import CliRunner

from variantrank.cli import app

FIXTURE = Path(__file__).parents[1] / "fixtures" / "example.vcf"
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
