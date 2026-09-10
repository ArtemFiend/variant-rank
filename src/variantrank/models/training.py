"""Baseline training orchestration and artifact persistence."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

import joblib
import pandas as pd

from variantrank import __version__
from variantrank.data.download import file_digest
from variantrank.evaluation import classification_metrics, gene_aware_split, random_split
from variantrank.evaluation.splits import DatasetSplit, count_unique_genes
from variantrank.features import (
    BASIC_CATEGORICAL_FEATURES,
    BASIC_NUMERIC_FEATURES,
    MODEL_CATEGORICAL_FEATURES,
    MODEL_FEATURES,
    MODEL_NUMERIC_FEATURES,
    build_basic_features,
)
from variantrank.models.baselines import build_baseline_models

SplitStrategy = Literal["random", "gene"]
FeatureSet = Literal["basic", "annotated"]
BASIC_DATASET_COLUMNS = ["chrom", "ref", "alt", "variant_type", "gene", "target"]
ANNOTATED_DATASET_COLUMNS = ["gene", "target", "high_confidence", *MODEL_FEATURES]
TRAINING_REQUIRED_COLUMNS = ["gene", "target"]


@dataclass(frozen=True, slots=True)
class BaselineExperimentResult:
    """Summary and paths from a completed baseline comparison."""

    strategy: SplitStrategy
    dataset: Path
    artifact_dir: Path
    metrics_path: Path
    metrics: dict[str, dict[str, dict[str, float]]]


def run_baseline_experiment(
    dataset: Path,
    artifact_root: Path,
    *,
    strategy: SplitStrategy,
    feature_set: FeatureSet = "basic",
    high_confidence_only: bool = False,
    random_seed: int = 42,
    max_rows: int | None = None,
) -> BaselineExperimentResult:
    """Train and evaluate Dummy and Logistic Regression on one dataset."""
    if not dataset.is_file():
        raise FileNotFoundError(dataset)
    if max_rows is not None and max_rows < 100:
        raise ValueError("max_rows must be at least 100")

    variants, features, numeric_features, categorical_features = _load_features(
        dataset,
        feature_set=feature_set,
        high_confidence_only=high_confidence_only,
    )
    if max_rows is not None and len(variants) > max_rows:
        sampled = _stratified_sample(variants, max_rows, random_seed)
        features = features.loc[sampled.index]
        variants = sampled.reset_index(drop=True)
        features = features.reset_index(drop=True)
    _validate_training_frame(variants)

    target = variants["target"].astype("int8")
    split = _make_split(target, variants["gene"], strategy, random_seed)

    cohort = "high_confidence" if high_confidence_only else "all"
    feature_version = "basic_variant_v1" if feature_set == "basic" else "annotated_vep_v1"
    artifact_dir = artifact_root / dataset.stem / cohort / feature_version / strategy
    artifact_dir.mkdir(parents=True, exist_ok=True)
    all_metrics: dict[str, dict[str, dict[str, float]]] = {}
    durations: dict[str, float] = {}

    for name, model in build_baseline_models(
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        random_seed=random_seed,
    ).items():
        started = perf_counter()
        model.fit(features.iloc[split.train], target.iloc[split.train])
        durations[name] = perf_counter() - started
        all_metrics[name] = {
            "validation": classification_metrics(
                target.iloc[split.validation].to_numpy(),
                model.predict_proba(features.iloc[split.validation])[:, 1],
            ),
            "test": classification_metrics(
                target.iloc[split.test].to_numpy(),
                model.predict_proba(features.iloc[split.test])[:, 1],
            ),
        }
        joblib.dump(model, artifact_dir / f"{name}.joblib")

    metrics_path = artifact_dir / "metrics.json"
    _write_json(metrics_path, all_metrics)
    _write_json(
        artifact_dir / "metadata.json",
        {
            "pipeline_version": __version__,
            "created_at": datetime.now(UTC).isoformat(),
            "dataset": str(dataset),
            "dataset_sha256": file_digest(dataset),
            "dataset_rows": len(variants),
            "strategy": strategy,
            "random_seed": random_seed,
            "feature_set": feature_version,
            "cohort": cohort,
            "numeric_features": numeric_features,
            "categorical_features": categorical_features,
            "split": _split_summary(split, target, variants["gene"]),
            "training_seconds": durations,
        },
    )
    return BaselineExperimentResult(
        strategy=strategy,
        dataset=dataset,
        artifact_dir=artifact_dir,
        metrics_path=metrics_path,
        metrics=all_metrics,
    )


def _load_features(
    dataset: Path,
    *,
    feature_set: FeatureSet,
    high_confidence_only: bool,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str], list[str]]:
    if feature_set == "basic":
        if high_confidence_only:
            raise ValueError("high-confidence filtering requires the annotated feature dataset")
        variants = pd.read_parquet(dataset, columns=BASIC_DATASET_COLUMNS)
        features = _normalize_features(
            build_basic_features(variants),
            numeric_features=BASIC_NUMERIC_FEATURES,
            categorical_features=BASIC_CATEGORICAL_FEATURES,
        )
        return (
            variants,
            features,
            BASIC_NUMERIC_FEATURES,
            BASIC_CATEGORICAL_FEATURES,
        )
    if feature_set != "annotated":
        raise ValueError(f"unknown feature set: {feature_set}")

    variants = pd.read_parquet(dataset, columns=ANNOTATED_DATASET_COLUMNS)
    if high_confidence_only:
        variants = variants.loc[variants["high_confidence"]].copy()
    features = _normalize_features(
        variants.loc[:, MODEL_FEATURES].copy(),
        numeric_features=MODEL_NUMERIC_FEATURES,
        categorical_features=MODEL_CATEGORICAL_FEATURES,
    )
    return variants, features, MODEL_NUMERIC_FEATURES, MODEL_CATEGORICAL_FEATURES


def _normalize_features(
    features: pd.DataFrame,
    *,
    numeric_features: list[str],
    categorical_features: list[str],
) -> pd.DataFrame:
    features[numeric_features] = features[numeric_features].astype("float64")
    for name in categorical_features:
        column = features[name].astype("object")
        features[name] = column.where(column.notna(), None)
    return features


def _make_split(
    target: pd.Series,
    genes: pd.Series,
    strategy: SplitStrategy,
    random_seed: int,
) -> DatasetSplit:
    if strategy == "random":
        return random_split(target, random_seed=random_seed)
    return gene_aware_split(target, genes, random_seed=random_seed)


def _validate_training_frame(frame: pd.DataFrame) -> None:
    missing = set(TRAINING_REQUIRED_COLUMNS) - set(frame.columns)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"training dataset is missing columns: {names}")
    if frame.empty:
        raise ValueError("training dataset is empty")
    if set(frame["target"].unique()) != {0, 1}:
        raise ValueError("training dataset must contain binary targets 0 and 1")


def _stratified_sample(frame: pd.DataFrame, size: int, random_seed: int) -> pd.DataFrame:
    fractions = frame["target"].value_counts(normalize=True)
    sampled = [
        group.sample(
            n=min(len(group), max(1, round(size * float(fractions.loc[target])))),
            random_state=random_seed,
        )
        for target, group in frame.groupby("target", sort=True)
    ]
    return pd.concat(sampled).sample(frac=1, random_state=random_seed)


def _split_summary(
    split: DatasetSplit,
    target: pd.Series,
    genes: pd.Series,
) -> dict[str, dict[str, int | float]]:
    return {
        name: {
            "rows": len(indices),
            "pathogenic": int(target.iloc[indices].sum()),
            "pathogenic_fraction": float(target.iloc[indices].mean()),
            "genes": count_unique_genes(genes.iloc[indices]),
        }
        for name, indices in {
            "train": split.train,
            "validation": split.validation,
            "test": split.test,
        }.items()
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
