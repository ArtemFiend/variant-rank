# Annotation-free baseline results

Evaluation date: 2026-09-08
Genome assembly: GRCh38
Random seed: 42
Feature set: `basic_variant_v1`

## Scope

This experiment establishes a reproducible lower bound before functional,
population, conservation, or external pathogenicity annotations are introduced.
The model receives only properties derived from the normalized variant itself:
chromosome, variant type, substitution class, allele lengths, length change,
transition/transversion indicators, and allele GC fractions. Gene identity and
ClinVar assertion fields are excluded from the feature matrix.

Two models are evaluated:

- `DummyClassifier(strategy="prior")`, which represents the class-prevalence
  baseline;
- class-weighted Logistic Regression with median imputation, standard scaling,
  and one-hot encoding inside a fitted preprocessing pipeline.

All values below are calculated on held-out test partitions. The decision
threshold is fixed at 0.5; no test-set threshold optimization is performed.

## Test metrics

| Dataset | Split | Model | ROC-AUC | PR-AUC | MCC | F1 | Precision | Recall | Balanced accuracy | Brier | Log loss |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | Random | Dummy | 0.5000 | 0.1820 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.5000 | 0.1489 | 0.4744 |
| A | Random | Logistic Regression | 0.7522 | 0.5342 | 0.3484 | 0.4796 | 0.4182 | 0.5621 | 0.6941 | 0.1798 | 0.5519 |
| A | Gene-aware | Dummy | 0.5000 | 0.1820 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.5000 | 0.1489 | 0.4743 |
| A | Gene-aware | Logistic Regression | 0.7507 | 0.5352 | 0.3515 | 0.4813 | 0.4244 | 0.5560 | 0.6941 | 0.1770 | 0.5445 |
| B | Random | Dummy | 0.5000 | 0.2281 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.5000 | 0.1761 | 0.5370 |
| B | Random | Logistic Regression | 0.7203 | 0.5420 | 0.3005 | 0.4717 | 0.4362 | 0.5136 | 0.6587 | 0.1939 | 0.5776 |
| B | Gene-aware | Dummy | 0.5000 | 0.2281 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.5000 | 0.1761 | 0.5370 |
| B | Gene-aware | Logistic Regression | 0.7005 | 0.5295 | 0.2861 | 0.4547 | 0.4386 | 0.4720 | 0.6467 | 0.1935 | 0.5753 |

## Split audit

| Dataset | Split | Train rows | Validation rows | Test rows | Test pathogenic rate | Test genes |
|---|---|---:|---:|---:|---:|---:|
| A | Random | 1,143,783 | 245,096 | 245,097 | 18.20% | 11,594 |
| A | Gene-aware | 1,167,086 | 233,482 | 233,408 | 18.20% | 2,573 |
| B | Random | 261,151 | 55,961 | 55,961 | 22.81% | 5,872 |
| B | Gene-aware | 266,484 | 53,317 | 53,272 | 22.81% | 1,393 |

Random partitions are stratified by the binary target. Gene-aware partitions
use stratified group folds: each gene belongs to exactly one of train,
validation, or test, while pathogenic prevalence remains closely matched.

## Interpretation

- The variant-only Logistic Regression substantially exceeds the prevalence
  baseline in every protocol, establishing a useful annotation-free lower bound.
- Dataset A changes little between random and gene-aware evaluation
  (ROC-AUC 0.7522 vs. 0.7507). This primitive feature set does not include gene
  identity, so a large gene-leakage penalty is neither observed nor claimed.
- Dataset B shows a clearer unseen-gene penalty: ROC-AUC falls by 0.0198,
  PR-AUC by 0.0126, and MCC by 0.0144 under gene-aware evaluation.
- PR-AUC must be read alongside prevalence. Dataset B has a higher pathogenic
  fraction (22.81% vs. 18.20%), so its raw PR-AUC is not directly comparable to
  Dataset A without that context.
- The class-weighted model is optimized for discrimination, not calibration.
  Its raw outputs must not be interpreted as clinical probabilities; probability
  calibration and calibration curves belong to the next modeling stage.

## Reproduction

After building the ClinVar datasets, run:

```bash
uv run variantrank train --strategy both
uv run variantrank train \
  --dataset data/processed/clinvar_high_confidence.parquet \
  --artifact-dir artifacts/models/baselines/clinvar_high_confidence \
  --strategy both
```

Each run writes the fitted pipelines, metrics, dataset checksum, feature schema,
split statistics, seed, and training duration beneath `artifacts/models/`.
Model binaries and generated datasets remain untracked; this report and the data
build summary provide the versioned experimental record.
