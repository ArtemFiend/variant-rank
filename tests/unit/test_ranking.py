import numpy as np
import pytest

from variantrank.evaluation import ranking_metrics, simulate_patient_rankings


def test_ranking_metrics_for_perfect_order() -> None:
    metrics = ranking_metrics(
        np.array([0, 1, 0, 1]),
        np.array([0.1, 0.9, 0.2, 0.8]),
        cutoffs=(1, 2, 4),
    )

    assert metrics["mrr"] == pytest.approx(1.0)
    assert metrics["precision_at_2"] == pytest.approx(1.0)
    assert metrics["recall_at_2"] == pytest.approx(1.0)
    assert metrics["ndcg_at_4"] == pytest.approx(1.0)


def test_ranking_metrics_without_positive_variants_are_zero() -> None:
    metrics = ranking_metrics(np.array([0, 0]), np.array([0.8, 0.2]), cutoffs=(1, 2))

    assert metrics["mrr"] == 0.0
    assert metrics["recall_at_2"] == 0.0
    assert metrics["ndcg_at_2"] == 0.0


def test_patient_simulation_is_reproducible_and_finds_perfect_signal() -> None:
    target = np.array([1] * 10 + [0] * 100)
    score = target.astype(float)

    first = simulate_patient_rankings(
        target,
        score,
        patients=20,
        variants_per_patient=10,
        cutoffs=(1, 5),
        random_seed=7,
    )
    second = simulate_patient_rankings(
        target,
        score,
        patients=20,
        variants_per_patient=10,
        cutoffs=(1, 5),
        random_seed=7,
    )

    assert first == second
    assert first["mrr"] == pytest.approx(1.0)
    assert first["recall_at_1"] == pytest.approx(1.0)


def test_patient_simulation_rejects_impossible_cohort() -> None:
    with pytest.raises(ValueError, match="insufficient"):
        simulate_patient_rankings(
            np.array([1, 0]),
            np.array([0.9, 0.1]),
            variants_per_patient=10,
            cutoffs=(1,),
        )
