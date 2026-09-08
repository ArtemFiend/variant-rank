# VariantRank
## End-to-End ML System for Genetic Variant Pathogenicity Prioritization

**Тип проекта:** Bioinformatics / Genomics / Machine Learning / ML Engineering  
**Формат:** portfolio-grade open-source project  
**Основная задача:** ранжирование генетических вариантов по вероятности клинической значимости  
**Целевой результат:** воспроизводимая система `VCF → annotation → features → ML → ranked variants → report/API`  
**Ориентировочное время реализации с Codex:** 7–10 дней для основной версии, 2–4 недели для расширенной  
**Требования к железу:** CPU-first; GPU не требуется  
**Рекомендуемая RAM:** 16–32 GB  
**Ориентировочный диск:** 20–50 GB  

---

# 1. Идея проекта

VariantRank — система для автоматизированной приоритизации генетических вариантов.

На вход система получает VCF-файл с генетическими вариантами. Для каждого варианта выполняется:

1. parsing и нормализация;
2. QC;
3. функциональная аннотация;
4. добавление популяционных и геномных признаков;
5. feature engineering;
6. оценка ML-моделью;
7. расчёт вероятности патогенности;
8. ранжирование вариантов;
9. формирование JSON/CSV/HTML-отчёта.

Пример результата:

```text
Variant              Gene   Consequence       AF        Score   Prediction
17:7674220:C>T       TP53   missense_variant  0.00001   0.947   Pathogenic
13:32340301:C>T      BRCA2  stop_gained       0.00003   0.916   Pathogenic
2:215632123:G>A      BARD1  missense_variant  0.00210   0.731   Uncertain
...
```

Проект должен выглядеть не как учебный notebook, а как полноценная воспроизводимая ML/bioinformatics система.

---

# 2. Цель проекта

Разработать production-style pipeline для приоритизации генетических вариантов с использованием:

- VCF;
- ClinVar;
- Ensembl VEP или эквивалентных функциональных аннотаций;
- популяционных частот;
- классического ML;
- корректной биоинформатической валидации;
- explainability;
- CLI;
- REST API;
- Docker;
- автоматизированных тестов;
- CI.

---

# 3. Задачи проекта

## 3.1. Bioinformatics

Необходимо продемонстрировать работу с:

- VCF;
- genomic coordinates;
- REF/ALT;
- SNV/indel;
- variant normalization;
- consequences;
- gene/transcript annotations;
- allele frequency;
- ClinVar labels;
- variant-level filtering;
- genomic annotation pipelines.

## 3.2. Data Science

Необходимо реализовать:

- EDA;
- обработку пропусков;
- feature engineering;
- categorical encoding;
- imbalance handling;
- baseline models;
- gradient boosting;
- probability calibration;
- threshold selection;
- feature importance;
- SHAP;
- error analysis.

## 3.3. Machine Learning Engineering

Необходимо реализовать:

- конфигурируемый pipeline;
- train/inference separation;
- сохранение моделей;
- model metadata;
- CLI;
- REST API;
- Docker;
- logging;
- tests;
- CI;
- reproducibility.

---

# 4. Что проект НЕ должен делать

На основной стадии не требуется:

- анализ полного WGS пациента;
- обучение нейросети;
- использование больших LLM;
- скачивание полного gnomAD;
- реализация clinical-grade ACMG/AMP классификатора;
- постановка медицинского диагноза;
- использование проекта для реального медицинского решения.

Проект является исследовательским и портфолио-инструментом.

---

# 5. Формулировка ML-задачи

Основная задача:

```text
Binary classification:
Pathogenic / Likely pathogenic
vs
Benign / Likely benign
```

Целевой output:

```text
P(pathogenic | variant features)
```

После этого варианты сортируются по вероятности:

```text
score_1 >= score_2 >= ... >= score_n
```

---

# 6. Возможная расширенная постановка

После основной версии можно добавить:

```text
Benign
Likely benign
VUS
Likely pathogenic
Pathogenic
```

Однако multiclass-версия должна быть stretch goal, а не основной задачей.

Причина: ClinVar содержит значительное количество неоднозначных и конфликтующих интерпретаций.

---

# 7. Источники данных

## 7.1. ClinVar

Основной источник labels.

Использовать варианты с понятной клинической интерпретацией.

### Positive class

```text
Pathogenic
Likely pathogenic
```

### Negative class

```text
Benign
Likely benign
```

### Исключить из основной обучающей выборки

```text
Uncertain significance
Conflicting interpretations
not provided
drug response
risk factor
association
protective
```

---

# 8. Требования к labels

