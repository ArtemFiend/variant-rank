# Random Forest probability calibration

Experiment date: 2026-09-10
Random seed: 42
Feature contract: `annotated_vep_v1`
Validation strategy: gene-aware connected components

The fitted Random Forest is frozen before calibration. Platt scaling and
isotonic regression are fitted only on the validation partition; all reported
comparison metrics are then calculated on the untouched test partition.

## Probability quality

| Dataset | Method | ROC-AUC | PR-AUC | Brier | Log loss |
|---|---|---:|---:|---:|---:|
| A, all curated labels | Raw | 0.9923 | 0.9731 | 0.03037 | 0.11011 |
| A, all curated labels | Platt | 0.9923 | 0.9731 | 0.02521 | 0.09210 |
| A, all curated labels | Isotonic | 0.9923 | 0.9709 | **0.02301** | **0.07991** |
| B, high confidence | Raw | 0.9977 | 0.9931 | 0.01929 | 0.06893 |
| B, high confidence | Platt | 0.9977 | 0.9931 | 0.01495 | 0.05811 |
| B, high confidence | Isotonic | 0.9977 | 0.9926 | **0.01383** | **0.05308** |

Isotonic calibration gives the lowest Brier score and log loss in both
cohorts. Its small PR-AUC change is caused by tied values introduced by the
piecewise-constant mapping; calibration is intended to improve probability
quality, not ranking discrimination.

## Validation-selected operating points

The following thresholds are selected without inspecting test labels. Precision
and recall constraints refer to the validation partition. Test columns show how
those fixed thresholds transfer to held-out genes.

| Dataset | Rule | Threshold | Validation precision | Validation recall | Test precision | Test recall | Test F1 | Test MCC |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| A | Maximum F1 | 0.4590 | 0.9208 | 0.9009 | 0.9216 | 0.9057 | 0.9136 | 0.8946 |
| A | Precision ≥ 0.90 | 0.3913 | 0.9012 | 0.9166 | 0.9000 | 0.9232 | 0.9115 | 0.8915 |
| A | Recall ≥ 0.90 | 0.4590 | 0.9208 | 0.9009 | 0.9216 | 0.9057 | 0.9136 | 0.8946 |
| B | Maximum F1 | 0.4709 | 0.9584 | 0.9248 | 0.9598 | 0.9638 | 0.9618 | 0.9505 |
| B | Precision ≥ 0.90 | 0.3568 | 0.9361 | 0.9405 | 0.9499 | 0.9697 | 0.9597 | 0.9477 |
| B | Recall ≥ 0.90 | 0.7458 | 0.9807 | 0.9007 | 0.9700 | 0.9516 | 0.9607 | 0.9493 |

Dataset A uses 233,313 validation and 233,406 test variants. Dataset B uses
53,240 validation and 53,216 test variants. Multi-gene labels remain within one
connected component, so no individual gene crosses partitions.

## Interpretation

The selected default candidate is the isotonic Random Forest with the
maximum-F1 operating point. Both calibration methods and all operating points
remain available as versioned artifacts so an inference consumer can choose a
policy appropriate to its intended research workflow.

These values describe retrospective performance on ClinVar-derived cohorts.
They are not clinical risk estimates, diagnostic probabilities, or evidence of
prospective utility.

## Reproduction

```bash
uv run variantrank calibrate \
  --dataset data/features/clinvar.features.parquet \
  --baseline-artifact-dir \
    artifacts/models/annotated-baselines/clinvar.features/all/annotated_vep_v1/gene \
  --strategy gene

uv run variantrank calibrate \
  --dataset data/features/clinvar.features.parquet \
  --baseline-artifact-dir \
    artifacts/models/annotated-baselines/clinvar.features/high_confidence/annotated_vep_v1/gene \
  --strategy gene \
  --cohort high-confidence
```

Each run writes calibrated pipelines, held-out metrics, validation-selected
operating points, source model paths, dataset checksum, split parameters, and
timings to the source model's ignored `calibration/` directory.
