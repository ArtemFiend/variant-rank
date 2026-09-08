# ClinVar training data contract

This document defines how VariantRank turns the NCBI ClinVar
`variant_summary.txt.gz` release into binary training labels. The rules are part
of the model definition: changing them requires a new dataset version and a new
evaluation run.

## Source and provenance

The default source is the official NCBI ClinVar tab-delimited release:

```text
https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz
```

VariantRank verifies the publisher-provided MD5 checksum before processing and
records a SHA-256 digest, byte size, genome assembly, processing timestamp,
pipeline version, and output schema in `clinvar_source.json`. The URL points to
the current ClinVar release; the recorded checksum identifies the exact source
snapshot used by an experiment.

## Included labels

Only unambiguous germline significance groups enter the binary task:

| Target | Accepted ClinVar terms |
|---:|---|
| `1` | `Pathogenic`, `Likely pathogenic`, `Pathogenic/Likely pathogenic` |
| `0` | `Benign`, `Likely benign`, `Benign/Likely benign` |

Composite assertions are accepted only when every component belongs to the same
target class. For example, `Pathogenic; risk factor` is excluded.

The following categories are excluded, including their spelling variants:

- uncertain significance;
- conflicting classifications or interpretations;
- drug response, risk factor, association, or protective;
- not provided and other assertions outside the binary task.

The original `ClinicalSignificance` value remains in the curated dataset. It is
label metadata and must never be used as a model feature.

## Genomic scope

The default build retains GRCh38 rows with:

- a supported small-variant type: single nucleotide variant, deletion,
  insertion, or indel;
- a positive 1-based `PositionVCF`;
- explicit DNA `ReferenceAlleleVCF` and `AlternateAlleleVCF` values;
- a canonical chromosome (`1`–`22`, `X`, `Y`, or `MT`) and gene symbol;
- an accepted binary clinical significance.

Chromosome names are stored without the `chr` prefix, and mitochondrial aliases
are canonicalized to `MT`. Common REF/ALT prefixes and suffixes are trimmed to a
minimal representation. Reference-aware left alignment is a separate pipeline
step and will use the matching genome FASTA through `bcftools norm`.

## Duplicate and conflict policy

The normalized key is:

```text
chrom:pos:ref:alt
```

If the same key maps to both target classes, all rows for that key are removed.
If duplicate rows agree on the target, VariantRank keeps the row with the
strongest review status and then the most recent evaluation date.

Review tiers used for this deterministic choice are:

| Tier | Review status |
|---:|---|
| 4 | practice guideline |
| 3 | reviewed by expert panel |
| 2 | criteria provided, multiple submitters, no conflicts |
| 1 | criteria provided, single submitter |
| 0 | no assertion criteria / other status |

## Output datasets

`clinvar.parquet` contains every curated unambiguous variant (Dataset A).

`clinvar_high_confidence.parquet` contains only variants whose selected record
has tier 2–4 review status (Dataset B).

Both datasets use the same columns:

```text
variant_id, variation_id, allele_id, chrom, pos, ref, alt, gene,
variant_type, clinical_significance, review_status, review_tier,
number_submitters, condition, last_evaluated, assembly, target,
high_confidence
```

`clinvar_qc.json` records every filtering stage, conflict count, duplicate count,
dataset size, and class distribution. These counters are required inputs to the
EDA and model cards.

## Leakage boundary

The following columns are retained for provenance, stratified error analysis,
and confidence filtering but are excluded from model features:

```text
clinical_significance
review_status
review_tier
target
high_confidence
condition
variation_id
allele_id
```

Feature selection is enforced later by the versioned feature schema rather than
by dropping this audit metadata from the curated dataset.