Необходимо хранить как минимум:

```text
variant_id
chrom
pos
ref
alt
gene
clinical_significance
review_status
condition
last_evaluated
```

Рекомендуется сохранить исходную clinical significance отдельно от бинарного target.

Пример:

```text
clinical_significance = "Likely pathogenic"
target = 1
```

---

# 9. Контроль качества ClinVar

Необходимо исследовать `review_status`.

Например:

- criteria provided, single submitter;
- criteria provided, multiple submitters;
- reviewed by expert panel;
- practice guideline.

Рекомендуется реализовать два датасета:

### Dataset A

Все однозначные pathogenic/benign варианты.

### Dataset B — high confidence

Только варианты с более высоким уровнем review confidence.

После этого сравнить качество модели.

---

# 10. Функциональная аннотация

Основной вариант:

**Ensembl Variant Effect Predictor (VEP).**

Для каждого варианта желательно получить:

```text
gene
transcript
consequence
impact
biotype
exon
intron
protein_position
amino_acids
codons
canonical
mane_select
```

---

# 11. Популяционные признаки

Минимальный набор:

```text
allele_frequency
population_max_af
rare_variant_flag
```

Если доступны:

```text
AFR_AF
AMR_AF
EAS_AF
NFE_AF
SAS_AF
```

Полный gnomAD скачивать не требуется.

Допускаются:

- VEP annotations;
- подготовленные compact resources;
- subset;
- локальный cache только для нужных регионов.

---

# 12. Дополнительные признаки

По возможности:

## 12.1. Sequence / variant features

```text
variant_type
ref_length
alt_length
is_snv
is_indel
transition_transversion
gc_context
```

## 12.2. Consequence features

```text
is_missense
is_synonymous
is_stop_gained
is_frameshift
is_splice
is_start_lost
is_stop_lost
```

## 12.3. Protein features

```text
protein_position
amino_acid_change
```

## 12.4. Gene-level features

```text
gene
gene_constraint
lof_intolerance
```

## 12.5. Conservation/deleteriousness

Если доступны:

```text
CADD
SIFT
PolyPhen
REVEL
phyloP
phastCons
```

---

# 13. Важное ограничение по leakage

Нельзя строить модель, которая фактически воспроизводит ClinVar label через признаки, являющиеся прямым производным от ClinVar.

Запрещено использовать как feature:

```text
ClinVar clinical significance
ClinVar pathogenicity assertion
любые прямые label-derived признаки
```

Также необходимо внимательно относиться к pathogenicity predictors, которые могли обучаться на ClinVar.

Если используются CADD/REVEL/PolyPhen и аналогичные оценки, это должно быть явно описано как ограничение.

---

# 14. Data Pipeline

Общая схема:

```text
ClinVar / VCF
     ↓
download
     ↓
normalize
     ↓
filter
     ↓
annotate
     ↓
feature extraction
     ↓
dataset validation
     ↓
train/validation/test split
     ↓
model training
     ↓
evaluation
     ↓
model artifact
```

---

# 15. Inference Pipeline

```text
patient.vcf
    ↓
VCF parser
    ↓
normalization
    ↓
annotation
    ↓
feature builder
    ↓
trained model
    ↓
probability calibration
    ↓
variant ranking
    ↓
CSV / JSON / HTML
```

---

# 16. Архитектура проекта

```text
                    ┌──────────────────┐
                    │      VCF         │
                    └────────┬─────────┘
                             │
                             ↓
                    ┌──────────────────┐
                    │ Variant Parser   │
                    └────────┬─────────┘
                             │
                             ↓
                    ┌──────────────────┐
                    │ Normalization    │
                    └────────┬─────────┘
                             │
                             ↓
                    ┌──────────────────┐
                    │ Annotation Layer │
                    │ VEP / population │
                    └────────┬─────────┘
                             │
                             ↓
                    ┌──────────────────┐
                    │ Feature Builder  │
                    └────────┬─────────┘
                             │
                             ↓
                    ┌──────────────────┐
                    │   ML Model       │
                    └────────┬─────────┘
                             │
                             ↓
                    ┌──────────────────┐
                    │ Calibration      │
                    └────────┬─────────┘
                             │
                             ↓
                    ┌──────────────────┐
                    │ Variant Ranking  │
                    └────────┬─────────┘
                             │
                ┌────────────┼────────────┐
                ↓            ↓            ↓
               CSV          JSON         HTML
```

---

# 17. Предлагаемый стек

## Язык

```text
Python 3.12+
```

## Data

```text
pandas
numpy
pyarrow
polars — опционально
```

