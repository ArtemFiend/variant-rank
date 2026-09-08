"""VariantRank command-line interface."""

from pathlib import Path
from typing import Annotated

import typer

from variantrank import __version__
from variantrank.data import VCFFormatError, validate_vcf

app = typer.Typer(
    name="variantrank",
    help="Research-grade genetic variant prioritization.",
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"variantrank {__version__}")
        raise typer.Exit


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=version_callback, is_eager=True, help="Show version."),
    ] = None,
) -> None:
    """VariantRank command group."""


@app.command("validate-vcf")
def validate_vcf_command(
    input_path: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True, help="VCF or VCF.GZ file."),
    ],
) -> None:
    """Validate and summarize a VCF without running annotation or inference."""
    try:
        summary = validate_vcf(input_path)
    except VCFFormatError as error:
        typer.echo(f"Invalid VCF: {error}", err=True)
        raise typer.Exit(code=2) from error

    chromosomes = ", ".join(summary.chromosomes) or "none"
    typer.echo(f"Valid VCF: {summary.records} records, {summary.alleles} alleles")
    typer.echo(f"Chromosomes: {chromosomes}")


if __name__ == "__main__":  # pragma: no cover
    app()
