"""VariantRank command-line interface."""

import logging
from pathlib import Path
from typing import Annotated

import typer

from variantrank import __version__
from variantrank.annotation import (
    DEFAULT_CACHE_VERSION,
    DEFAULT_VEP_IMAGE,
    LocalVEPConfig,
    LocalVEPError,
    VEPClient,
    VEPRequestError,
    annotate_vcf,
    convert_vep_output,
    export_vep_input,
    format_command,
    run_local_vep,
)
from variantrank.data import (
    ClinVarSchemaError,
    VCFFormatError,
    prepare_clinvar_dataset,
    validate_vcf,
)
from variantrank.data.clinvar import DEFAULT_CLINVAR_MD5_URL, DEFAULT_CLINVAR_URL
from variantrank.data.download import ChecksumError, download_file, fetch_published_md5
from variantrank.features import FeatureDatasetError, build_feature_dataset
from variantrank.inference import InferenceError, predict_annotated_vcf
from variantrank.models import CatBoostConfig, run_baseline_experiment, run_calibration_experiment

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


@app.command("export-vep-input")
def export_vep_input_command(
    dataset: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True, help="Curated Parquet dataset."),
    ] = Path("data/processed/clinvar.parquet"),
    output_path: Annotated[
        Path,
        typer.Option(help="Destination VCF or VCF.GZ file."),
    ] = Path("data/interim/clinvar.vep.vcf.gz"),
    batch_size: Annotated[
        int,
        typer.Option(min=1, help="Parquet rows converted per streaming batch."),
    ] = 100_000,
    force: Annotated[bool, typer.Option(help="Replace a matching cached export.")] = False,
) -> None:
    """Stream a curated training dataset into VEP-compatible VCF."""
    try:
        result = export_vep_input(
            dataset,
            output_path,
            batch_size=batch_size,
            force=force,
        )
    except (OSError, ValueError) as error:
        logger.error("VEP input export failed: %s", error)
        raise typer.Exit(code=2) from error
    status = "already current" if result.cached else "written"
    typer.echo(f"VEP input {status}: {result.output} ({result.rows:,} variants)")
    typer.echo(f"Manifest: {result.manifest}")


@app.command("annotate-local")
def annotate_local_command(
    input_path: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True, help="GRCh38 VCF or VCF.GZ."),
    ],
    output_path: Annotated[
        Path,
        typer.Option(help="Compact allowlisted VEP tabular output file."),
    ] = Path("data/annotated/vep.tsv"),
    cache_dir: Annotated[
        Path,
        typer.Option(help="Host directory containing the Ensembl VEP cache."),
    ] = Path("data/external/vep"),
    image: Annotated[
        str, typer.Option(help="Pinned Ensembl VEP Docker image.")
    ] = DEFAULT_VEP_IMAGE,
    cache_version: Annotated[
        int,
        typer.Option(min=1, help="Ensembl cache release matching the VEP image."),
    ] = DEFAULT_CACHE_VERSION,
    forks: Annotated[int, typer.Option(min=1, help="Parallel VEP worker processes.")] = 4,
    fasta: Annotated[
        Path | None,
        typer.Option(
            exists=True, dir_okay=False, readable=True, help="Optional indexed GRCh38 FASTA."
        ),
    ] = None,
    force: Annotated[bool, typer.Option(help="Ignore a matching annotation manifest.")] = False,
    dry_run: Annotated[
        bool, typer.Option(help="Print the Docker command without executing it.")
    ] = False,
) -> None:
    """Run pinned Ensembl VEP offline with cache-aware provenance."""
    config = LocalVEPConfig(
        cache_dir=cache_dir,
        image=image,
        cache_version=cache_version,
        forks=forks,
        fasta=fasta,
    )
    try:
        result = run_local_vep(
            input_path,
            output_path,
            config,
            force=force,
            dry_run=dry_run,
        )
    except (OSError, ValueError, LocalVEPError) as error:
        logger.error("Local VEP annotation failed: %s", error)
        raise typer.Exit(code=2) from error

    if dry_run:
        typer.echo(format_command(result.command))
    elif result.cached:
        typer.echo(f"Annotations already current: {result.output}")
    else:
        typer.echo(f"Annotations: {result.output}")
        typer.echo(f"Manifest: {result.manifest}")