## Bioinformatics

```text
cyvcf2 или pysam
bcftools
Ensembl VEP
BioPython — опционально
```

## ML

```text
scikit-learn
CatBoost
LightGBM или XGBoost
Optuna
```

## Explainability

```text
SHAP
```

## Validation

```text
scikit-learn
```

## API

```text
FastAPI
Pydantic
Uvicorn
```

## CLI

```text
Typer
```

## Configuration

```text
YAML
pydantic-settings
```

## Testing

```text
pytest
pytest-cov
```

## Quality

```text
ruff
mypy
pre-commit
```

## Infrastructure

```text
Docker
Docker Compose
GitHub Actions
```

## Experiment tracking

Минимум:

```text
JSON/YAML + CSV metrics
```

Расширенно:

```text
MLflow
```

---

# 18. Почему CatBoost должен быть основной моделью

Для первого production-grade baseline CatBoost подходит хорошо, потому что:

- работает с категориальными признаками;
- устойчив на табличных данных;
- не требует GPU;
- хорошо работает на средних датасетах;
- поддерживает probability prediction;
- легко интегрируется с SHAP;
- относительно простой deployment.

Но обязательно сравнить с baseline-моделями.

---

# 19. Набор моделей

## Baseline 0

```text
DummyClassifier
```

## Baseline 1

```text
Logistic Regression
```

## Baseline 2

```text
Random Forest
```

## Основные

```text
CatBoost
LightGBM
```

Опционально:

```text
XGBoost
```

---

# 20. Feature Sets

Необходимо сделать несколько экспериментов.

## Feature Set A

Только простые variant features.

```text
variant_type
consequence
impact
allele_frequency
```

## Feature Set B

A +

```text
protein-related features
gene-level features
population features
```

## Feature Set C

B +

```text
conservation / pathogenicity scores
```

Это позволит оценить вклад дополнительных биологических источников.

---

# 21. EDA

Обязательные исследования:

## Labels

- количество pathogenic;
- количество benign;
- class imbalance.

## Variant type

- SNV;
- insertion;
- deletion.

## Consequences

- missense;
- synonymous;
- stop_gained;
- frameshift;
- splice.

## Population frequency

Распределения AF отдельно для классов.

## Genes

- число уникальных genes;
- число вариантов на gene;
- genes с большим количеством variants.

## Chromosomes

Распределение вариантов по chromosome.

## Missing values

Доля пропусков по каждому признаку.

---

# 22. Визуализации

Минимальный набор:

```text
class distribution
variant type distribution
consequence distribution
AF distributions
missingness
feature importance
SHAP summary
ROC curve
Precision-Recall curve
calibration curve
confusion matrix
```

---

# 23. Validation Strategy

Это одна из главных частей проекта.

Необходимо показать, что случайный split может переоценивать качество.

---

# 24. Split 1 — Random Stratified Split

Использовать как baseline.

```text
train 70%
validation 15%
test 15%
```

С сохранением class ratio.

---

# 25. Split 2 — Gene-aware Split

Варианты одного gene не должны одновременно попадать в train и test.

Пример:

```text
TRAIN:
TP53
BRCA1
APC

TEST:
BRCA2
MLH1
MSH2
```

Это позволяет оценить generalization на новые genes.

---

# 26. Split 3 — Chromosome Holdout

Stretch goal.

Например:

```text
train: chr1-20
validation: chr21
test: chr22
```

Или несколько chromosome folds.

---

# 27. Cross-validation

Рекомендуется:

```text
StratifiedGroupKFold
```

где:

```text
group = gene
```

---

# 28. Метрики

Основные:

```text
ROC-AUC
PR-AUC
F1
Precision
Recall
MCC
```

Дополнительно:

```text
Balanced Accuracy
Brier Score
Log Loss
```

---

# 29. Почему PR-AUC важен

Если классы несбалансированы, ROC-AUC может выглядеть слишком оптимистично.

Поэтому PR-AUC должен быть одной из ключевых метрик.

---

# 30. Probability Calibration

Поскольку система выдаёт вероятность патогенности, необходимо проверить calibration.

Сравнить:

```text
raw probabilities
vs
Platt scaling
vs
Isotonic calibration
```

Построить:

```text
calibration curve
```

---

# 31. Threshold Selection

Не использовать автоматически:

```text
threshold = 0.5
```

Исследовать:

```text
threshold maximizing F1
threshold for Recall >= X
threshold for Precision >= X
```

Для portfolio-версии можно показать несколько operating points.

---

# 32. Ranking Evaluation

