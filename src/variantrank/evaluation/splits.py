"""Reproducible random and gene-aware train/validation/test splits."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold, train_test_split


@dataclass(frozen=True, slots=True)
class DatasetSplit:
    """Positional indices for three disjoint dataset partitions."""

    train: np.ndarray
    validation: np.ndarray
    test: np.ndarray


def random_split(target: pd.Series, *, random_seed: int = 42) -> DatasetSplit:
    """Create a 70/15/15 stratified variant-level split."""
    indices = np.arange(len(target))
    train, remainder = train_test_split(
        indices,
        test_size=0.30,
        stratify=target,
        random_state=random_seed,
    )
    validation, test = train_test_split(
        remainder,
        test_size=0.50,
        stratify=target.iloc[remainder],
        random_state=random_seed,
    )
    return DatasetSplit(train=np.sort(train), validation=np.sort(validation), test=np.sort(test))


def gene_aware_split(
    target: pd.Series,
    genes: pd.Series,
    *,
    random_seed: int = 42,
) -> DatasetSplit:
    """Create approximately 71/14/14 splits with no gene overlap."""
    if genes.isna().any():
        raise ValueError("gene-aware split requires a gene for every variant")
    unique_genes = genes.nunique()
    if unique_genes < 7:
        raise ValueError("gene-aware split requires at least 7 unique genes")

    indices = np.arange(len(target))
    outer = StratifiedGroupKFold(n_splits=7, shuffle=True, random_state=random_seed)
    train_validation, test = next(outer.split(indices, target, groups=genes))

    inner_target = target.iloc[train_validation].reset_index(drop=True)
    inner_genes = genes.iloc[train_validation].reset_index(drop=True)
    inner_indices = np.arange(len(train_validation))
    inner = StratifiedGroupKFold(n_splits=6, shuffle=True, random_state=random_seed + 1)
    train_relative, validation_relative = next(
        inner.split(inner_indices, inner_target, groups=inner_genes)
    )
    train = train_validation[train_relative]
    validation = train_validation[validation_relative]

    _assert_no_group_overlap(genes, train, validation, test)
    return DatasetSplit(train=np.sort(train), validation=np.sort(validation), test=np.sort(test))


def _assert_no_group_overlap(
    genes: pd.Series,
    train: np.ndarray,
    validation: np.ndarray,
    test: np.ndarray,
) -> None:
    train_genes = set(genes.iloc[train])
    validation_genes = set(genes.iloc[validation])
    test_genes = set(genes.iloc[test])
    if train_genes & validation_genes or train_genes & test_genes or validation_genes & test_genes:
        raise RuntimeError("gene-aware split contains overlapping genes")
