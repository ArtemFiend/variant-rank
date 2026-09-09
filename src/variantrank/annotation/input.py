"""Streaming conversion from curated Parquet rows to VEP-ready VCF."""

import gzip
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

import pyarrow.parquet as pq

from variantrank.annotation.vep import encode_variant_identifier
from variantrank.data.download import file_digest

VEP_INPUT_COLUMNS = ("chrom", "pos", "ref", "alt")


@dataclass(frozen=True, slots=True)
class VEPInputResult:
    """Output of a streaming training-dataset export."""

    output: Path
    manifest: Path
    rows: int
    cached: bool


def export_vep_input(
    dataset: Path,
    output: Path,
    *,
    batch_size: int = 100_000,
    force: bool = False,
) -> VEPInputResult:
    """Export required Parquet columns as an atomic, VEP-compatible VCF."""
    if not dataset.is_file():
        raise FileNotFoundError(dataset)
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    source_checksum = file_digest(dataset)
    manifest = output.with_suffix(output.suffix + ".manifest.json")
    cached_rows = _cached_rows(output, manifest, source_checksum)
    if not force and cached_rows is not None:
        return VEPInputResult(output, manifest, cached_rows, cached=True)

    parquet = pq.ParquetFile(dataset)
    missing = set(VEP_INPUT_COLUMNS) - set(parquet.schema.names)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"dataset is missing VEP input columns: {names}")

    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + ".partial")
    partial.unlink(missing_ok=True)
    rows = 0
    with _open_output(partial, compressed=output.suffix == ".gz") as handle:
        handle.write("##fileformat=VCFv4.2\n")
        handle.write("##reference=GRCh38\n")
        handle.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n")
        for batch in parquet.iter_batches(batch_size=batch_size, columns=list(VEP_INPUT_COLUMNS)):
            chroms, positions, refs, alts = (batch.column(index).to_pylist() for index in range(4))
            for chrom, pos, ref, alt in zip(chroms, positions, refs, alts, strict=True):
                variant_key = f"{chrom}:{pos}:{ref}:{alt}"
                identifier = encode_variant_identifier(variant_key)
                handle.write(f"{chrom}\t{pos}\t{identifier}\t{ref}\t{alt}\t.\tPASS\t.\n")
                rows += 1
    if rows == 0:
        partial.unlink(missing_ok=True)
        raise ValueError("dataset contains no variants")
    partial.replace(output)
    manifest.write_text(
        json.dumps(
            {
                "assembly": "GRCh38",
                "created_at": datetime.now(UTC).isoformat(),
                "dataset": str(dataset),
                "dataset_sha256": source_checksum,
                "output": str(output),
                "output_sha256": file_digest(output),
                "rows": rows,
                "variant_id_encoding": "urlsafe-base64",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return VEPInputResult(output, manifest, rows, cached=False)


def _open_output(path: Path, *, compressed: bool) -> TextIO:
    if compressed:
        return gzip.open(path, mode="wt", encoding="utf-8")
    return path.open(mode="w", encoding="utf-8")


def _cached_rows(output: Path, manifest: Path, source_checksum: str) -> int | None:
    if not output.is_file() or output.stat().st_size == 0 or not manifest.is_file():
        return None
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        if payload.get("dataset_sha256") == source_checksum and payload.get(
            "output_sha256"
        ) == file_digest(output):
            return int(payload["rows"])
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError):
        return None
    return None