Так как конечная задача — variant prioritization, необходимо оценить ranking.

Дополнительно к classification metrics:

```text
Precision@K
Recall@K
MRR
NDCG@K
```

Можно симулировать "пациентов":

- объединять небольшое количество benign variants;
- добавлять 1–N pathogenic variants;
- проверять, насколько высоко pathogenic вариант поднимается в ranking.

---

# 33. Error Analysis

Обязательная часть.

Отдельно изучить:

```text
False Positives
False Negatives
```

По:

- consequence;
- gene;
- allele frequency;
- variant type;
- review status;
- chromosome.

Пример вопроса:

```text
Почему модель ошибается на missense-вариантах чаще,
чем на stop_gained?
```

---

# 34. Explainability

Использовать:

```text
SHAP
```

Необходимо показать:

## Global

```text
SHAP summary plot
```

## Individual variant

Например:

```text
Prediction = 0.94 pathogenic

positive:
+ stop_gained
+ extremely low AF
+ high conservation

negative:
- ...
```

---

# 35. CLI

После установки:

```bash
variantrank --help
```

Предлагаемые команды:

```bash
variantrank prepare-data
variantrank train
variantrank evaluate
variantrank predict patient.vcf
variantrank report patient.vcf
```

---

# 36. Пример CLI

```bash
variantrank predict examples/example.vcf \
    --model artifacts/model.cbm \
    --output results/variants.csv
```

---

# 37. REST API

Минимальные endpoints:

```text
GET /health
GET /model/info
POST /predict
```

---

# 38. GET /health

Response:

```json
{
  "status": "ok"
}
```

---

# 39. GET /model/info

Пример:

```json
{
  "model": "CatBoostClassifier",
  "version": "1.0.0",
  "features": 42,
  "training_date": "2026-09-XX"
}
```

---

# 40. POST /predict

Input:

```text
multipart/form-data
VCF file
```

Output:

```json
{
  "variants": [
    {
      "chrom": "17",
      "pos": 7674220,
      "ref": "C",
      "alt": "T",
      "gene": "TP53",
      "score": 0.947,
      "prediction": "pathogenic"
    }
  ]
}
```

---

# 41. Структура репозитория

```text
variantrank/
│
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .python-version
├── .gitignore
├── .pre-commit-config.yaml
├── Dockerfile
├── docker-compose.yml
├── Makefile
│
├── configs/
│   ├── data.yaml
│   ├── features.yaml
│   ├── train.yaml
│   └── inference.yaml
│
├── data/
│   ├── raw/
│   ├── interim/
│   ├── processed/
│   └── external/
│
├── artifacts/
│   ├── models/
│   ├── metrics/
│   └── encoders/
│
├── reports/
│   ├── figures/
│   ├── tables/
│   └── examples/
│
├── notebooks/
│   ├── 01_eda.ipynb
│   ├── 02_features.ipynb
│   └── 03_error_analysis.ipynb
│
├── src/
│   └── variantrank/
│       ├── __init__.py
│       ├── cli.py
│       │
│       ├── data/
│       │   ├── download.py
│       │   ├── clinvar.py
│       │   ├── vcf.py
│       │   └── validation.py
│       │
│       ├── annotation/
│       │   ├── vep.py
│       │   └── population.py
│       │
│       ├── features/
│       │   ├── builder.py
│       │   ├── variant.py
│       │   ├── consequence.py
│       │   └── population.py
│       │
│       ├── models/
│       │   ├── baselines.py
│       │   ├── catboost.py
│       │   ├── calibration.py
│       │   └── registry.py
│       │
│       ├── evaluation/
│       │   ├── metrics.py
│       │   ├── splits.py
│       │   ├── ranking.py
│       │   └── plots.py
│       │
│       ├── explainability/
│       │   └── shap.py
│       │
│       ├── inference/
│       │   ├── predictor.py
│       │   └── ranking.py
│       │
│       ├── reports/
│       │   └── html.py
│       │
│       └── api/
│           ├── app.py
│           ├── schemas.py
│           └── routes.py
│
├── scripts/
│   ├── prepare_data.py
│   ├── annotate_variants.py
│   ├── train.py
│   └── evaluate.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
└── .github/
    └── workflows/
        ├── ci.yml
        └── docker.yml
```

---

# 42. Package Management

Предпочтительно использовать:

```text
uv
```

Пример:

```bash
uv init
uv add pandas numpy scikit-learn catboost lightgbm shap
uv add fastapi uvicorn pydantic typer
uv add cyvcf2
uv add --dev pytest pytest-cov ruff mypy pre-commit
```

