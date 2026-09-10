import numpy as np
import pandas as pd
import pytest

from variantrank.evaluation.splits import gene_aware_split, random_split


def test_random_split_has_expected_sizes_and_class_balance() -> None:
    target = pd.Series([0, 1] * 100)

    split = random_split(target)

    assert (len(split.train), len(split.validation), len(split.test)) == (140, 30, 30)
    assert target.iloc[split.train].mean() == pytest.approx(0.5)
    assert not set(split.train) & set(split.test)


def test_gene_aware_split_keeps_genes_disjoint() -> None:
    genes = pd.Series(np.repeat([f"GENE{index}" for index in range(70)], 2))
    genes.iloc[:2] = "GENE0;BRIDGE"
    genes.iloc[2:4] = "BRIDGE;GENE1"
    target = pd.Series([0, 1] * 70)

    split = gene_aware_split(target, genes)
    partitions = [
        {token for value in genes.iloc[indices] for token in value.replace(";", ",").split(",")}
        for indices in (split.train, split.validation, split.test)
    ]

    assert not partitions[0] & partitions[1]
    assert not partitions[0] & partitions[2]
    assert not partitions[1] & partitions[2]
    assert sum(len(indices) for indices in (split.train, split.validation, split.test)) == len(
        target
    )


def test_gene_aware_split_requires_enough_groups() -> None:
    with pytest.raises(ValueError, match="7 unique genes"):
        gene_aware_split(pd.Series([0, 1] * 3), pd.Series(["A", "A", "B", "B", "C", "C"]))
