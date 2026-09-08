from pathlib import Path

import pytest

from variantrank.data.vcf import (
    VCFFormatError,
    canonical_chromosome,
    minimal_representation,
    read_vcf,
    validate_vcf,
)

FIXTURE = Path(__file__).parents[1] / "fixtures" / "example.vcf"


def test_read_vcf_splits_multiallelic_records() -> None:
    variants = list(read_vcf(FIXTURE))

    assert len(variants) == 3
    assert variants[0].key == "17:7674220:C:T"
    assert variants[1].chrom == "13"


def test_validate_vcf_reports_record_and_allele_counts() -> None:
    summary = validate_vcf(FIXTURE)

    assert summary.records == 2
    assert summary.alleles == 3
    assert summary.chromosomes == ("13", "17")


def test_minimal_representation_trims_shared_sequence() -> None:
    assert minimal_representation(100, "ACG", "ATG") == (101, "C", "T")


def test_symbolic_allele_is_not_trimmed() -> None:
    assert minimal_representation(100, "A", "<DEL>") == (100, "A", "<DEL>")


@pytest.mark.parametrize(("raw", "expected"), [("Chr1", "1"), ("chrM", "MT"), ("mt", "MT")])
def test_canonical_chromosome(raw: str, expected: str) -> None:
    assert canonical_chromosome(raw) == expected


def test_read_vcf_requires_header(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.vcf"
    invalid.write_text("1\t1\t.\tA\tT\t.\tPASS\t.\n", encoding="utf-8")

    with pytest.raises(VCFFormatError, match="#CHROM"):
        list(read_vcf(invalid))


def test_read_vcf_rejects_short_record(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.vcf"
    invalid.write_text("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n1\t1\t.\tA\tT\n")

    with pytest.raises(VCFFormatError, match="8 columns"):
        list(read_vcf(invalid))


def test_read_vcf_rejects_invalid_position(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.vcf"
    invalid.write_text(
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n1\tbad\t.\tA\tT\t.\tPASS\t.\n"
    )

    with pytest.raises(VCFFormatError, match="invalid POS"):
        list(read_vcf(invalid))