---

# 43. Configuration

Не хардкодить параметры.

Например:

```yaml
model:
  type: catboost
  iterations: 1000
  depth: 7
  learning_rate: 0.05

validation:
  strategy: gene_group
  folds: 5

features:
  use_population: true
  use_consequence: true
```

---

# 44. Reproducibility

Обязательно фиксировать:

```text
random_seed
package versions
dataset version
feature schema
model version
git commit
```

---

# 45. Logging

Использовать стандартный Python `logging`.

Логировать:

```text
dataset size
class distribution
missing values
selected features
split sizes
training time
metrics
model path
```

Не использовать `print()` как основной механизм логирования.

---

# 46. Model Artifact

Сохранять:

```text
model
feature schema
categorical columns
threshold
calibrator
metadata
metrics
```

В идеале:

```text
artifacts/models/v1/
├── model.cbm
├── metadata.json
├── feature_schema.json
├── threshold.json
└── metrics.json
```

---

# 47. Dataset Versioning

Минимальная версия:

```text
raw file checksum
source URL
download date
source version
```

Расширенно:

```text
DVC
```

Но DVC не является обязательным для MVP.

---

# 48. Tests

## Unit tests

Необходимо покрыть:

```text
VCF parsing
variant normalization
feature builder
label mapping
metrics
ranking
model loading
```

## Integration tests

```text
small VCF
 ↓
pipeline
 ↓
predictions
```

## API tests

```text
GET /health → 200
POST /predict → valid response
```

---

# 49. Test Fixtures

В repository должен находиться небольшой synthetic/example VCF:

```text
tests/fixtures/example.vcf
```

Он не должен содержать чувствительных данных.

---

# 50. CI

GitHub Actions должен автоматически выполнять:

```text
ruff check
mypy
pytest
```

При необходимости:

```text
docker build
```

---

# 51. Docker

Минимум:

```bash
docker build -t variantrank .
docker run ...
```

Для API:

```bash
docker compose up
```

---

# 52. Makefile

Пример команд:

```text
make install
make lint
make test
make train
make evaluate
make api
make docker
```

---

# 53. README

README должен быть одной из сильнейших частей проекта.

Структура:

```text
# VariantRank

One-line description

## Demo
## Motivation
## Architecture
## Dataset
## Features
## Validation
## Models
## Results
## Explainability
## CLI
## API
## Installation
## Reproducibility
## Limitations
## Roadmap
## License
```

---

# 54. README Hero Section

Пример:

> VariantRank is an end-to-end machine-learning system for prioritizing potentially pathogenic genetic variants from VCF files using functional, population and genomic annotations.

Ниже должна быть схема pipeline.

---

# 55. README — Results

Главная таблица:

```text
Model               Random CV    Gene-aware CV
------------------------------------------------
Logistic Regression   ...
Random Forest         ...
LightGBM              ...
CatBoost              ...
```

Метрики:

```text
ROC-AUC
PR-AUC
MCC
F1
```

---

# 56. README — Key Finding

Важно не просто показать лучшую метрику.

Нужно сделать исследовательский вывод.

Пример:

> Random variant-level validation substantially overestimated model performance compared with gene-aware validation, demonstrating the importance of controlling biological relatedness between train and test variants.

Такой вывод ценнее пары процентов ROC-AUC.

---

# 57. README — Limitations

Обязательно честно указать:

- ClinVar ascertainment bias;
- class imbalance;
- conflicting interpretations;
- annotation incompleteness;
- dependency of some predictors on previously labeled variants;
- gene-level distribution shift;
- no clinical validation;
- no ACMG/AMP classification;
- research use only.

---

# 58. Medical Disclaimer

README и API documentation должны содержать:

> VariantRank is a research and educational project. It is not intended for diagnosis, treatment decisions, or other clinical use.

---

# 59. Git Workflow

Основная ветка:

```text
main
```

Feature branches:

```text
feat/data-pipeline
feat/vep
feat/baselines
feat/catboost
feat/api
...
```

Commits:

```text
feat:
fix:
test:
docs:
refactor:
chore:
```

---

# 60. Этап 0 — Project Initialization

## Задачи

- создать GitHub repository;
- создать Python package;
- настроить uv;
- добавить linting;
- добавить pytest;
- добавить pre-commit;
- добавить GitHub Actions;
- создать базовый README.

## Definition of Done

```bash
uv run pytest
uv run ruff check .
```

проходят успешно.

---

# 61. Этап 1 — ClinVar Dataset

## Задачи

