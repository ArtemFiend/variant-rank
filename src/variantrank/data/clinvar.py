"""ClinVar label curation and reproducible dataset construction."""

import json
import re
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from variantrank import __version__
from variantrank.data.download import file_digest
from variantrank.data.vcf import canonical_chromosome, minimal_representation

DEFAULT_CLINVAR_URL = (
    "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz"
)
DEFAULT_CLINVAR_MD5_URL = f"{DEFAULT_CLINVAR_URL}.md5"

POSITIVE_TERMS = frozenset({"pathogenic", "likely pathogenic"})
NEGATIVE_TERMS = frozenset({"benign", "likely benign"})
SUPPORTED_VARIANT_TYPES = frozenset({"single nucleotide variant", "deletion", "insertion", "indel"})
CANONICAL_CHROMOSOMES = frozenset({*(str(value) for value in range(1, 23)), "X", "Y", "MT"})
HIGH_CONFIDENCE_REVIEWS = frozenset(
    {
        "criteria provided, multiple submitters, no conflicts",
        "reviewed by expert panel",
        "practice guideline",
    }
)
REVIEW_TIERS = {
    "no assertion criteria provided": 0,
    "no assertion provided": 0,
    "criteria provided, single submitter": 1,
    "criteria provided, multiple submitters, no conflicts": 2,
    "reviewed by expert panel": 3,
    "practice guideline": 4,
}

COLUMN_MAP = {
    "#AlleleID": "allele_id",
    "Type": "variant_type",
    "GeneSymbol": "gene",
    "ClinicalSignificance": "clinical_significance",
    "LastEvaluated": "last_evaluated",
    "PhenotypeList": "condition",
    "Assembly": "assembly",
    "Chromosome": "chrom",
    "ReviewStatus": "review_status",
    "NumberSubmitters": "number_submitters",
    "VariationID": "variation_id",
    "PositionVCF": "pos",
    "ReferenceAlleleVCF": "ref",
    "AlternateAlleleVCF": "alt",
}
REQUIRED_COLUMNS = frozenset(COLUMN_MAP)
OUTPUT_COLUMNS = [
    "variant_id",
    "variation_id",
    "allele_id",
    "chrom",
    "pos",
    "ref",
    "alt",
    "gene",
    "variant_type",
    "clinical_significance",
    "review_status",
    "review_tier",
    "number_submitters",
    "condition",
    "last_evaluated",
    "assembly",
    "target",
    "high_confidence",
]


class ClinVarSchemaError(ValueError):
    """Raised when the source does not satisfy the expected ClinVar schema."""


@dataclass(slots=True)
class ClinVarQC:
    """Auditable counters collected throughout label curation."""

    source_rows: int = 0
    assembly_rows: int = 0
    excluded_assembly: int = 0
    excluded_variant_type: int = 0
    excluded_label: int = 0
    excluded_gene: int = 0
    excluded_coordinates: int = 0
    excluded_noncanonical_chromosome: int = 0
    eligible_rows: int = 0
    conflicting_variants: int = 0
    duplicate_rows_removed: int = 0
    dataset_a_rows: int = 0
    dataset_a_pathogenic: int = 0
    dataset_a_benign: int = 0
    dataset_b_rows: int = 0
    dataset_b_pathogenic: int = 0
    dataset_b_benign: int = 0


@dataclass(frozen=True, slots=True)
class ClinVarBuildResult:
    """Paths and metrics produced by one dataset build."""

    dataset_a: Path
    dataset_b: Path
    qc_report: Path
    source_metadata: Path
    qc: ClinVarQC


def normalize_label(value: str) -> str:
    """Normalize ClinVar label typography while preserving its semantics."""
    return " ".join(value.strip().lower().replace("_", " ").split())


def map_clinical_significance(value: str) -> int | None:
    """Map an unambiguous germline ClinVar assertion to the binary target."""
    normalized = normalize_label(value)
    terms = {
        " ".join(term.split()) for term in re.split(r"\s*[/;|]\s*", normalized) if term.strip()
    }
    if terms and terms <= POSITIVE_TERMS:
        return 1
    if terms and terms <= NEGATIVE_TERMS:
        return 0
    return None


def normalize_review_status(value: str) -> str:
    """Normalize review strings used by ClinVar tab-delimited releases."""
    return normalize_label(value)


