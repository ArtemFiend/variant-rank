"""Streaming conversion of local VEP JSON Lines into the annotation contract."""

import gzip
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

import pyarrow as pa
import pyarrow.parquet as pq

from variantrank.annotation.vep import VEPRequestError, parse_vep_response
from variantrank.data.download import file_digest

ANNOTATION_SCHEMA = pa.schema(
    [
        ("variant", pa.string()),
        ("gene", pa.string()),
        ("gene_id", pa.string()),
        ("transcript", pa.string()),
        ("consequence", pa.string()),
        ("impact", pa.string()),
        ("biotype", pa.string()),
        ("exon", pa.string()),
        ("intron", pa.string()),
        ("protein_position", pa.int64()),
        ("amino_acids", pa.string()),
        ("codons", pa.string()),
        ("canonical", pa.bool_()),
        ("mane_select", pa.string()),
        ("allele_frequency", pa.float64()),
        ("population_max_af", pa.float64()),
        ("afr_af", pa.float64()),
        ("amr_af", pa.float64()),
        ("eas_af", pa.float64()),
        ("nfe_af", pa.float64()),
        ("sas_af", pa.float64()),
        ("rare_variant_flag", pa.bool_()),
    ]
)


@dataclass(frozen=True, slots=True)
class VEPOutputResult:
    """Output of a raw local VEP JSON conversion."""

    output: Path
    manifest: Path
    rows: int
    cached: bool


def convert_vep_output(
    source: Path,
    output: Path,
    *,
    batch_size: int = 50_000,
    force: bool = False,
) -> VEPOutputResult:
    """Convert VEP JSON Lines to an atomic, typed Parquet dataset."""
    if not source.is_file():
        raise FileNotFoundError(source)
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    source_checksum = file_digest(source)
    manifest = output.with_suffix(output.suffix + ".manifest.json")
    cached_rows = _cached_rows(output, manifest, source_checksum)
    if not force and cached_rows is not None:
        return VEPOutputResult(output, manifest, cached_rows, cached=True)

    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + ".partial")
    partial.unlink(missing_ok=True)
    writer = pq.ParquetWriter(partial, ANNOTATION_SCHEMA, compression="zstd")
    buffer: list[dict[str, object]] = []
    rows = 0
    try:
        with _open_input(source) as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                if not raw_line.strip():
                    continue
                try:
                    payload = json.loads(raw_line)
                except json.JSONDecodeError as error:
                    raise VEPRequestError(f"invalid VEP JSON at line {line_number}") from error
                if not isinstance(payload, dict):
                    raise VEPRequestError(f"VEP JSON line {line_number} must be an object")
                annotations = parse_vep_response([payload])
                buffer.append(asdict(annotations[0]))
                rows += 1
                if len(buffer) >= batch_size:
                    _write_batch(writer, buffer)
                    buffer.clear()
        if buffer:
            _write_batch(writer, buffer)
    except Exception:
        writer.close()
        partial.unlink(missing_ok=True)
        raise
    writer.close()
    if rows == 0:
        partial.unlink(missing_ok=True)
        raise ValueError("VEP output contains no annotations")
    partial.replace(output)
    manifest.write_text(
        json.dumps(
            {
                "created_at": datetime.now(UTC).isoformat(),
                "output": str(output),
                "output_sha256": file_digest(output),
                "rows": rows,
                "schema": ANNOTATION_SCHEMA.names,
                "source": str(source),
                "source_sha256": source_checksum,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return VEPOutputResult(output, manifest, rows, cached=False)


def _write_batch(writer: pq.ParquetWriter, records: list[dict[str, object]]) -> None:
    writer.write_table(pa.Table.from_pylist(records, schema=ANNOTATION_SCHEMA))


def _open_input(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return gzip.open(path, mode="rt", encoding="utf-8")
    return path.open(encoding="utf-8")


def _cached_rows(output: Path, manifest: Path, source_checksum: str) -> int | None:
    if not output.is_file() or output.stat().st_size == 0 or not manifest.is_file():
        return None
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        if payload.get("source_sha256") == source_checksum and payload.get(
            "output_sha256"
        ) == file_digest(output):
            return int(payload["rows"])
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError):
        return None
    return None
