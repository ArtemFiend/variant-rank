import pytest

from variantrank.domain import Variant


def test_variant_key() -> None:
    variant = Variant(chrom="17", pos=7674220, ref="C", alt="T")

    assert variant.key == "17:7674220:C:T"


def test_variant_rejects_non_positive_position() -> None:
    with pytest.raises(ValueError, match="positive"):
        Variant(chrom="17", pos=0, ref="C", alt="T")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"chrom": "", "pos": 1, "ref": "A", "alt": "T"}, "chromosome"),
        ({"chrom": "1", "pos": 1, "ref": ".", "alt": "T"}, "REF"),
        ({"chrom": "1", "pos": 1, "ref": "A", "alt": "."}, "ALT"),
    ],
)
def test_variant_rejects_missing_fields(kwargs: dict[str, str | int], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        Variant(**kwargs)  # type: ignore[arg-type]


def test_variant_rejects_identical_ref_and_alt() -> None:
    with pytest.raises(ValueError, match="must differ"):
        Variant(chrom="1", pos=100, ref="A", alt="A")
