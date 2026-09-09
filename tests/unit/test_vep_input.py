import gzip
import json
from pathlib import Path

import pandas as pd
import pytest

from variantrank.annotation import export_vep_input, parse_vep_response


def test_export_vep_input_streams_compressed_vcf_and_reuses_cache(tmp_path: Path) -> None:
    dataset = tmp_path / "clinvar.parquet"
    output = tmp_path / "clinvar.vep.vcf.gz"
    pd.DataFrame(
        {
            "chrom": ["17", "13"],
            "pos": [7674220, 32340301],
            "ref": ["C", "C"],
            "alt": ["T", "G"],
        }
    ).to_parquet(dataset, index=False)

    first = export_vep_input(dataset, output, batch_size=1)
    second = export_vep_input(dataset, output, batch_size=1)
    with gzip.open(output, mode="rt", encoding="utf-8") as handle:
        lines = [line.rstrip() for line in handle]
    identifier = lines[3].split("\t")[2]
    restored = parse_vep_response([{"input": f"17 7674220 {identifier} C T . . ."}])[0]
    manifest = json.loads(first.manifest.read_text())

    assert first.rows == 2
    assert second.cached is True
    assert lines[2].startswith("#CHROM")
    assert restored.variant == "17:7674220:C:T"
    assert len(manifest["output_sha256"]) == 64


def test_export_vep_input_validates_schema_and_batch_size(tmp_path: Path) -> None:
    dataset = tmp_path / "invalid.parquet"
    pd.DataFrame({"chrom": ["1"]}).to_parquet(dataset, index=False)

    with pytest.raises(ValueError, match="batch_size"):
        export_vep_input(dataset, tmp_path / "output.vcf", batch_size=0)
    with pytest.raises(ValueError, match="missing VEP input columns"):
        export_vep_input(dataset, tmp_path / "output.vcf")
