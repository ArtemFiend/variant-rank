# Model-ready feature contract

VariantRank materializes a versioned, leakage-safe dataset between annotation
and model training. This boundary makes the exact training matrix independently
auditable and prevents label metadata from entering estimators accidentally.

## Build

```bash
uv run variantrank build-features \
  --labels data/processed/clinvar.parquet \
  --annotations data/annotated/clinvar.vep.parquet \
  --output-path data/features/clinvar.features.parquet
```

The builder requires unique variant keys and an exact one-to-one match between
the curated labels and VEP annotations. Missing or unexpected keys fail the
build before the destination is replaced. Successful output is written
atomically and reused only while both source checksums and the output checksum
match its sidecar manifest.

## Non-feature columns

| Column | Purpose |
|---|---|
| `variant_id` | Stable join and inference identifier |
| `gene` | Grouping key for gene-aware validation; never a model feature |
| `target` | Binary training target; never a model feature |
| `high_confidence` | Dataset B selection flag; never a model feature |

ClinVar clinical significance, review status, submitter count, condition, and
evaluation date are intentionally absent from the model-ready dataset.

## Feature families

- normalized allele geometry and sequence composition;
- SNV/indel and substitution indicators;
- selected VEP consequence, impact, and biotype;
- protein position and transcript-selection indicators;
- overall and population allele frequencies;
- explicit consequence flags for missense, synonymous, stop, frameshift,
  splice, and start-loss effects.

Missing population frequency remains null and is imputed inside the fitted
model pipeline. It is never interpreted as zero frequency.

## Provenance

The adjacent `*.manifest.json` records the source paths and SHA-256 checksums,
feature contract version, ordered numeric and categorical feature lists, output
schema, row count, creation time, and output checksum.
