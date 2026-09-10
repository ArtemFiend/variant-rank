"""Genomic variant domain model."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Variant:
    """A single alternate allele from a VCF record."""

    chrom: str
    pos: int
    ref: str
    alt: str
    identifier: str | None = None

    def __post_init__(self) -> None:
        if not self.chrom:
            raise ValueError("chromosome must not be empty")
        if self.pos < 1:
            raise ValueError("position must be a positive 1-based coordinate")
        if not self.ref or self.ref == ".":
            raise ValueError("REF allele must not be empty")
        if not self.alt or self.alt == ".":
            raise ValueError("ALT allele must not be empty")
        if self.ref == self.alt:
            raise ValueError("REF and ALT alleles must differ")

    @property
    def key(self) -> str:
        """Return a stable variant key."""
        return f"{self.chrom}:{self.pos}:{self.ref}:{self.alt}"