1. скачать ClinVar;
2. выбрать представление данных;
3. распарсить варианты;
4. привести clinical significance к единой схеме;
5. удалить ambiguous labels;
6. удалить дубликаты;
7. сохранить processed dataset.

## Output

```text
data/processed/clinvar.parquet
```

Пример schema:

```text
chrom
pos
ref
alt
gene
clinical_significance
review_status
target
```

---

# 62. Этап 2 — Variant Normalization

Необходимо:

- canonical chromosome naming;
- trimming common bases;
- left alignment для indels, если возможно;
- проверка REF/ALT;
- uniqueness key.

Ключ:

```text
chrom:pos:ref:alt
```

---

# 63. Этап 3 — Functional Annotation

Интегрировать VEP.

Необходимо:

- wrapper;
- subprocess handling;
- error handling;
- caching;
- parsing VEP output.

Не запускать VEP повторно для уже аннотированных вариантов.

---

# 64. Этап 4 — Feature Engineering

Создать единый:

```python
FeatureBuilder
```

Вход:

```text
annotated variants
```

Выход:

```text
model-ready dataframe
```

Feature schema должна быть сохранена.

---

# 65. Этап 5 — EDA

Создать:

```text
notebooks/01_eda.ipynb
```

Notebook должен использовать функции из `src/`, а не содержать весь production code внутри.

---

# 66. Этап 6 — Baselines

Обучить:

```text
Dummy
Logistic Regression
Random Forest
```

Получить первую baseline table.

---

# 67. Этап 7 — CatBoost / LightGBM

Обучить основные модели.

Hyperparameter optimization:

```text
Optuna
```

Но ограничить количество trials:

```text
20–50
```

Не нужно делать сотни запусков.

---

# 68. Этап 8 — Robust Validation

Главный эксперимент:

```text
random validation
vs
gene-aware validation
```

Сравнить все модели в одинаковых условиях.

---

# 69. Этап 9 — Calibration

Для лучшей модели:

```text
probability calibration
```

Сохранить calibrator.

---

# 70. Этап 10 — Explainability

Реализовать SHAP pipeline:

```text
global importance
individual variant explanation
```

Экспортировать plots в:

```text
reports/figures/
```

---

# 71. Этап 11 — Ranking

Создать `VariantRanker`.

Input:

```text
variants + probabilities
```

Output:

```text
sorted variants
rank
score
```

---

# 72. Этап 12 — CLI

Реализовать пользовательский workflow:

```bash
variantrank predict input.vcf
```

Без необходимости писать Python code.

---

# 73. Этап 13 — REST API

Создать FastAPI application.

Команда:

```bash
uvicorn variantrank.api.app:app
```

Swagger:

```text
/docs
```

---

# 74. Этап 14 — Docker

Docker image должен позволять запустить API без установки Python dependencies вручную.

---

# 75. Этап 15 — Documentation

Добавить:

```text
README
architecture diagram
example input
example output
metrics table
SHAP screenshot
API example
```

---

# 76. Этап 16 — Final Audit

Проверить:

- clean clone;
- installation;
- tests;
- train command;
- inference command;
- Docker;
- README;
- no secrets;
- no huge files;
- no private data.

---

# 77. План реализации на 10 дней

## День 1

### Project setup

- repo;
- uv;
- package;
- lint/test;
- CI;
- README skeleton.

### Data

- загрузка ClinVar;
- изучение schema.

---

## День 2

### ClinVar processing

- parser;
- label mapping;
- duplicates;
- QC;
- parquet dataset.

### Результат

Готовый clean training dataset.

---

## День 3

### Annotation

- VEP integration;
- feature schema;
- caching.

---

## День 4

### EDA + Baselines

- EDA;
- Dummy;
- Logistic Regression;
- Random Forest.

---

## День 5

### Boosting

- CatBoost;
- LightGBM;
- Optuna;
- baseline metrics.

---

## День 6

### Robust validation

- Group split;
- gene-aware CV;
- leakage analysis;
- сравнение с random split.

---

## День 7

### Explainability

- SHAP;
- feature importance;
- error analysis;
- calibration.

---

## День 8

### Inference

- model artifact;
- predictor;
- ranking;
- CLI.

---

## День 9

### Production

- FastAPI;
- Docker;
- integration tests;
- API tests.

---

## День 10

### Portfolio polish

- README;
- diagrams;
- figures;
- example VCF;
- metrics;
- limitations;
- cleanup;
- release `v1.0.0`.

---

# 78. Definition of Done — Data

Проект считается готовым по data части, если:

