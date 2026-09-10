# Variant ranking evaluation

Experiment date: 2026-09-10
Random seed: 42
Model: isotonic CatBoost
Validation strategy: gene-aware connected components

Variant prioritization is evaluated separately from binary classification. The
primary experiment creates 1,000 deterministic synthetic patient cohorts, each
containing one pathogenic and 49 benign variants sampled from untouched test
genes. The model ranks all 50 variants by score.

## Simulated-patient results

| Cohort | MRR | Pathogenic ranked first | Recall@5 | Recall@10 | NDCG@5 | NDCG@10 |
|---|---:|---:|---:|---:|---:|---:|
| Dataset A, all curated labels | 0.9213 | 87.5% | 98.0% | 99.1% | 0.9345 | 0.9382 |
| Dataset B, high confidence | **0.9715** | **95.4%** | **99.2%** | **99.8%** | **0.9760** | **0.9780** |

With one relevant variant per simulated patient, Recall@K is also the fraction
of cohorts whose pathogenic variant appears within the first K positions. MRR
captures how close the first pathogenic variant is to rank one.

## Global held-out ranking

The full Dataset A test partition contains 233,406 variants, including 42,506
pathogenic variants. Precision is 1.000 at K=10 and K=100, and 0.995 at K=1,000.
Dataset B contains 53,216 test variants, including 12,179 pathogenic variants;
precision is 1.000 through K=1,000.

Global top-K results demonstrate enrichment but are less representative of a
patient prioritization workflow because the held-out ClinVar cohort contains
many pathogenic variants. The mixed 50-variant simulation is therefore the
primary ranking evaluation.

## Reproduction

```bash
uv run variantrank evaluate-ranking \
  --dataset data/features/clinvar.features.parquet \
  --model artifacts/models/candidates/clinvar.features/all/annotated_vep_v1/gene/calibration-catboost/catboost_isotonic.joblib \
  --output artifacts/evaluation/ranking_catboost_all.json \
  --strategy gene \
  --cohort all \
  --patients 1000 \
  --variants-per-patient 50
```

The JSON artifact records dataset and model checksums, split settings, cohort
composition, global metrics, simulation parameters, and aggregated results.
These simulations estimate retrospective prioritization performance only; they
do not represent prospective patient cohorts or clinical validation.
