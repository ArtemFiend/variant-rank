# Ranked inference contract

VariantRank inference accepts a normalized GRCh38 VCF, a typed VEP annotation
Parquet with exactly the same alternate alleles, and a persisted VariantRank
pipeline. It returns one score per alternate allele, sorted from highest to
lowest predicted pathogenicity.

## Input invariants

- VCF records must pass the VariantRank parser and normalization rules.
- Multiallelic records are decomposed into one inference row per ALT allele.
- Annotation keys use the canonical `chrom:pos:ref:alt` representation.
- Annotation keys must be unique and exactly match the VCF allele set.
- The model must implement `predict_proba` for the `annotated_vep_v1` feature
  contract.

Inference fails closed when annotations are missing, duplicated, or unexpected.
This prevents a partial annotation response from producing a deceptively
complete ranked result.

## Output schema

| Column | Type | Meaning |
|---|---|---|
| `rank` | integer | One-based position after descending score sort |
| `variant_id` | string | Canonical variant key |
| `chrom` | string | Canonical chromosome |
| `pos` | integer | One-based GRCh38 position |
| `ref` | string | Reference allele |
| `alt` | string | Alternate allele |
| `gene` | nullable string | VEP-selected gene symbol |
| `consequence` | string | VEP-selected consequence term(s) |
| `score` | float | Model probability-like score |
| `prediction` | string | `pathogenic` or `benign` at the supplied threshold |

Ties retain input VCF order, making output deterministic. CSV and JSON contain
the same fields and ordering.

## Feature parity

Training and inference call the same `build_model_features` implementation and
the same ordered numerical/categorical contract. Basic allele features are rebuilt
from VCF alleles; functional and population features are rebuilt from the typed
VEP annotation schema. Label, review status, condition, and gene identity are
not passed to the estimator.

## Scope

Scores are intended for retrospective research and engineering evaluation.
They are not ACMG/AMP classifications, diagnostic conclusions, or clinical
recommendations.
