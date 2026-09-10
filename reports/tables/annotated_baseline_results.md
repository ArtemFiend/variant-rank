# Annotated baseline results

Experiment date: 2026-09-10  
Random seed: 42  
Feature contract: `annotated_vep_v1`

The experiment compares Dummy, Logistic Regression, and Random Forest models
on the complete leakage-audited VEP feature dataset. Every metric below is
calculated on a held-out test partition that was not used for fitting.

## Dataset A — all curated labels

| Split | Model | ROC-AUC | PR-AUC | MCC | F1 | Brier |
|---|---|---:|---:|---:|---:|---:|
| Random | Dummy | 0.5000 | 0.1820 | 0.0000 | 0.0000 | 0.14890 |
| Random | Logistic Regression | 0.9881 | 0.9575 | 0.7958 | 0.8279 | 0.04547 |
| Random | Random Forest | 0.9922 | 0.9728 | 0.8753 | 0.8977 | 0.03130 |
| Gene-aware | Dummy | 0.5000 | 0.1821 | 0.0000 | 0.0000 | 0.14891 |
| Gene-aware | Logistic Regression | 0.9833 | 0.9417 | 0.7806 | 0.8184 | 0.04732 |
| Gene-aware | Random Forest | **0.9923** | **0.9731** | **0.8770** | **0.8992** | **0.03037** |

Dataset A contains 1,633,439 variants. The random test partition contains
245,016 variants; the gene-aware test partition contains 233,406 variants.

## Dataset B — high-confidence labels

| Split | Model | ROC-AUC | PR-AUC | MCC | F1 | Brier |
|---|---|---:|---:|---:|---:|---:|
| Random | Dummy | 0.5000 | 0.2283 | 0.0000 | 0.0000 | 0.17618 |
| Random | Logistic Regression | 0.9918 | 0.9746 | 0.8519 | 0.8839 | 0.03902 |
| Random | Random Forest | **0.9968** | **0.9911** | **0.9239** | **0.9413** | **0.02007** |
| Gene-aware | Dummy | 0.5000 | 0.2289 | 0.0000 | 0.0000 | 0.17648 |
| Gene-aware | Logistic Regression | 0.9715 | 0.9480 | 0.8090 | 0.8528 | 0.05235 |
| Gene-aware | Random Forest | **0.9977** | **0.9931** | **0.9306** | **0.9462** | **0.01929** |

Dataset B contains 372,765 variants. The random test partition contains 55,915
variants; the gene-aware test partition contains 53,216 variants.

## Validation interpretation

Gene-aware splitting assigns each gene to exactly one partition. Multi-gene
ClinVar values are expanded and connected into components, so indirect bridges
such as `GENE1;GENE2` cannot place either individual gene in another partition.
This prevents the model from benefiting from variants in the same gene across
training and test data. Gene identity is retained only as a grouping key and is
never passed to an estimator.

The annotated models materially outperform the annotation-free lower bound.
Population frequency and molecular consequence are expected to carry strong
signal for curated pathogenicity labels. These results remain retrospective
performance on ClinVar-derived cohorts; they do not establish clinical utility,
prospective performance, or calibrated diagnostic probabilities.

## Estimators

- Dummy: empirical class prior;
- Logistic Regression: balanced class weights and scaled/imputed numeric plus
  one-hot categorical features;
- Random Forest: 100 trees, depth 20, minimum leaf size 5, balanced bootstrap
  weights, and fixed seed 42.

All fitted pipelines, metrics, split summaries, feature lists, source checksum,
training durations, and package version are stored under the ignored local
`artifacts/models/annotated-baselines/` directory.

## Reproduction

```bash
uv run variantrank train \
  --dataset data/features/clinvar.features.parquet \
  --feature-set annotated \
  --strategy both

uv run variantrank train \
  --dataset data/features/clinvar.features.parquet \
  --feature-set annotated \
  --cohort high-confidence \
  --strategy both
```
