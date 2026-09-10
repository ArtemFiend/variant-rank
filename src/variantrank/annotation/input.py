"""Streaming conversion from curated Parquet rows to VEP-ready VCF."""

import gzip
import io
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

import pyarrow.parquet as pq

from variantrank.annotation.vep import encode_variant_identifier
from variantrank.data.download import file_digest

VEP_INPUT_COLUMNS = ("chrom", "pos", "ref", "alt")
CANONICAL_CHROMOSOMES = (*map(str, range(1, 23)), "X", "Y", "MT")
VEP_INPUT_VERSION = 2
VEP_SORT_ORDER = "canonical_chromosome,pos,ref,alt"


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
        for chrom in CANONICAL_CHROMOSOMES:
            table = pq.read_table(
                dataset,
                columns=list(VEP_INPUT_COLUMNS),
                filters=[("chrom", "=", chrom)],
            ).sort_by([("pos", "ascending"), ("ref", "ascending"), ("alt", "ascending")])
            for batch in table.to_batches(max_chunksize=batch_size):
                chroms, positions, refs, alts = (
                    batch.column(index).to_pylist() for index in range(4)
                )
                for row_chrom, pos, ref, alt in zip(chroms, positions, refs, alts, strict=True):
                    variant_key = f"{row_chrom}:{pos}:{ref}:{alt}"
                    identifier = encode_variant_identifier(variant_key)
                    handle.write(f"{row_chrom}\t{pos}\t{identifier}\t{ref}\t{alt}\t.\tPASS\t.\n")
                    rows += 1
    if rows != parquet.metadata.num_rows:
        partial.unlink(missing_ok=True)
        raise ValueError(
            "dataset contains non-canonical chromosomes: "
            f"exported {rows} of {parquet.metadata.num_rows} variants"
        )
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
                "sort_order": VEP_SORT_ORDER,
                "variant_id_encoding": "urlsafe-base64",
                "version": VEP_INPUT_VERSION,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return VEPInputResult(output, manifest, rows, cached=False)


@contextmanager
def _open_output(path: Path, *, compressed: bool) -> Iterator[TextIO]:
    if compressed:
        with (
            path.open(mode="wb") as raw,
            gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as compressed_file,
            io.TextIOWrapper(compressed_file, encoding="utf-8") as text_file,
        ):
            yield text_file
        return
    with path.open(mode="w", encoding="utf-8") as text_file:
        yield text_file


def _cached_rows(output: Path, manifest: Path, source_checksum: str) -> int | None:
    if not output.is_file() or output.stat().st_size == 0 or not manifest.is_file():
        return None
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        if (
            payload.get("version") == VEP_INPUT_VERSION
            and payload.get("dataset_sha256") == source_checksum
            and payload.get("output_sha256") == file_digest(output)
        ):
            return int(payload["rows"])
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError):
        return None
    return None