- ClinVar загружается автоматически или документированно;
- preprocessing воспроизводим;
- labels формируются автоматически;
- ambiguous variants исключаются;
- dataset сохраняется;
- schema проверяется.

---

# 79. Definition of Done — ML

Необходимо:

- минимум 3 модели;
- random baseline;
- group-aware validation;
- минимум ROC-AUC + PR-AUC + MCC;
- model comparison;
- probability calibration;
- error analysis;
- SHAP.

---

# 80. Definition of Done — Engineering

Необходимо:

```text
CLI
FastAPI
Docker
pytest
CI
config
logging
saved model
```

---

# 81. Definition of Done — Portfolio

GitHub visitor должен за первые 30 секунд понять:

1. какую проблему решает проект;
2. как выглядит architecture;
3. какие данные используются;
4. какие модели сравнивались;
5. какая validation strategy;
6. какие результаты;
7. как запустить проект;
8. как выглядит output.

---

# 82. Acceptance Criteria

Проект можно считать полностью завершённым, если выполняется:

```bash
git clone ...
cd variantrank
uv sync
uv run pytest
uv run variantrank --help
```

и предоставленный example VCF успешно проходит inference.

---

# 83. Minimum Portfolio Version

Если нужно сократить проект, обязательный минимум:

```text
ClinVar
VCF parser
annotations
feature engineering
Logistic Regression
CatBoost
gene-aware split
ROC-AUC / PR-AUC / MCC
SHAP
CLI
README
tests
Docker
```

API можно отложить.

---

# 84. Advanced Version

После v1.0 можно добавить:

- multiclass classification;
- VUS ranking;
- ACMG evidence support;
- phenotype-aware prioritization;
- HPO terms;
- gene-disease associations;
- inheritance models;
- trio analysis;
- ensemble;
- protein language model embeddings;
- sequence context embeddings;
- web interface.

---

# 85. Stretch Goal — Phenotype-aware Variant Ranking

Добавить:

```text
patient HPO terms
+
variant features
+
gene-disease associations
```

Pipeline:

```text
HPO phenotype
       ↓
gene relevance score
       ↓
variant pathogenicity
       ↓
combined ranking
```

Это превратит VariantRank в значительно более реалистичный variant prioritization system.

---

# 86. Stretch Goal — Protein Language Models

Для missense variants можно добавить embeddings:

```text
wild-type protein
mutant protein
```

и вычислять:

```text
embedding distance
```

или использовать pretrained protein model.

Это уже потребует GPU, но не входит в основную версию.

---

# 87. Stretch Goal — Sequence Context Model

Использовать DNA context вокруг варианта:

```text
±128 / ±256 bp
```

как вход в pretrained DNA encoder.

Основной проект должен работать и без этого.

---

# 88. Stretch Goal — Web UI

Простой интерфейс:

```text
Upload VCF
    ↓
Analyze
    ↓
sortable table
    ↓
variant details
```

Стек:

```text
Streamlit
```

или:

```text
React + FastAPI
```

---

# 89. Потенциальные проблемы

## Problem 1

Слишком большой dataset.

### Решение

- parquet;
- column pruning;
- chunking;
- polars/pyarrow;
- subset на этапе разработки.

---

## Problem 2

VEP работает медленно.

### Решение

- batch mode;
- cache;
- annotation cache;
- не аннотировать повторно.

---

## Problem 3

Leakage.

### Решение

- group-aware splits;
- audit features;
- separate external predictors;
- compare feature sets.

---

## Problem 4

Слишком высокая метрика.

Если ROC-AUC оказывается условно `0.99+`, нельзя автоматически считать это успехом.

Проверить:

- leakage;
- duplicate variants;
- gene overlap;
- direct pathogenicity predictors;
- label-derived annotations.

---

# 90. Что НЕ использовать как доказательство качества

Нельзя ограничиваться:

```text
Accuracy = 98%
```

Без:

- class balance;
- PR-AUC;
- gene-aware evaluation;
- leakage analysis.

---

# 91. Hardware Strategy

Основной проект CPU-first.

## Минимально

```text
CPU: 4 cores
RAM: 16 GB
GPU: none
SSD: 20+ GB free
```

## Комфортно

```text
CPU: 8+ cores
RAM: 32 GB
GPU: none
SSD: 50+ GB free
```

GPU не должен быть обязательной зависимостью.

---

# 92. Что должно быть видно работодателю

Проект должен демонстрировать:

## Bioinformatics

```text
VCF
ClinVar
VEP
variant annotation
genomic coordinates
allele frequencies
```

## ML

```text
classification
imbalance
boosting
calibration
ranking
SHAP
robust validation
```

## Engineering

