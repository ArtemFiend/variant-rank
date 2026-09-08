from hashlib import md5
from pathlib import Path

import pytest

from variantrank.data.download import ChecksumError, download_file, file_digest


def test_download_file_verifies_checksum_and_reuses_valid_file(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    destination = tmp_path / "downloaded" / "source.txt"
    source.write_bytes(b"clinvar fixture\n")
    expected = md5(source.read_bytes(), usedforsecurity=False).hexdigest()

    downloaded = download_file(source.as_uri(), destination, expected_md5=expected)
    reused = download_file(source.as_uri(), destination, expected_md5=expected)

    assert downloaded.downloaded is True
    assert reused.downloaded is False
    assert file_digest(destination) == downloaded.sha256


def test_download_file_removes_partial_file_after_checksum_failure(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    destination = tmp_path / "downloaded.txt"
    source.write_text("unexpected content")

    with pytest.raises(ChecksumError, match="download checksum mismatch"):
        download_file(source.as_uri(), destination, expected_md5="0" * 32)

    assert not destination.exists()
    assert not destination.with_suffix(".txt.part").exists()
