import json
import subprocess
from pathlib import Path

import pytest

from variantrank.annotation import (
    LocalVEPConfig,
    LocalVEPError,
    format_command,
    run_local_vep,
)

FIXTURE = Path(__file__).parents[1] / "fixtures" / "example.vcf"


def test_dry_run_builds_pinned_offline_command(tmp_path: Path) -> None:
    config = LocalVEPConfig(cache_dir=tmp_path / "cache", forks=6)

    result = run_local_vep(FIXTURE, tmp_path / "vep.jsonl", config, dry_run=True)
    rendered = format_command(result.command)

    assert result.executed is False
    assert "ensemblorg/ensembl-vep:release_116.1" in rendered
    assert "--offline" in result.command
    assert "--cache_version 116" in rendered
    assert "--fork 6" in rendered


def test_successful_run_writes_manifest_and_is_cached(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    output = tmp_path / "vep.jsonl"
    partial = tmp_path / "vep.jsonl.partial"
    calls = 0

    def runner(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        partial.write_text('{"input":"example"}\n', encoding="utf-8")
        return subprocess.CompletedProcess([], 0, stdout="", stderr="")

    config = LocalVEPConfig(cache_dir=cache)
    first = run_local_vep(FIXTURE, output, config, runner=runner)
    second = run_local_vep(FIXTURE, output, config, runner=runner)
    manifest = json.loads(first.manifest.read_text())

    assert first.executed is True
    assert second.cached is True
    assert calls == 1
    assert len(manifest["input_sha256"]) == 64
    assert len(manifest["output_sha256"]) == 64


def test_failed_run_removes_partial_output(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    output = tmp_path / "vep.jsonl"
    partial = tmp_path / "vep.jsonl.partial"

    def runner(*_args, **_kwargs):
        partial.write_text("partial", encoding="utf-8")
        return subprocess.CompletedProcess([], 2, stdout="", stderr="invalid variant")

    with pytest.raises(LocalVEPError, match="invalid variant"):
        run_local_vep(FIXTURE, output, LocalVEPConfig(cache_dir=cache), runner=runner)

    assert not partial.exists()


def test_run_requires_cache_for_execution(tmp_path: Path) -> None:
    with pytest.raises(LocalVEPError, match="cache directory"):
        run_local_vep(
            FIXTURE,
            tmp_path / "vep.jsonl",
            LocalVEPConfig(cache_dir=tmp_path / "missing"),
        )


def test_config_rejects_invalid_parallelism(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="forks"):
        LocalVEPConfig(cache_dir=tmp_path, forks=0)

    with pytest.raises(ValueError, match="cache_version"):
        LocalVEPConfig(cache_dir=tmp_path, cache_version=0)


def test_run_rejects_success_without_output(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()

    def runner(*_args, **_kwargs):
        return subprocess.CompletedProcess([], 0, stdout="", stderr="")

    with pytest.raises(LocalVEPError, match="non-empty output"):
        run_local_vep(
            FIXTURE,
            tmp_path / "vep.jsonl",
            LocalVEPConfig(cache_dir=cache),
            runner=runner,
        )
