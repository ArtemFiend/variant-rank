"""Ensembl VEP REST adapter for small inference batches."""

import json
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from variantrank.data import read_vcf
from variantrank.data.download import file_digest
from variantrank.domain import Variant

DEFAULT_VEP_URL = "https://rest.ensembl.org"
MAX_REST_BATCH_SIZE = 200
Transport = Callable[[str, dict[str, list[str]], float], object]


class VEPRequestError(RuntimeError):
    """Raised when Ensembl VEP cannot return a valid annotation response."""


@dataclass(frozen=True, slots=True)
class VEPAnnotation:
    """Stable, flattened annotation contract for one alternate allele."""

    variant: str
    gene: str | None
    gene_id: str | None
    transcript: str | None
    consequence: str
    impact: str | None
    biotype: str | None
    exon: str | None
    intron: str | None
    protein_position: int | None
    amino_acids: str | None
    codons: str | None
    canonical: bool
    mane_select: str | None
    allele_frequency: float | None
    population_max_af: float | None
    afr_af: float | None
    amr_af: float | None
    eas_af: float | None
    nfe_af: float | None
    sas_af: float | None
    rare_variant_flag: bool | None


class VEPClient:
    """Batched client for the GRCh38 Ensembl VEP REST endpoint."""

    def __init__(
        self,
        *,
        server: str = DEFAULT_VEP_URL,
        batch_size: int = MAX_REST_BATCH_SIZE,
        timeout: float = 60.0,
        transport: Transport | None = None,
    ) -> None:
        if not 1 <= batch_size <= MAX_REST_BATCH_SIZE:
            raise ValueError(f"batch_size must be between 1 and {MAX_REST_BATCH_SIZE}")
        self.server = server.rstrip("/")
        self.batch_size = batch_size
        self.timeout = timeout
        self.transport = transport or _post_json

    def annotate(self, variants: Sequence[Variant]) -> list[VEPAnnotation]:
        """Annotate variants while preserving input order and cardinality."""
        annotations: list[VEPAnnotation] = []
        for start in range(0, len(variants), self.batch_size):
            batch = variants[start : start + self.batch_size]
            identifiers = [f"vr{index}" for index in range(len(batch))]
            payload = {
                "variants": [
                    _as_vcf_record(variant, identifier)
                    for variant, identifier in zip(batch, identifiers, strict=True)
                ]
            }
            response = self.transport(self.endpoint, payload, self.timeout)
            if not isinstance(response, list):
                raise VEPRequestError("VEP response must be a JSON array")
            parsed = parse_vep_response(response)
            by_identifier = {annotation.variant: annotation for annotation in parsed}
            for variant, identifier in zip(batch, identifiers, strict=True):
                annotation = by_identifier.get(identifier)
                if annotation is None:
                    raise VEPRequestError(f"VEP response omitted variant {variant.key}")
                annotations.append(replace(annotation, variant=variant.key))
        return annotations

    @property
    def endpoint(self) -> str:
        options = urlencode(
            {
                "af": 1,
                "af_gnomade": 1,
                "canonical": 1,
                "mane": 1,
                "numbers": 1,
                "pick": 1,
                "protein": 1,
                "variant_class": 1,
            }
        )
        return f"{self.server}/vep/homo_sapiens/region?{options}"


def parse_vep_response(payload: Iterable[Mapping[str, Any]]) -> list[VEPAnnotation]:
    """Flatten the relevant fields from VEP JSON responses."""
    annotations: list[VEPAnnotation] = []
    for result in payload:
        variant_key = _variant_key(result)
        transcript = _pick_transcript(result.get("transcript_consequences"))
        terms = transcript.get("consequence_terms", [])
        consequence = "&".join(str(term) for term in terms) if terms else "intergenic_variant"
        frequencies = _frequencies(result, transcript)
        population_values = [
            value
            for name, value in frequencies.items()
            if name in {"afr", "amr", "eas", "nfe", "sas"} and value is not None
        ]
        overall_values = [
            value
            for name, value in frequencies.items()
            if name in {"af", "gnomade", "gnomadg"} and value is not None
        ]
        allele_frequency = max(overall_values, default=None)
        population_max = max(population_values, default=allele_frequency)
        annotations.append(
            VEPAnnotation(
                variant=variant_key,
                gene=_string(transcript.get("gene_symbol")),
                gene_id=_string(transcript.get("gene_id")),
                transcript=_string(transcript.get("transcript_id")),
                consequence=consequence,
                impact=_string(transcript.get("impact")),
                biotype=_string(transcript.get("biotype")),
                exon=_string(transcript.get("exon")),
                intron=_string(transcript.get("intron")),
                protein_position=_integer(transcript.get("protein_start")),
                amino_acids=_string(transcript.get("amino_acids")),
                codons=_string(transcript.get("codons")),
                canonical=_boolean(transcript.get("canonical")),
                mane_select=_string(transcript.get("mane_select")),
                allele_frequency=allele_frequency,
                population_max_af=population_max,
                afr_af=frequencies.get("afr"),
                amr_af=frequencies.get("amr"),
                eas_af=frequencies.get("eas"),
                nfe_af=frequencies.get("nfe"),
                sas_af=frequencies.get("sas"),
                rare_variant_flag=None if population_max is None else population_max <= 0.01,
            )
        )
    return annotations


