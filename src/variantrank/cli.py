"""VariantRank command-line interface."""

import logging
from pathlib import Path
from typing import Annotated

import typer

from variantrank import __version__
from variantrank.annotation import VEPClient, VEPRequestError, annotate_vcf
from variantrank.data import (
    ClinVarSchemaError,
    VCFFormatError,
    prepare_clinvar_dataset,
    validate_vcf,
)
from variantrank.data.clinvar import DEFAULT_CLINVAR_MD5_URL, DEFAULT_CLINVAR_URL
from variantrank.data.download import ChecksumError, download_file, fetch_published_md5
from variantrank.models import run_baseline_experiment

logger = logging.getLogger(__name__)

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


@app.command("annotate-vcf")
def annotate_vcf_command(
    input_path: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True, help="GRCh38 VCF file."),
    ],
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory for annotation Parquet and provenance metadata."),
    ] = Path("data/annotated"),
    batch_size: Annotated[
        int,
        typer.Option(min=1, max=200, help="Variants per Ensembl REST request."),
    ] = 200,
    server: Annotated[
        str,
        typer.Option(help="Ensembl REST server URL."),
    ] = "https://rest.ensembl.org",
) -> None:
    """Annotate a small VCF through the Ensembl VEP REST service."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        annotations, metadata = annotate_vcf(
            input_path,
            output_dir,
            client=VEPClient(server=server, batch_size=batch_size),
        )
    except (OSError, ValueError, VEPRequestError, VCFFormatError) as error:
        logger.error("VEP annotation failed: %s", error)
        raise typer.Exit(code=2) from error

    typer.echo(f"Annotations: {annotations}")
    typer.echo(f"Metadata: {metadata}")


@app.command("prepare-data")
def prepare_data_command(
    source: Annotated[
        Path | None,
        typer.Option(
            "--source",
            dir_okay=False,
            readable=True,
            help="Local ClinVar variant_summary file. Downloads the official release when omitted.",
        ),
    ] = None,
    raw_dir: Annotated[
        Path,
        typer.Option(help="Directory for downloaded source data."),
    ] = Path("data/raw"),
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory for curated Parquet datasets and audit metadata."),
    ] = Path("data/processed"),
    assembly: Annotated[str, typer.Option(help="Genome assembly to retain.")] = "GRCh38",
    chunk_size: Annotated[
        int,
        typer.Option(min=1, help="Number of source rows processed per chunk."),
    ] = 100_000,
    force_download: Annotated[
        bool,
        typer.Option("--force-download", help="Replace an existing raw ClinVar file."),
    ] = False,
) -> None:
    """Download, curate, deduplicate, and version the ClinVar training labels."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    published_md5: str | None = None
    source_url: str | None = None

    try:
        if source is None:
            published_md5 = fetch_published_md5(DEFAULT_CLINVAR_MD5_URL)
            source_path = raw_dir / "variant_summary.txt.gz"
            logger.info("Preparing ClinVar source at %s", source_path)
            download = download_file(
                DEFAULT_CLINVAR_URL,
                source_path,
                expected_md5=published_md5,
                force=force_download,
            )
            source_url = download.url
            logger.info(
                "ClinVar source verified: %s bytes, sha256=%s",
                download.bytes,
                download.sha256,
            )
        else:
            source_path = source
            logger.info("Using local ClinVar source %s", source_path)

        result = prepare_clinvar_dataset(
            source_path,
            output_dir,
            assembly=assembly,
            chunk_size=chunk_size,
            source_url=source_url,
            published_md5=published_md5,
        )
    except (ChecksumError, ClinVarSchemaError, OSError, ValueError) as error:
        logger.error("ClinVar preparation failed: %s", error)
        raise typer.Exit(code=2) from error

    qc = result.qc
    typer.echo(
        f"Dataset A: {qc.dataset_a_rows:,} variants "
        f"({qc.dataset_a_pathogenic:,} pathogenic, {qc.dataset_a_benign:,} benign)"
    )
    typer.echo(
        f"Dataset B: {qc.dataset_b_rows:,} high-confidence variants "
        f"({qc.dataset_b_pathogenic:,} pathogenic, {qc.dataset_b_benign:,} benign)"
    )
    typer.echo(f"Data: {result.dataset_a}")
    typer.echo(f"QC: {result.qc_report}")


@app.command("train")
def train_command(
    dataset: Annotated[
        Path,
        typer.Option(
            exists=True,
            dir_okay=False,
            readable=True,
            help="Curated ClinVar Parquet dataset.",
        ),
    ] = Path("data/processed/clinvar.parquet"),
    artifact_dir: Annotated[
        Path,
        typer.Option(help="Root directory for models, metrics, and metadata."),
    ] = Path("artifacts/models/baselines"),
    strategy: Annotated[
        str,
        typer.Option(help="Validation strategy: random, gene, or both."),
    ] = "both",
    random_seed: Annotated[int, typer.Option(help="Reproducible random seed.")] = 42,
    max_rows: Annotated[
        int | None,
        typer.Option(min=100, help="Optional stratified development sample."),
    ] = None,
) -> None:
    """Train Dummy and Logistic Regression baselines."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if strategy not in {"random", "gene", "both"}:
        logger.error("Unknown validation strategy %r", strategy)
        raise typer.Exit(code=2)
    strategies = ["random", "gene"] if strategy == "both" else [strategy]

    try:
        for selected_strategy in strategies:
            logger.info("Training %s baselines on %s", selected_strategy, dataset)
            result = run_baseline_experiment(
                dataset,
                artifact_dir,
                strategy=selected_strategy,  # type: ignore[arg-type]
                random_seed=random_seed,
                max_rows=max_rows,
            )
            typer.echo(f"\n{selected_strategy} test metrics")
            for model_name, partitions in result.metrics.items():
                metrics = partitions["test"]
                typer.echo(
                    f"{model_name:>20}: ROC-AUC={metrics['roc_auc']:.4f} "
                    f"PR-AUC={metrics['pr_auc']:.4f} MCC={metrics['mcc']:.4f}"
                )
            typer.echo(f"Artifacts: {result.artifact_dir}")
    except (OSError, ValueError) as error:
        logger.error("Baseline training failed: %s", error)
        raise typer.Exit(code=2) from error


if __name__ == "__main__":  # pragma: no cover
    app()
