from pathlib import Path

from typer.testing import CliRunner

from variantrank.cli import app

FIXTURE = Path(__file__).parents[1] / "fixtures" / "example.vcf"
runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "variantrank 0.1.0" in result.stdout


def test_validate_vcf_command() -> None:
    result = runner.invoke(app, ["validate-vcf", str(FIXTURE)])

    assert result.exit_code == 0
    assert "2 records, 3 alleles" in result.stdout