def is_high_confidence_review(value: str) -> bool:
    """Return whether a review status belongs to Dataset B."""
    return normalize_review_status(value) in HIGH_CONFIDENCE_REVIEWS


def review_tier(value: str) -> int:
    """Convert review status into an ordering used only for deduplication."""
    return REVIEW_TIERS.get(normalize_review_status(value), 0)


def prepare_clinvar_dataset(
    source: Path,
    output_dir: Path,
    *,
    assembly: str = "GRCh38",
    chunk_size: int = 100_000,
    source_url: str | None = None,
    published_md5: str | None = None,
) -> ClinVarBuildResult:
    """Build all-label and high-confidence binary ClinVar datasets."""
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    if not source.is_file():
        raise FileNotFoundError(source)

    qc = ClinVarQC()
    curated_chunks: list[pd.DataFrame] = []
    for chunk in _read_chunks(source, chunk_size):
        curated = _curate_chunk(chunk, assembly, qc)
        if not curated.empty:
            curated_chunks.append(curated)

    if curated_chunks:
        eligible = pd.concat(curated_chunks, ignore_index=True)
    else:
        eligible = pd.DataFrame(columns=OUTPUT_COLUMNS)

    dataset_a = _deduplicate(eligible, qc)
    dataset_b = dataset_a.loc[dataset_a["high_confidence"]].reset_index(drop=True)
    _populate_output_counts(dataset_a, dataset_b, qc)

    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_a_path = output_dir / "clinvar.parquet"
    dataset_b_path = output_dir / "clinvar_high_confidence.parquet"
    qc_path = output_dir / "clinvar_qc.json"
    metadata_path = output_dir / "clinvar_source.json"

    dataset_a.to_parquet(dataset_a_path, index=False)
    dataset_b.to_parquet(dataset_b_path, index=False)
    _write_json(qc_path, asdict(qc))
    _write_json(
        metadata_path,
        {
            "source_file": source.name,
            "source_url": source_url,
            "assembly": assembly,
            "published_md5": published_md5,
            "actual_md5": file_digest(source, "md5"),
            "sha256": file_digest(source),
            "source_bytes": source.stat().st_size,
            "processed_at": datetime.now(UTC).isoformat(),
            "pipeline_version": __version__,
            "output_schema": OUTPUT_COLUMNS,
        },
    )
    return ClinVarBuildResult(
        dataset_a=dataset_a_path,
        dataset_b=dataset_b_path,
        qc_report=qc_path,
        source_metadata=metadata_path,
        qc=qc,
    )


def _read_chunks(source: Path, chunk_size: int) -> Iterator[pd.DataFrame]:
    try:
        reader = pd.read_csv(
            source,
            sep="\t",
            dtype="string",
            keep_default_na=False,
            compression="infer",
            chunksize=chunk_size,
            low_memory=False,
        )
        for chunk in reader:
            missing = REQUIRED_COLUMNS - set(chunk.columns)
            if missing:
                names = ", ".join(sorted(missing))
                raise ClinVarSchemaError(f"missing required ClinVar columns: {names}")
            yield chunk.loc[:, list(COLUMN_MAP)].rename(columns=COLUMN_MAP)
    except pd.errors.EmptyDataError as error:
        raise ClinVarSchemaError("ClinVar source is empty") from error


