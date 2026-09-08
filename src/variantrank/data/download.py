"""Download helpers with atomic writes and checksum verification."""

import shutil
from dataclasses import dataclass
from hashlib import md5, sha256
from pathlib import Path
from typing import Literal, cast
from urllib.request import Request, urlopen

USER_AGENT = "VariantRank/0.1 (+https://github.com/ArtemFiend/variant-rank)"


class ChecksumError(ValueError):
    """Raised when a downloaded file does not match its published checksum."""


@dataclass(frozen=True, slots=True)
class DownloadResult:
    """Provenance captured for a downloaded source file."""

    path: Path
    url: str
    md5: str
    sha256: str
    bytes: int
    last_modified: str | None
    downloaded: bool


def file_digest(path: Path, algorithm: Literal["md5", "sha256"] = "sha256") -> str:
    """Calculate a streaming digest without loading the file into memory."""
    digest = sha256() if algorithm == "sha256" else md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch_published_md5(url: str) -> str:
    """Read the first hexadecimal digest from an NCBI ``.md5`` file."""
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        payload = cast(bytes, response.read()).decode("utf-8")
    checksum = payload.split(maxsplit=1)[0].strip().lower()
    if len(checksum) != 32 or any(char not in "0123456789abcdef" for char in checksum):
        raise ChecksumError(f"invalid MD5 response from {url}")
    return checksum


def download_file(
    url: str,
    destination: Path,
    *,
    expected_md5: str,
    force: bool = False,
) -> DownloadResult:
    """Download a file atomically and verify the publisher-provided MD5."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    normalized_md5 = expected_md5.lower()

    if destination.exists() and not force:
        actual_md5 = file_digest(destination, "md5")
        if actual_md5 != normalized_md5:
            raise ChecksumError(
                f"existing file checksum mismatch: expected {normalized_md5}, got {actual_md5}"
            )
        return _result(destination, url, actual_md5, None, downloaded=False)

    temporary = destination.with_suffix(f"{destination.suffix}.part")
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=120) as response:
            last_modified = response.headers.get("Last-Modified")
            with temporary.open("wb") as output:
                shutil.copyfileobj(response, output, length=1024 * 1024)

        actual_md5 = file_digest(temporary, "md5")
        if actual_md5 != normalized_md5:
            raise ChecksumError(
                f"download checksum mismatch: expected {normalized_md5}, got {actual_md5}"
            )
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    return _result(destination, url, actual_md5, last_modified, downloaded=True)


def _result(
    path: Path,
    url: str,
    actual_md5: str,
    last_modified: str | None,
    *,
    downloaded: bool,
) -> DownloadResult:
    return DownloadResult(
        path=path,
        url=url,
        md5=actual_md5,
        sha256=file_digest(path),
        bytes=path.stat().st_size,
        last_modified=last_modified,
        downloaded=downloaded,
    )
