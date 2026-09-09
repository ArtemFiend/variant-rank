import json
from pathlib import Path

import pandas as pd
import pytest

from variantrank.annotation import VEPClient, VEPRequestError, annotate_vcf, parse_vep_response
from variantrank.domain import Variant

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_parse_vep_response_flattens_transcript_and_frequencies() -> None:
    payload = json.loads((FIXTURES / "vep_response.json").read_text())

    annotation = parse_vep_response(payload)[0]

    assert annotation.variant == "17:7674220:C:T"
    assert annotation.gene == "TP53"
    assert annotation.consequence == "missense_variant"
    assert annotation.protein_position == 273
    assert annotation.allele_frequency == pytest.approx(0.00002)
    assert annotation.population_max_af == pytest.approx(0.00003)
    assert annotation.rare_variant_flag is True


def test_client_batches_and_restores_input_order() -> None:
    payload = json.loads((FIXTURES / "vep_response.json").read_text())
    calls: list[dict[str, list[str]]] = []

    def transport(_url: str, request: dict[str, list[str]], _timeout: float) -> object:
        calls.append(request)
        response = json.loads(json.dumps(payload[0]))
        response["input"] = request["variants"][0]
        return [response]

    variants = [
        Variant("17", 7674220, "C", "T"),
        Variant("13", 32340301, "C", "T"),
    ]
    client = VEPClient(batch_size=1, transport=transport)

    annotations = client.annotate(variants)

    assert [annotation.variant for annotation in annotations] == [
        variant.key for variant in variants
    ]
    assert len(calls) == 2


def test_client_rejects_missing_annotation() -> None:
    client = VEPClient(transport=lambda _url, _payload, _timeout: [])

    with pytest.raises(VEPRequestError, match="omitted variant"):
        client.annotate([Variant("1", 100, "A", "G")])


def test_client_validates_batch_size_and_response_shape() -> None:
    with pytest.raises(ValueError, match="batch_size"):
        VEPClient(batch_size=201)

    client = VEPClient(transport=lambda _url, _payload, _timeout: {"error": "failed"})
    with pytest.raises(VEPRequestError, match="JSON array"):
        client.annotate([Variant("1", 100, "A", "G")])


def test_parse_intergenic_result_preserves_missing_frequency() -> None:
    result = parse_vep_response([{"input": "1 100 1:100:A:G A G . . ."}])[0]

    assert result.consequence == "intergenic_variant"
    assert result.gene is None
    assert result.population_max_af is None
    assert result.rare_variant_flag is None


def test_annotate_vcf_persists_contract(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "vep_response.json").read_text())

    def transport(_url: str, request: dict[str, list[str]], _timeout: float) -> object:
        responses = []
        for value in request["variants"]:
            response = json.loads(json.dumps(payload[0]))
            response["input"] = value
            responses.append(response)
        return responses

    annotations, metadata = annotate_vcf(
        FIXTURES / "example.vcf",
        tmp_path,
        client=VEPClient(transport=transport),
    )

    frame = pd.read_parquet(annotations)
    assert len(frame) == 3
    assert frame["variant"].is_unique
    assert metadata.is_file()
