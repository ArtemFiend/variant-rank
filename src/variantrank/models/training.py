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
from variantrank.evaluation.splits import DatasetSplit
from variantrank.features import (
    BASIC_CATEGORICAL_FEATURES,
    BASIC_NUMERIC_FEATURES,
    build_basic_features,
)
from variantrank.models.baselines import build_baseline_models

SplitStrategy = Literal["random", "gene"]
DATASET_COLUMNS = ["chrom", "ref", "alt", "variant_type", "gene", "target"]


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
    random_seed: int = 42,
    max_rows: int | None = None,
) -> BaselineExperimentResult:
    """Train and evaluate Dummy and Logistic Regression on one dataset."""
    if not dataset.is_file():
        raise FileNotFoundError(dataset)
    if max_rows is not None and max_rows < 100:
        raise ValueError("max_rows must be at least 100")

    variants = pd.read_parquet(dataset, columns=DATASET_COLUMNS)
    if max_rows is not None and len(variants) > max_rows:
        variants = _stratified_sample(variants, max_rows, random_seed)
    _validate_training_frame(variants)

    target = variants["target"].astype("int8")
    features = build_basic_features(variants)
    split = _make_split(target, variants["gene"], strategy, random_seed)

    artifact_dir = artifact_root / dataset.stem / strategy
    artifact_dir.mkdir(parents=True, exist_ok=True)
    all_metrics: dict[str, dict[str, dict[str, float]]] = {}
    durations: dict[str, float] = {}

    for name, model in build_baseline_models(random_seed=random_seed).items():
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
            "feature_set": "basic_variant_v1",
            "numeric_features": BASIC_NUMERIC_FEATURES,
            "categorical_features": BASIC_CATEGORICAL_FEATURES,
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
    missing = set(DATASET_COLUMNS) - set(frame.columns)
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
    return pd.concat(sampled).sample(frac=1, random_state=random_seed).reset_index(drop=True)


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
            "genes": int(genes.iloc[indices].nunique()),
        }
        for name, indices in {
            "train": split.train,
            "validation": split.validation,
            "test": split.test,
        }.items()
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