@app.command("parse-vep-output")
def parse_vep_output_command(
    input_path: Annotated[
        Path,
        typer.Argument(
            exists=True, dir_okay=False, readable=True, help="VEP TSV or JSON Lines file."
        ),
    ],
    output_path: Annotated[
        Path,
        typer.Option(help="Typed annotation Parquet output."),
    ] = Path("data/annotated/clinvar.vep.parquet"),
    batch_size: Annotated[
        int,
        typer.Option(min=1, help="Annotations converted per Parquet row group."),
    ] = 50_000,
    force: Annotated[bool, typer.Option(help="Replace a matching cached conversion.")] = False,
) -> None:
    """Convert local VEP TSV or JSON Lines into the stable annotation contract."""
    try:
        result = convert_vep_output(
            input_path,
            output_path,
            batch_size=batch_size,
            force=force,
        )
    except (OSError, ValueError, VEPRequestError) as error:
        logger.error("VEP output conversion failed: %s", error)
        raise typer.Exit(code=2) from error
    status = "already current" if result.cached else "written"
    typer.echo(f"Annotation dataset {status}: {result.output} ({result.rows:,} variants)")
    typer.echo(f"Manifest: {result.manifest}")


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


@app.command("build-features")
def build_features_command(
    labels: Annotated[
        Path,
        typer.Option(exists=True, dir_okay=False, readable=True, help="Curated label Parquet."),
    ] = Path("data/processed/clinvar.parquet"),
    annotations: Annotated[
        Path,
        typer.Option(
            exists=True,
            dir_okay=False,
            readable=True,
            help="Typed VEP annotation Parquet.",
        ),
    ] = Path("data/annotated/clinvar.vep.parquet"),
    output_path: Annotated[
        Path,
        typer.Option(help="Destination model-ready Parquet dataset."),
    ] = Path("data/features/clinvar.features.parquet"),
    force: Annotated[bool, typer.Option(help="Replace a matching cached feature dataset.")] = False,
) -> None:
    """Build the leakage-safe model-ready feature dataset."""
    try:
        result = build_feature_dataset(labels, annotations, output_path, force=force)
    except (FeatureDatasetError, OSError, ValueError) as error:
        logger.error("Feature dataset build failed: %s", error)
        raise typer.Exit(code=2) from error
    status = "already current" if result.cached else "written"
    typer.echo(f"Feature dataset {status}: {result.output} ({result.rows:,} variants)")
    typer.echo(f"Manifest: {result.manifest}")


