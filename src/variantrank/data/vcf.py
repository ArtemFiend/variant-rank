"""Small dependency-free VCF reader used for validation and test fixtures."""

import gzip
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from variantrank.domain import Variant


class VCFFormatError(ValueError):
    """Raised when a VCF record is malformed."""


@dataclass(frozen=True, slots=True)
class VCFSummary:
    """Validation summary for one VCF file."""

    records: int
    alleles: int
    chromosomes: tuple[str, ...]


def canonical_chromosome(chrom: str) -> str:
    """Return a chromosome name without a ``chr`` prefix."""
    value = chrom[3:] if chrom[:3].lower() == "chr" else chrom
    return "MT" if value.upper() in {"M", "MT"} else value


def minimal_representation(pos: int, ref: str, alt: str) -> tuple[int, str, str]:
    """Trim shared allele bases while retaining one anchor base per allele.

    This is not reference-aware left alignment. Full indel normalization will be
    performed by bcftools in the annotation pipeline.
    """
    if alt.startswith("<") or "[" in alt or "]" in alt or alt == "*":
        return pos, ref, alt

    while len(ref) > 1 and len(alt) > 1 and ref[-1] == alt[-1]:
        ref = ref[:-1]
        alt = alt[:-1]
    while len(ref) > 1 and len(alt) > 1 and ref[0] == alt[0]:
        ref = ref[1:]
        alt = alt[1:]
        pos += 1
    return pos, ref, alt


def _open_text(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return gzip.open(path, mode="rt", encoding="utf-8")
    return path.open(encoding="utf-8")


def read_vcf(path: str | Path) -> Iterator[Variant]:
    """Yield one normalized :class:`Variant` for every ALT allele."""
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)

    saw_header = False
    with _open_text(source) as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.rstrip("\r\n")
            if not line:
                continue
            if line.startswith("##"):
                continue
            if line.startswith("#CHROM"):
                saw_header = True
                continue
            if line.startswith("#"):
                continue
            if not saw_header:
                raise VCFFormatError(f"line {line_number}: missing #CHROM header")

            fields = line.split("\t")
            if len(fields) < 8:
                raise VCFFormatError(f"line {line_number}: expected at least 8 columns")

            chrom, raw_pos, identifier, ref, alt_field = fields[:5]
            try:
                pos = int(raw_pos)
            except ValueError as error:
                raise VCFFormatError(f"line {line_number}: invalid POS {raw_pos!r}") from error

            for alt in alt_field.split(","):
                normalized_pos, normalized_ref, normalized_alt = minimal_representation(
                    pos, ref.upper(), alt.upper()
                )
                try:
                    yield Variant(
                        chrom=canonical_chromosome(chrom),
                        pos=normalized_pos,
                        ref=normalized_ref,
                        alt=normalized_alt,
                        identifier=None if identifier == "." else identifier,
                    )
                except ValueError as error:
                    raise VCFFormatError(f"line {line_number}: {error}") from error

    if not saw_header:
        raise VCFFormatError("missing #CHROM header")


def validate_vcf(path: str | Path) -> VCFSummary:
    """Parse a VCF and return counts useful for a fast input check."""
    variants = list(read_vcf(path))
    chromosomes = tuple(sorted({variant.chrom for variant in variants}))
    return VCFSummary(
        records=_count_records(Path(path)), alleles=len(variants), chromosomes=chromosomes
    )


def _count_records(path: Path) -> int:
    with _open_text(path) as handle:
        return sum(1 for line in handle if line.strip() and not line.startswith("#"))
