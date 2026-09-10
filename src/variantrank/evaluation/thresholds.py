"""Validation-set operating point selection for binary classifiers."""

from dataclasses import dataclass

import numpy as np
from sklearn.metrics import precision_recall_curve


@dataclass(frozen=True, slots=True)
class OperatingPoint:
    """A probability threshold and its validation-set precision/recall."""

    threshold: float
    precision: float
    recall: float
    f1: float


def select_operating_points(
    target: np.ndarray,
    probability: np.ndarray,
    *,
    minimum_recall: float = 0.90,
    minimum_precision: float = 0.90,
) -> dict[str, OperatingPoint]:
    """Select F1, recall-constrained, and precision-constrained thresholds."""
    if target.ndim != 1 or probability.ndim != 1 or len(target) != len(probability):
        raise ValueError("target and probability must be aligned one-dimensional arrays")
    if not 0.0 < minimum_recall <= 1.0 or not 0.0 < minimum_precision <= 1.0:
        raise ValueError("minimum precision and recall must be in (0, 1]")
    if not np.isfinite(probability).all() or ((probability < 0) | (probability > 1)).any():
        raise ValueError("probabilities must be finite and between 0 and 1")

    precision, recall, thresholds = precision_recall_curve(target, probability)
    candidates = [
        OperatingPoint(
            threshold=float(threshold),
            precision=float(candidate_precision),
            recall=float(candidate_recall),
            f1=_f1(float(candidate_precision), float(candidate_recall)),
        )
        for threshold, candidate_precision, candidate_recall in zip(
            thresholds, precision[:-1], recall[:-1], strict=True
        )
    ]
    if not candidates:
        raise ValueError("at least two distinct classes and one probability threshold are required")

    max_f1 = max(candidates, key=lambda point: (point.f1, point.threshold))
    recall_candidates = [point for point in candidates if point.recall >= minimum_recall]
    precision_candidates = [point for point in candidates if point.precision >= minimum_precision]
    if not recall_candidates:
        raise ValueError(f"no threshold reaches minimum recall {minimum_recall:.3f}")
    if not precision_candidates:
        raise ValueError(f"no threshold reaches minimum precision {minimum_precision:.3f}")

    recall_target = max(
        recall_candidates,
        key=lambda point: (point.precision, point.recall, point.threshold),
    )
    precision_target = max(
        precision_candidates,
        key=lambda point: (point.recall, point.precision, -point.threshold),
    )
    return {
        "max_f1": max_f1,
        f"recall_at_least_{minimum_recall:.2f}": recall_target,
        f"precision_at_least_{minimum_precision:.2f}": precision_target,
    }


def _f1(precision: float, recall: float) -> float:
    denominator = precision + recall
    return 0.0 if denominator == 0.0 else 2.0 * precision * recall / denominator
