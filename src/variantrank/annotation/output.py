"""Streaming conversion of local VEP output into the annotation contract."""

import gzip
import json
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

import pyarrow as pa
import pyarrow.parquet as pq

from variantrank.annotation.vep import (
    VEPRequestError,
    decode_variant_identifier,
    parse_vep_response,
)
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
    """Output of a raw local VEP conversion."""

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
    """Convert allowlisted VEP TSV or JSON Lines to typed Parquet."""
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
        for record in _iter_records(source):
            buffer.append(record)
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


def _iter_records(source: Path) -> Iterator[dict[str, object]]:
    header: list[str] | None = None
    with _open_input(source) as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("##"):
                continue
            if line.startswith("#"):
                header = line[1:].split("\t")
                continue
            if line.startswith("{"):
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as error:
                    raise VEPRequestError(f"invalid VEP JSON at line {line_number}") from error
                if not isinstance(payload, dict):
                    raise VEPRequestError(f"VEP JSON line {line_number} must be an object")
                yield asdict(parse_vep_response([payload])[0])
                continue
            if header is None:
                raise VEPRequestError(f"VEP tabular output has no header before line {line_number}")
            values = line.split("\t")
            if len(values) != len(header):
                raise VEPRequestError(f"VEP tabular line {line_number} has incorrect field count")
            yield _tab_record(dict(zip(header, values, strict=True)))


def _tab_record(row: dict[str, str]) -> dict[str, object]:
    required = {"Uploaded_variation", "Consequence", "Allele"}
    missing = required - set(row)
    if missing:
        names = ", ".join(sorted(missing))
        raise VEPRequestError(f"VEP tabular output is missing fields: {names}")
    afr = _maximum(_number(row.get("AFR_AF")), _number(row.get("gnomADe_AFR_AF")))
    amr = _maximum(_number(row.get("AMR_AF")), _number(row.get("gnomADe_AMR_AF")))
    eas = _maximum(_number(row.get("EAS_AF")), _number(row.get("gnomADe_EAS_AF")))
    nfe = _number(row.get("gnomADe_NFE_AF"))
    sas = _maximum(_number(row.get("SAS_AF")), _number(row.get("gnomADe_SAS_AF")))
    allele_frequency = _maximum(_number(row.get("AF")), _number(row.get("gnomADe_AF")))
    population_max = _maximum(afr, amr, eas, nfe, sas, allele_frequency)
    return {
        "variant": decode_variant_identifier(row["Uploaded_variation"]),
        "gene": _text(row.get("SYMBOL")),
        "gene_id": _text(row.get("Gene")),
        "transcript": _text(row.get("Feature")),
        "consequence": row["Consequence"],
        "impact": _text(row.get("IMPACT")),
        "biotype": _text(row.get("BIOTYPE")),
        "exon": _text(row.get("EXON")),
        "intron": _text(row.get("INTRON")),
        "protein_position": _position(row.get("Protein_position")),
        "amino_acids": _text(row.get("Amino_acids")),
        "codons": _text(row.get("Codons")),
        "canonical": row.get("CANONICAL") == "YES",
        "mane_select": _text(row.get("MANE_SELECT")),
        "allele_frequency": allele_frequency,
        "population_max_af": population_max,
        "afr_af": afr,
        "amr_af": amr,
        "eas_af": eas,
        "nfe_af": nfe,
        "sas_af": sas,
        "rare_variant_flag": None if population_max is None else population_max <= 0.01,
    }


def _text(value: str | None) -> str | None:
    return None if value in {None, "", "-", "?"} else value


def _number(value: str | None) -> float | None:
    text = _text(value)
    return float(text) if text is not None else None


def _position(value: str | None) -> int | None:
    text = _text(value)
    if text is None:
        return None
    start = text.split("-", maxsplit=1)[0]
    return None if start == "?" else int(start)


def _maximum(*values: float | None) -> float | None:
    present = [value for value in values if value is not None]
    return max(present, default=None)


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
