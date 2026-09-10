import json
from pathlib import Path

import pandas as pd
import pytest

from variantrank.annotation import VEPRequestError, convert_vep_output

FIXTURE = Path(__file__).parents[1] / "fixtures" / "vep_response.json"


def test_convert_vep_output_writes_typed_parquet_and_cache(tmp_path: Path) -> None:
    source = tmp_path / "vep.jsonl"
    output = tmp_path / "annotations.parquet"
    payload = json.loads(FIXTURE.read_text())[0]
    source.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    first = convert_vep_output(source, output, batch_size=1)
    second = convert_vep_output(source, output, batch_size=1)
    frame = pd.read_parquet(output)

    assert first.rows == 1
    assert second.cached is True
    assert frame.loc[0, "variant"] == "17:7674220:C:T"
    assert frame.loc[0, "gene"] == "TP53"
    assert frame.loc[0, "canonical"]


def test_convert_vep_output_rejects_invalid_json_and_cleans_partial(tmp_path: Path) -> None:
    source = tmp_path / "invalid.jsonl"
    output = tmp_path / "annotations.parquet"
    source.write_text("not-json\n", encoding="utf-8")

    with pytest.raises(VEPRequestError, match="line 1"):
        convert_vep_output(source, output)

    assert not output.with_suffix(".parquet.partial").exists()


def test_convert_allowlisted_tab_output(tmp_path: Path) -> None:
    source = tmp_path / "vep.tsv"
    output = tmp_path / "annotations.parquet"
    source.write_text(
        "## ENSEMBL VARIANT EFFECT PREDICTOR v116.1\n"
        "#Uploaded_variation\tAllele\tGene\tFeature\tConsequence\tProtein_position\t"
        "Amino_acids\tCodons\tSYMBOL\tIMPACT\tBIOTYPE\tEXON\tINTRON\tCANONICAL\t"
        "MANE_SELECT\tAF\tAFR_AF\tAMR_AF\tEAS_AF\tSAS_AF\tgnomADe_AF\t"
        "gnomADe_AFR_AF\tgnomADe_AMR_AF\tgnomADe_EAS_AF\tgnomADe_NFE_AF\t"
        "gnomADe_SAS_AF\n"
        "vr_MTc6NzY3NDIyMDpDOlQ\tT\tENSG00000141510\tENST00000269305\t"
        "missense_variant\t?-1585\tR/Q\tcGg/cAg\tTP53\tMODERATE\tprotein_coding\t"
        "7/11\t-\tYES\tNM_000546.6\t-\t-\t-\t-\t-\t6.158e-06\t0\t0\t"
        "2.519e-05\t6.296e-06\t0\n",
        encoding="utf-8",
    )

    result = convert_vep_output(source, output)
    frame = pd.read_parquet(output)

    assert result.rows == 1
    assert frame.loc[0, "variant"] == "17:7674220:C:T"
    assert frame.loc[0, "gene"] == "TP53"
    assert pd.isna(frame.loc[0, "protein_position"])
    assert frame.loc[0, "allele_frequency"] == pytest.approx(6.158e-06)
    assert frame.loc[0, "population_max_af"] == pytest.approx(2.519e-05)