def _curate_chunk(chunk: pd.DataFrame, assembly: str, qc: ClinVarQC) -> pd.DataFrame:
    qc.source_rows += len(chunk)
    assembly_mask = chunk["assembly"].eq(assembly)
    qc.excluded_assembly += int((~assembly_mask).sum())
    selected = chunk.loc[assembly_mask].copy()
    qc.assembly_rows += len(selected)

    type_mask = selected["variant_type"].str.lower().isin(SUPPORTED_VARIANT_TYPES)
    qc.excluded_variant_type += int((~type_mask).sum())
    selected = selected.loc[type_mask].copy()

    selected["target"] = selected["clinical_significance"].map(map_clinical_significance)
    label_mask = selected["target"].notna()
    qc.excluded_label += int((~label_mask).sum())
    selected = selected.loc[label_mask].copy()

    valid_gene = ~selected["gene"].str.lower().isin({"", "-", "na"})
    qc.excluded_gene += int((~valid_gene).sum())
    selected = selected.loc[valid_gene].copy()

    selected["pos"] = pd.to_numeric(selected["pos"], errors="coerce")
    valid_coordinates = (
        selected["pos"].notna()
        & selected["pos"].gt(0)
        & ~selected["ref"].str.lower().isin({"", "-", "na"})
        & ~selected["alt"].str.lower().isin({"", "-", "na"})
        & selected["ref"].str.fullmatch(r"[ACGTNacgtn]+")
        & selected["alt"].str.fullmatch(r"[ACGTNacgtn]+")
        & ~selected["chrom"].str.lower().isin({"", "-", "na"})
    )
    qc.excluded_coordinates += int((~valid_coordinates).sum())
    selected = selected.loc[valid_coordinates].copy()

    selected["chrom"] = selected["chrom"].map(canonical_chromosome)
    chromosome_mask = selected["chrom"].isin(CANONICAL_CHROMOSOMES)
    qc.excluded_noncanonical_chromosome += int((~chromosome_mask).sum())
    selected = selected.loc[chromosome_mask].copy()

    records: list[dict[str, Any]] = []
    for row in selected.to_dict(orient="records"):
        pos, ref, alt = minimal_representation(
            int(row["pos"]), str(row["ref"]).upper(), str(row["alt"]).upper()
        )
        chrom = str(row["chrom"])
        records.append(
            {
                "variant_id": f"{chrom}:{pos}:{ref}:{alt}",
                "variation_id": _optional_text(str(row["variation_id"])),
                "allele_id": _optional_text(str(row["allele_id"])),
                "chrom": chrom,
                "pos": pos,
                "ref": ref,
                "alt": alt,
                "gene": _optional_text(str(row["gene"])),
                "variant_type": _optional_text(str(row["variant_type"])),
                "clinical_significance": str(row["clinical_significance"]),
                "review_status": str(row["review_status"]),
                "review_tier": review_tier(str(row["review_status"])),
                "number_submitters": _optional_int(str(row["number_submitters"])),
                "condition": _optional_text(str(row["condition"])),
                "last_evaluated": _iso_date(str(row["last_evaluated"])),
                "assembly": str(row["assembly"]),
                "target": int(row["target"]),
                "high_confidence": is_high_confidence_review(str(row["review_status"])),
            }
        )
    qc.eligible_rows += len(records)
    return pd.DataFrame.from_records(records, columns=OUTPUT_COLUMNS)


def _deduplicate(frame: pd.DataFrame, qc: ClinVarQC) -> pd.DataFrame:
    if frame.empty:
        return frame.astype({"target": "int8", "high_confidence": "bool"})

    target_counts = frame.groupby("variant_id", sort=False)["target"].nunique()
    conflict_ids = target_counts[target_counts > 1].index
    qc.conflicting_variants = len(conflict_ids)
    without_conflicts = frame.loc[~frame["variant_id"].isin(conflict_ids)].copy()

    before = len(without_conflicts)
    without_conflicts = without_conflicts.sort_values(
        ["variant_id", "review_tier", "last_evaluated"],
        ascending=[True, False, False],
        na_position="last",
    )
    result = without_conflicts.drop_duplicates("variant_id", keep="first").reset_index(drop=True)
    qc.duplicate_rows_removed = before - len(result)
    result["target"] = result["target"].astype("int8")
    result["review_tier"] = result["review_tier"].astype("int8")
    result["high_confidence"] = result["high_confidence"].astype("bool")
    return result.loc[:, OUTPUT_COLUMNS]


def _populate_output_counts(
    dataset_a: pd.DataFrame, dataset_b: pd.DataFrame, qc: ClinVarQC
) -> None:
    qc.dataset_a_rows = len(dataset_a)
    qc.dataset_a_pathogenic = int(dataset_a["target"].sum())
    qc.dataset_a_benign = qc.dataset_a_rows - qc.dataset_a_pathogenic
    qc.dataset_b_rows = len(dataset_b)
    qc.dataset_b_pathogenic = int(dataset_b["target"].sum())
    qc.dataset_b_benign = qc.dataset_b_rows - qc.dataset_b_pathogenic


def _optional_text(value: str) -> str | None:
    stripped = value.strip()
    return None if stripped.lower() in {"", "-", "na"} else stripped


def _optional_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def _iso_date(value: str) -> str | None:
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else parsed.date().isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
