# Model-ready feature dataset summary

Build date: 2026-09-10

The feature dataset joins the curated ClinVar labels to the pinned offline VEP
annotations with an exact one-to-one key contract. All 1,633,439 Dataset A
variants are represented once.

| Property | Value |
|---|---:|
| Rows | 1,633,439 |
| Columns | 40 |
| Metadata columns | 4 |
| Numeric features | 30 |
| Categorical features | 6 |
| Dataset B / high-confidence rows | 372,765 |
| Pathogenic rows | 297,354 |
| Benign rows | 1,336,085 |
| Label-to-annotation coverage | 100% |

## Functional profile

| VEP impact | Variants |
|---|---:|
| HIGH | 209,774 |
| MODERATE | 209,383 |
| LOW | 818,995 |
| MODIFIER | 395,287 |

| Missing-value measure | Variants |
|---|---:|
| Missing biotype | 62 |
| Missing protein position | 606,806 |
| Missing population frequency | 559,201 |
| Rare (`population_max_af <= 0.01`) | 895,203 |
| Common (`population_max_af > 0.01`) | 179,035 |

Missing frequency remains null rather than being interpreted as zero. The
training pipeline owns imputation, which keeps absent data distinct from an
observed zero frequency.

## Leakage audit

The materialized dataset contains only four non-feature columns:
`variant_id`, `gene`, `target`, and `high_confidence`. Gene is reserved for
grouped splitting, while target and the confidence flag are reserved for
dataset selection and evaluation. None are included in the model feature list.

Clinical significance text, review status, condition, submitter counts,
evaluation dates, and VEP co-located clinical fields are absent.

## Provenance

| Artifact | SHA-256 |
|---|---|
| Curated labels | `5ed661da6ed3d6826cb6be267a5bf270d16fd39491a89a9b8133c6dbb2c597ec` |
| Typed VEP annotations | `dff48c45ea6b903e369f2432fa7c938c18b357a0e507a571db80052399b07fd4` |
| Model-ready features | `9e77beb7f089023feed5f14f40b61c45d8d77e58b34ffae0e8b48284c8b44e9e` |

The local sidecar manifest also records the ordered feature lists, complete
output schema, row count, source paths, creation time, and feature-contract
version.
