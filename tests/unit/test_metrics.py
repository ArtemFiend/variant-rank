import numpy as np
import pytest

from variantrank.evaluation.metrics import classification_metrics


def test_classification_metrics_for_perfect_ranking() -> None:
    metrics = classification_metrics(np.array([0, 0, 1, 1]), np.array([0.01, 0.1, 0.9, 0.99]))

    assert metrics["roc_auc"] == pytest.approx(1.0)
    assert metrics["pr_auc"] == pytest.approx(1.0)
    assert metrics["mcc"] == pytest.approx(1.0)


def test_classification_metrics_rejects_invalid_threshold() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        classification_metrics(np.array([0, 1]), np.array([0.1, 0.9]), threshold=1.1)