@app.command("train")
def train_command(
    dataset: Annotated[
        Path,
        typer.Option(
            exists=True,
            dir_okay=False,
            readable=True,
            help="Curated labels or model-ready feature Parquet dataset.",
        ),
    ] = Path("data/features/clinvar.features.parquet"),
    artifact_dir: Annotated[
        Path,
        typer.Option(help="Root directory for models, metrics, and metadata."),
    ] = Path("artifacts/models/baselines"),
    strategy: Annotated[
        str,
        typer.Option(help="Validation strategy: random, gene, or both."),
    ] = "both",
    feature_set: Annotated[
        str,
        typer.Option(help="Feature contract: basic or annotated."),
    ] = "annotated",
    cohort: Annotated[
        str,
        typer.Option(help="Training cohort: all or high-confidence."),
    ] = "all",
    random_seed: Annotated[int, typer.Option(help="Reproducible random seed.")] = 42,
    max_rows: Annotated[
        int | None,
        typer.Option(min=100, help="Optional stratified development sample."),
    ] = None,
    catboost: Annotated[
        bool,
        typer.Option("--catboost/--no-catboost", help="Include the primary CatBoost candidate."),
    ] = False,
    catboost_iterations: Annotated[
        int,
        typer.Option(min=1, help="Number of CatBoost boosting iterations."),
    ] = 1000,
    catboost_depth: Annotated[
        int,
        typer.Option(min=1, max=16, help="CatBoost tree depth."),
    ] = 7,
    catboost_learning_rate: Annotated[
        float,
        typer.Option(min=0.001, max=1.0, help="CatBoost learning rate."),
    ] = 0.05,
) -> None:
    """Train baseline estimators and the optional CatBoost candidate."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if strategy not in {"random", "gene", "both"}:
        logger.error("Unknown validation strategy %r", strategy)
        raise typer.Exit(code=2)
    if feature_set not in {"basic", "annotated"}:
        logger.error("Unknown feature set %r", feature_set)
        raise typer.Exit(code=2)
    if cohort not in {"all", "high-confidence"}:
        logger.error("Unknown cohort %r", cohort)
        raise typer.Exit(code=2)
    strategies = ["random", "gene"] if strategy == "both" else [strategy]

    try:
        for selected_strategy in strategies:
            logger.info("Training %s baselines on %s", selected_strategy, dataset)
            result = run_baseline_experiment(
                dataset,
                artifact_dir,
                strategy=selected_strategy,  # type: ignore[arg-type]
                feature_set=feature_set,  # type: ignore[arg-type]
                high_confidence_only=cohort == "high-confidence",
                include_catboost=catboost,
                catboost_config=CatBoostConfig(
                    iterations=catboost_iterations,
                    depth=catboost_depth,
                    learning_rate=catboost_learning_rate,
                ),
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


@app.command("predict")
def predict_command(
    input_path: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True, help="Normalized GRCh38 VCF."),
    ],
    annotations: Annotated[
        Path,
        typer.Option(
            exists=True,
            dir_okay=False,
            readable=True,
            help="Typed VEP annotation Parquet matching the input VCF.",
        ),
    ],
    model: Annotated[
        Path,
        typer.Option(
            exists=True,
            dir_okay=False,
            readable=True,
            help="Persisted fitted or calibrated pipeline.",
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(help="Ranked .csv or .json destination."),
    ] = Path("results/variants.csv"),
    threshold: Annotated[
        float,
        typer.Option(min=0.0, max=1.0, help="Pathogenic prediction threshold."),
    ] = 0.5,
) -> None:
    """Score and rank an annotated VCF with a persisted model pipeline."""
    try:
        result = predict_annotated_vcf(
            input_path,
            annotations,
            model,
            output,
            threshold=threshold,
        )
    except (InferenceError, OSError, ValueError, VCFFormatError) as error:
        logger.error("Variant inference failed: %s", error)
        raise typer.Exit(code=2) from error
    typer.echo(f"Ranked {result.rows:,} variants: {result.output}")


@app.command("calibrate")
def calibrate_command(
    dataset: Annotated[
        Path,
        typer.Option(
            exists=True,
            dir_okay=False,
            readable=True,
            help="Model-ready feature Parquet dataset.",
        ),
    ] = Path("data/features/clinvar.features.parquet"),
    baseline_artifact_dir: Annotated[
        Path,
        typer.Option(
            exists=True,
            file_okay=False,
            readable=True,
            help="Exact training run directory containing the persisted model.",
        ),
    ] = Path("artifacts/models/baselines/clinvar.features/all/annotated_vep_v1/gene"),
    strategy: Annotated[
        str,
        typer.Option(help="Validation strategy used for baseline training: random or gene."),
    ] = "gene",
    cohort: Annotated[
        str,
        typer.Option(help="Training cohort: all or high-confidence."),
    ] = "all",
    model_name: Annotated[
        str,
        typer.Option(help="Persisted model to calibrate: random_forest or catboost."),
    ] = "random_forest",
    random_seed: Annotated[int, typer.Option(help="Baseline split random seed.")] = 42,
    minimum_recall: Annotated[
        float,
        typer.Option(min=0.01, max=1.0, help="Recall-constrained operating point."),
    ] = 0.90,
    minimum_precision: Annotated[
        float,
        typer.Option(min=0.01, max=1.0, help="Precision-constrained operating point."),
    ] = 0.90,
) -> None:
    """Compare raw, Platt-scaled, and isotonic model probabilities."""
    if strategy not in {"random", "gene"}:
        logger.error("Unknown validation strategy %r", strategy)
        raise typer.Exit(code=2)
    if cohort not in {"all", "high-confidence"}:
        logger.error("Unknown cohort %r", cohort)
        raise typer.Exit(code=2)
    if model_name not in {"random_forest", "catboost"}:
        logger.error("Unknown calibration model %r", model_name)
        raise typer.Exit(code=2)
    try:
        result = run_calibration_experiment(
            dataset,
            baseline_artifact_dir,
            strategy=strategy,  # type: ignore[arg-type]
            high_confidence_only=cohort == "high-confidence",
            model_name=model_name,
            random_seed=random_seed,
            minimum_recall=minimum_recall,
            minimum_precision=minimum_precision,
        )
    except (OSError, ValueError) as error:
        logger.error("Probability calibration failed: %s", error)
        raise typer.Exit(code=2) from error

    typer.echo("\nHeld-out test calibration metrics")
    for method, metrics in result.metrics.items():
        typer.echo(
            f"{method:>10}: ROC-AUC={metrics['roc_auc']:.4f} "
            f"PR-AUC={metrics['pr_auc']:.4f} Brier={metrics['brier_score']:.5f}"
        )
    typer.echo(f"Artifacts: {result.artifact_dir}")


if __name__ == "__main__":  # pragma: no cover
    app()