def annotate_vcf(
    source: Path,
    output_dir: Path,
    *,
    client: VEPClient | None = None,
) -> tuple[Path, Path]:
    """Annotate a VCF and persist tabular annotations plus provenance."""
    variants = list(read_vcf(source))
    if not variants:
        raise ValueError("VCF contains no variants")
    selected_client = client or VEPClient()
    annotations = selected_client.annotate(variants)
    output_dir.mkdir(parents=True, exist_ok=True)
    annotations_path = (
        output_dir / f"{source.name.removesuffix('.gz').removesuffix('.vcf')}.vep.parquet"
    )
    metadata_path = annotations_path.with_suffix(".metadata.json")
    pd.DataFrame(asdict(annotation) for annotation in annotations).to_parquet(
        annotations_path, index=False
    )
    metadata_path.write_text(
        json.dumps(
            {
                "assembly": "GRCh38",
                "created_at": datetime.now(UTC).isoformat(),
                "endpoint": selected_client.endpoint,
                "input": str(source),
                "input_sha256": file_digest(source),
                "records": len(annotations),
                "schema": list(asdict(annotations[0])),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return annotations_path, metadata_path


def _post_json(url: str, payload: dict[str, list[str]], timeout: float) -> object:
    request = Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(3):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read())
        except HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise VEPRequestError(f"VEP request failed with HTTP {error.code}") from error
            delay = min(float(error.headers.get("Retry-After", attempt + 1)), 30.0)
        except (URLError, TimeoutError) as error:
            if attempt == 2:
                raise VEPRequestError(f"VEP request failed: {error}") from error
            delay = float(attempt + 1)
        time.sleep(delay)
    raise AssertionError("unreachable")


def _as_vcf_record(variant: Variant, identifier: str) -> str:
    return f"{variant.chrom} {variant.pos} {identifier} {variant.ref} {variant.alt} . . ."


def _variant_key(result: Mapping[str, Any]) -> str:
    fields = str(result.get("input", "")).split()
    if len(fields) >= 3 and fields[2] not in {"", "."}:
        return fields[2]
    raise VEPRequestError("VEP response has no input variant identifier")


def _pick_transcript(value: object) -> Mapping[str, Any]:
    if not isinstance(value, list) or not value:
        return {}
    transcripts = [item for item in value if isinstance(item, Mapping)]
    if not transcripts:
        return {}
    return max(
        transcripts,
        key=lambda item: (
            bool(item.get("pick")),
            bool(item.get("mane_select")),
            bool(item.get("canonical")),
        ),
    )


def _frequencies(
    result: Mapping[str, Any], transcript: Mapping[str, Any]
) -> dict[str, float | None]:
    allele = _string(transcript.get("variant_allele"))
    values: dict[str, float | None] = {}
    colocated = result.get("colocated_variants", [])
    if not isinstance(colocated, list):
        return values
    for record in colocated:
        if not isinstance(record, Mapping):
            continue
        all_frequencies = record.get("frequencies")
        if not isinstance(all_frequencies, Mapping):
            continue
        allele_frequencies = all_frequencies.get(allele, {})
        if not isinstance(allele_frequencies, Mapping):
            continue
        for raw_name, raw_value in allele_frequencies.items():
            name = str(raw_name).lower()
            normalized = next(
                (
                    population
                    for population in ("afr", "amr", "eas", "nfe", "sas")
                    if name.endswith(population)
                ),
                name,
            )
            value = _float(raw_value)
            if value is not None:
                values[normalized] = max(value, values.get(normalized) or 0.0)
    return values


def _string(value: object) -> str | None:
    return str(value) if value is not None and value != "" and value != "-" else None


def _integer(value: object) -> int | None:
    try:
        return int(str(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def _boolean(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _float(value: object) -> float | None:
    try:
        return float(str(value)) if value is not None else None
    except (TypeError, ValueError):
        return None
