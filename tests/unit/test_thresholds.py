import numpy as np
import pytest

from variantrank.evaluation.thresholds import select_operating_points


def test_select_operating_points_uses_validation_probabilities() -> None:
    points = select_operating_points(
        np.array([0, 0, 1, 1]),
        np.array([0.10, 0.40, 0.60, 0.90]),
        minimum_recall=1.0,
        minimum_precision=1.0,
    )

    assert points["max_f1"].threshold == pytest.approx(0.60)
    assert points["recall_at_least_1.00"].recall == pytest.approx(1.0)
    assert points["precision_at_least_1.00"].precision == pytest.approx(1.0)


@pytest.mark.parametrize("minimum", [0.0, 1.1])
def test_select_operating_points_rejects_invalid_constraints(minimum: float) -> None:
    with pytest.raises(ValueError, match="must be in"):
        select_operating_points(
            np.array([0, 1]),
            np.array([0.1, 0.9]),
            minimum_recall=minimum,
        )
