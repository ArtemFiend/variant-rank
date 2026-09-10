"""Reproducible local Ensembl VEP execution through Docker."""

import gzip
import json
import shlex
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from variantrank.data.download import file_digest

DEFAULT_VEP_IMAGE = "ensemblorg/ensembl-vep:release_116.1"
DEFAULT_CACHE_VERSION = 116
LOCAL_VEP_FLAGS = (
    "--pick",
    "--canonical",
    "--mane",
    "--numbers",
    "--protein",
    "--symbol",
    "--biotype",
    "--variant_class",
    "--af",
    "--af_gnomade",
)
VEP_TAB_FIELDS = (
    "Uploaded_variation",
    "Location",
    "Allele",
    "Gene",
    "Feature",
    "Consequence",
    "Protein_position",
    "Amino_acids",
    "Codons",
    "SYMBOL",
    "IMPACT",
    "BIOTYPE",
    "EXON",
    "INTRON",
    "CANONICAL",
    "MANE_SELECT",
    "AF",
    "AFR_AF",
    "AMR_AF",
    "EAS_AF",
    "SAS_AF",
    "gnomADe_AF",
    "gnomADe_AFR_AF",
    "gnomADe_AMR_AF",
    "gnomADe_EAS_AF",
    "gnomADe_NFE_AF",
    "gnomADe_SAS_AF",
)
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


class LocalVEPError(RuntimeError):
    """Raised when a local VEP job cannot be executed or validated."""


@dataclass(frozen=True, slots=True)
class LocalVEPConfig:
    """Versioned options for an offline GRCh38 VEP run."""

    cache_dir: Path
    image: str = DEFAULT_VEP_IMAGE
    cache_version: int = DEFAULT_CACHE_VERSION
    forks: int = 4
    fasta: Path | None = None

    def __post_init__(self) -> None:
        if self.cache_version < 1:
            raise ValueError("cache_version must be positive")
        if self.forks < 1:
            raise ValueError("forks must be positive")


@dataclass(frozen=True, slots=True)
class LocalVEPResult:
    """Outcome of an offline VEP execution."""

    output: Path
    manifest: Path
    command: tuple[str, ...]
    cached: bool
    executed: bool


def run_local_vep(
    source: Path,
    output: Path,
    config: LocalVEPConfig,
    *,
    force: bool = False,
    dry_run: bool = False,
    runner: CommandRunner = subprocess.run,
) -> LocalVEPResult:
    """Run pinned VEP offline and reuse an output with matching provenance."""
    if not source.is_file():
        raise FileNotFoundError(source)
    _validate_biallelic_vcf(source)
    source_checksum = file_digest(source)
    manifest = output.with_suffix(output.suffix + ".manifest.json")
    configuration = _configuration(config)
    if not force and _cache_matches(output, manifest, source_checksum, configuration):
        command = tuple(_docker_command(source, output, config))
        return LocalVEPResult(output, manifest, command, cached=True, executed=False)

    partial = output.with_suffix(output.suffix + ".partial")
    command = tuple(_docker_command(source, partial, config))
    if dry_run:
        return LocalVEPResult(output, manifest, command, cached=False, executed=False)
    if not config.cache_dir.is_dir():
        raise LocalVEPError(f"VEP cache directory does not exist: {config.cache_dir}")
    if config.fasta is not None and not config.fasta.is_file():
        raise LocalVEPError(f"reference FASTA does not exist: {config.fasta}")

    output.parent.mkdir(parents=True, exist_ok=True)
    partial.unlink(missing_ok=True)
    started = perf_counter()
    try:
        process = runner(command, capture_output=True, text=True, check=False)
    except FileNotFoundError as error:
        raise LocalVEPError("Docker executable was not found") from error
    if process.returncode != 0:
        partial.unlink(missing_ok=True)
        detail = process.stderr.strip() or process.stdout.strip() or "no diagnostic output"
        raise LocalVEPError(f"VEP exited with code {process.returncode}: {detail[-2000:]}")
    if not partial.is_file() or partial.stat().st_size == 0:
        raise LocalVEPError("VEP completed without a non-empty output file")

    partial.replace(output)
    payload: dict[str, Any] = {
        "assembly": "GRCh38",
        "command": list(command),
        "configuration": configuration,
        "created_at": datetime.now(UTC).isoformat(),
        "duration_seconds": perf_counter() - started,
        "input": str(source),
        "input_sha256": source_checksum,
        "output": str(output),
        "output_sha256": file_digest(output),
    }
    _write_json(manifest, payload)
    return LocalVEPResult(output, manifest, command, cached=False, executed=True)


def format_command(command: Sequence[str]) -> str:
    """Render an argv sequence for logs and dry-run output."""
    return shlex.join(command)


def _docker_command(source: Path, output: Path, config: LocalVEPConfig) -> list[str]:
    source = source.resolve()
    output = output.resolve()
    cache = config.cache_dir.resolve()
    command = [
        "docker",
        "run",
        "--rm",
        "--volume",
        f"{source.parent}:/input:ro",
        "--volume",
        f"{output.parent}:/output",
        "--volume",
        f"{cache}:/data:ro",
    ]
    fasta_path: str | None = None
    if config.fasta is not None:
        fasta = config.fasta.resolve()
        command.extend(["--volume", f"{fasta.parent}:/reference:ro"])
        fasta_path = f"/reference/{fasta.name}"
    command.extend(
        [
            config.image,
            "vep",
            "--input_file",
            f"/input/{source.name}",
            "--output_file",
            f"/output/{output.name}",
            "--format",
            "vcf",
            "--tab",
            "--fields",
            ",".join(VEP_TAB_FIELDS),
            "--cache",
            "--offline",
            "--dir_cache",
            "/data",
            "--cache_version",
            str(config.cache_version),
            "--species",
            "homo_sapiens",
            "--assembly",
            "GRCh38",
            *LOCAL_VEP_FLAGS,
            "--fork",
            str(config.forks),
            "--force_overwrite",
            "--no_stats",
        ]
    )
    if fasta_path is not None:
        command.extend(["--fasta", fasta_path, "--check_ref"])
    return command


def _configuration(config: LocalVEPConfig) -> dict[str, Any]:
    payload = asdict(config)
    payload["cache_dir"] = str(config.cache_dir.resolve())
    payload["fasta"] = str(config.fasta.resolve()) if config.fasta is not None else None
    payload["options"] = list(LOCAL_VEP_FLAGS)
    payload["output_fields"] = list(VEP_TAB_FIELDS)
    payload["output_format"] = "tab"
    return payload


def _cache_matches(
    output: Path,
    manifest: Path,
    source_checksum: str,
    configuration: dict[str, Any],
) -> bool:
    if not output.is_file() or output.stat().st_size == 0 or not manifest.is_file():
        return False
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(
        payload.get("input_sha256") == source_checksum
        and payload.get("configuration") == configuration
        and payload.get("output_sha256") == file_digest(output)
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _validate_biallelic_vcf(source: Path) -> None:
    opener = gzip.open if source.suffix == ".gz" else Path.open
    records = 0
    with opener(source, mode="rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.rstrip().split("\t")
            if len(fields) < 5:
                raise LocalVEPError(f"line {line_number}: expected at least 5 VCF columns")
            if "," in fields[4]:
                raise LocalVEPError(
                    f"line {line_number}: local VEP input must contain one ALT allele per row"
                )
            if fields[3].upper() == fields[4].upper():
                raise LocalVEPError(f"line {line_number}: REF and ALT alleles must differ")
            records += 1
    if records == 0:
        raise LocalVEPError("local VEP input contains no variants")
