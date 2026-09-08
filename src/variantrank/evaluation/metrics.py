"""Classification metrics for pathogenicity baselines."""

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    log_loss,
    matthews_corrcoef,
    precision_score,
    recall_score,
    roc_auc_score,
)


def classification_metrics(
    target: np.ndarray,
    probability: np.ndarray,
    *,
    threshold: float = 0.5,
) -> dict[str, float]:
    """Calculate discrimination, threshold, and probability metrics."""
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0 and 1")
    prediction = probability >= threshold
    return {
        "roc_auc": float(roc_auc_score(target, probability)),
        "pr_auc": float(average_precision_score(target, probability)),
        "f1": float(f1_score(target, prediction, zero_division=0)),
        "precision": float(precision_score(target, prediction, zero_division=0)),
        "recall": float(recall_score(target, prediction, zero_division=0)),
        "mcc": float(matthews_corrcoef(target, prediction)),
        "balanced_accuracy": float(balanced_accuracy_score(target, prediction)),
        "brier_score": float(brier_score_loss(target, probability)),
        "log_loss": float(log_loss(target, probability, labels=[0, 1])),
        "threshold": threshold,
    }
