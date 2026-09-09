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
