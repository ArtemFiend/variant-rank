"""Ranking metrics and deterministic synthetic patient-cohort evaluation."""

from collections.abc import Sequence

import numpy as np


def ranking_metrics(
    target: np.ndarray,
    score: np.ndarray,
    *,
    cutoffs: Sequence[int],
) -> dict[str, float]:
    """Calculate binary relevance ranking metrics at fixed cutoffs."""
    _validate_ranking_inputs(target, score, cutoffs)
    order = np.argsort(-score, kind="stable")
    relevance = target[order].astype(float)
    positives = float(relevance.sum())
    metrics: dict[str, float] = {}
    positive_ranks = np.flatnonzero(relevance) + 1
    metrics["mrr"] = 0.0 if len(positive_ranks) == 0 else 1.0 / float(positive_ranks[0])

    for cutoff in cutoffs:
        top = relevance[:cutoff]
        hits = float(top.sum())
        metrics[f"precision_at_{cutoff}"] = hits / cutoff
        metrics[f"recall_at_{cutoff}"] = 0.0 if positives == 0 else hits / positives
        discounts = 1.0 / np.log2(np.arange(2, cutoff + 2))
        dcg = float(np.sum(top * discounts))
        ideal_hits = min(int(positives), cutoff)
        ideal_dcg = float(np.sum(discounts[:ideal_hits]))
        metrics[f"ndcg_at_{cutoff}"] = 0.0 if ideal_dcg == 0.0 else dcg / ideal_dcg
    return metrics


def simulate_patient_rankings(
    target: np.ndarray,
    score: np.ndarray,
    *,
    patients: int = 1000,
    variants_per_patient: int = 50,
    pathogenic_per_patient: int = 1,
    cutoffs: Sequence[int] = (1, 5, 10),
    random_seed: int = 42,
) -> dict[str, float]:
    """Average ranking metrics over reproducible mixed benign/pathogenic cohorts."""
    _validate_ranking_inputs(target, score, cutoffs)
    if patients < 1:
        raise ValueError("patients must be positive")
    if not 1 <= pathogenic_per_patient < variants_per_patient:
        raise ValueError("pathogenic_per_patient must be between 1 and cohort size - 1")
    if max(cutoffs) > variants_per_patient:
        raise ValueError("ranking cutoff exceeds variants per patient")

    positive_indices = np.flatnonzero(target == 1)
    negative_indices = np.flatnonzero(target == 0)
    benign_per_patient = variants_per_patient - pathogenic_per_patient
    if len(positive_indices) < pathogenic_per_patient or len(negative_indices) < benign_per_patient:
        raise ValueError("insufficient positive or negative variants for patient simulation")

    generator = np.random.default_rng(random_seed)
    totals: dict[str, float] = {}
    for _ in range(patients):
        indices = np.concatenate(
            [
                generator.choice(positive_indices, pathogenic_per_patient, replace=False),
                generator.choice(negative_indices, benign_per_patient, replace=False),
            ]
        )
        metrics = ranking_metrics(target[indices], score[indices], cutoffs=cutoffs)
        for name, value in metrics.items():
            totals[name] = totals.get(name, 0.0) + value
    return {name: value / patients for name, value in totals.items()}


def _validate_ranking_inputs(
    target: np.ndarray,
    score: np.ndarray,
    cutoffs: Sequence[int],
) -> None:
    if target.ndim != 1 or score.ndim != 1 or len(target) != len(score) or len(target) == 0:
        raise ValueError("target and score must be aligned non-empty one-dimensional arrays")
    if not set(np.unique(target)).issubset({0, 1}):
        raise ValueError("ranking target must be binary")
    if not np.isfinite(score).all():
        raise ValueError("ranking scores must be finite")
    if not cutoffs or any(cutoff < 1 or cutoff > len(target) for cutoff in cutoffs):
        raise ValueError("ranking cutoffs must be between 1 and the number of variants")