```text
Python package
CLI
API
Docker
tests
CI
configs
logging
```

---

# 93. Какие вакансии закрывает проект

Проект наиболее полезен для ролей:

```text
Bioinformatician
Bioinformatics Engineer
Computational Biologist
Genomics Data Scientist
ML Engineer — Bioinformatics
Data Scientist — Biotech
Clinical Genomics Data Scientist
Precision Medicine Data Scientist
```

---

# 94. Формулировка для CV

После получения фактических метрик:

> **VariantRank — ML system for genetic variant prioritization:** developed an end-to-end VCF processing and pathogenicity ranking pipeline using ClinVar-derived labels, functional and population annotations, gradient boosting and calibrated probabilities; implemented gene-aware validation, SHAP-based explainability, CLI/API inference and reproducible Docker deployment.

Не добавлять конкретные метрики, пока они реально не получены.

---

# 95. Формулировка для GitHub

```text
VariantRank
Machine-learning system for prioritizing potentially pathogenic genetic variants from VCF files using functional and population annotations with robust gene-aware validation.
```

---

# 96. Рекомендуемое название GitHub repository

Основное:

```text
variant-rank
```

Альтернативы:

```text
variantrank
variant-prioritizer
genomic-variant-ranker
```

Предпочтительно:

```text
variant-rank
```

---

# 97. Release Strategy

## v0.1

```text
data pipeline
VCF parser
```

## v0.2

```text
features
baselines
```

## v0.3

```text
CatBoost
validation
```

## v0.4

```text
SHAP
calibration
ranking
```

## v0.5

```text
CLI
API
Docker
```

## v1.0

```text
tests
documentation
reproducibility
portfolio-ready release
```

---

# 98. Пример GitHub Issues

```text
[DATA] Implement ClinVar downloader
[DATA] Parse clinical significance labels
[BIO] Add VCF normalization
[BIO] Integrate VEP annotations
[ML] Implement logistic baseline
[ML] Add CatBoost training
[ML] Implement gene-aware CV
[ML] Add probability calibration
[ML] Add SHAP explanations
[ENG] Implement CLI
[ENG] Implement FastAPI service
[ENG] Add Docker image
[TEST] Add pipeline integration test
[DOCS] Add architecture diagram
[DOCS] Add benchmark table
```

---

# 99. Codex Workflow

Codex должен использоваться в первую очередь для:

- scaffolding;
- boilerplate;
- parsers;
- tests;
- refactoring;
- typing;
- CLI;
- FastAPI;
- Docker;
- GitHub Actions;
- documentation;
- repetitive feature code.

Не отдавать Codex без проверки решения по:

- labels;
- biological assumptions;
- leakage;
- validation strategy;
- interpretation;
- scientific conclusions.

---

# 100. Первый рабочий milestone

Первая цель:

```text
ClinVar
  ↓
clean dataframe
  ↓
features
  ↓
Logistic Regression
  ↓
gene-aware test
  ↓
metrics
```

До достижения этого milestone не заниматься UI и сложным deployment.

---

# 101. Второй milestone

```text
CatBoost
   ↓
calibration
   ↓
SHAP
   ↓
variant ranking
```

---

# 102. Третий milestone

```text
VCF
 ↓
annotation
 ↓
model
 ↓
ranked CSV
```

После этого проект уже имеет практическую ценность.

---

# 103. Четвёртый milestone

```text
CLI
API
Docker
Tests
CI
README
```

После этого проект становится portfolio-grade.

---

# 104. Финальный критерий качества

Проект должен отвечать на три вопроса:

### 1. Bioinformatics

> Умеет ли автор работать с реальными genomic data и форматами?

Ответ должен быть очевидно **да**.

### 2. Machine Learning

> Понимает ли автор validation, leakage, imbalance, calibration и explainability?

Ответ должен быть очевидно **да**.

### 3. Engineering

> Можно ли этот проект воспроизвести и использовать без открытия Jupyter Notebook?

Ответ должен быть очевидно **да**.

---

# 105. Итог

VariantRank должен быть не "моделью на ClinVar", а полноценным end-to-end проектом:

```text
real genomic input
        ↓
bioinformatics processing
        ↓
ML
        ↓
robust validation
        ↓
explainability
        ↓
variant ranking
        ↓
reproducible inference
```

При корректной реализации проект демонстрирует одновременно:

- genomics;
- bioinformatics;
- statistical ML;
- explainability;
- validation methodology;
- Python engineering;
- API development;
- reproducibility;
- Docker/CI.

Это и является основной целью проекта как portfolio-grade работы.
