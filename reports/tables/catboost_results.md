# CatBoost candidate model results

Experiment date: 2026-09-10
Random seed: 42
Feature contract: `annotated_vep_v1`
Validation strategy: gene-aware connected components

CatBoost was trained with native categorical features, balanced class weights,
1,000 boosting iterations, depth 7, and learning rate 0.05. The comparison uses
the exact train, validation, and untouched test gene partitions used by the
baseline models.

## Held-out model comparison

| Dataset | Model | ROC-AUC | PR-AUC | MCC | F1 | Brier | Training time |
|---|---|---:|---:|---:|---:|---:|---:|
| A, all curated labels | Random Forest | 0.9923 | 0.9731 | **0.8770** | **0.8992** | 0.03037 | 41.3 s |
| A, all curated labels | CatBoost | **0.9929** | **0.9750** | 0.8769 | 0.8988 | **0.02890** | 223.5 s |
| B, high confidence | Random Forest | **0.9977** | **0.9931** | 0.9306 | 0.9462 | 0.01929 | 5.0 s |
| B, high confidence | CatBoost | 0.9976 | 0.9928 | **0.9356** | **0.9501** | **0.01815** | 44.8 s |

CatBoost improves ranking metrics on the broader Dataset A and improves
thresholded classification on high-confidence Dataset B. Random Forest retains
a marginal PR-AUC advantage of 0.0003 on Dataset B. This is a genuinely close
comparison rather than evidence that one algorithm dominates every metric.

## Calibration comparison

Both persisted estimators were frozen and calibrated on validation genes. The
table reports probability metrics on untouched test genes.

| Dataset | Model | Raw Brier | Platt Brier | Isotonic Brier | Isotonic log loss |
|---|---|---:|---:|---:|---:|
| A | Random Forest | 0.03037 | 0.02521 | 0.02301 | 0.07991 |
| A | CatBoost | **0.02890** | **0.02451** | **0.02217** | **0.07683** |
| B | Random Forest | 0.01929 | **0.01495** | 0.01383 | **0.05308** |
| B | CatBoost | **0.01815** | 0.01539 | **0.01306** | 0.05570 |

Isotonic CatBoost has the lowest Brier score in both cohorts. On Dataset B,
isotonic Random Forest has slightly better log loss, showing that aggregate
probability quality still depends on the scoring rule.

## CatBoost operating points

Thresholds are selected on validation predictions after isotonic calibration,
then applied once to the test partition.

| Dataset | Rule | Threshold | Validation precision | Validation recall | Test precision | Test recall | Test F1 | Test MCC |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| A | Maximum F1 | 0.4761 | 0.9241 | 0.9048 | 0.9281 | 0.9071 | 0.9175 | 0.8995 |
| A | Precision ≥ 0.90 | 0.3768 | 0.9038 | 0.9200 | 0.9074 | 0.9252 | 0.9162 | 0.8974 |
| A | Recall ≥ 0.90 | 0.4761 | 0.9241 | 0.9048 | 0.9281 | 0.9071 | 0.9175 | 0.8995 |
| B | Maximum F1 | 0.4727 | 0.9632 | 0.9246 | 0.9616 | 0.9645 | 0.9631 | 0.9521 |
| B | Precision ≥ 0.90 | 0.2717 | 0.9026 | 0.9573 | 0.9351 | 0.9782 | 0.9561 | 0.9431 |
| B | Recall ≥ 0.90 | 0.6493 | 0.9781 | 0.9059 | 0.9727 | 0.9549 | 0.9637 | 0.9531 |

## Model selection

The isotonic CatBoost pipeline is selected as the primary model candidate. It
offers the strongest combined result across ranking, probability quality, and
thresholded classification while preserving CatBoost's native treatment of
categorical biological annotations. The isotonic Random Forest remains a
versioned fallback and comparison model.

Selection is based solely on retrospective ClinVar-derived cohorts. Neither
model is established for clinical use or prospective diagnostic performance.

## Reproduction

```bash
uv run variantrank train \
  --dataset data/features/clinvar.features.parquet \
  --artifact-dir artifacts/models/candidates \
  --feature-set annotated \
  --cohort all \
  --strategy gene \
  --catboost

uv run variantrank calibrate \
  --dataset data/features/clinvar.features.parquet \
  --baseline-artifact-dir \
    artifacts/models/candidates/clinvar.features/all/annotated_vep_v1/gene \
  --strategy gene \
  --model-name catboost
```

Repeat both commands with `--cohort high-confidence` for Dataset B. Local model
artifacts are ignored by Git; configuration, metrics, provenance, and the exact
reproduction commands are documented here.
