"""Reproducible random and gene-aware train/validation/test splits."""

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold, train_test_split

GENE_SEPARATOR = re.compile(r"[;,|/]")


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
    groups = _connected_gene_groups(genes)
    if groups.nunique() < 7:
        raise ValueError("gene-aware split requires at least 7 unique genes")

    indices = np.arange(len(target))
    outer = StratifiedGroupKFold(n_splits=7, shuffle=True, random_state=random_seed)
    train_validation, test = next(outer.split(indices, target, groups=groups))

    inner_target = target.iloc[train_validation].reset_index(drop=True)
    inner_groups = groups.iloc[train_validation].reset_index(drop=True)
    inner_indices = np.arange(len(train_validation))
    inner = StratifiedGroupKFold(n_splits=6, shuffle=True, random_state=random_seed + 1)
    train_relative, validation_relative = next(
        inner.split(inner_indices, inner_target, groups=inner_groups)
    )
    train = train_validation[train_relative]
    validation = train_validation[validation_relative]

    _assert_no_gene_overlap(genes, train, validation, test)
    return DatasetSplit(train=np.sort(train), validation=np.sort(validation), test=np.sort(test))


def count_unique_genes(genes: pd.Series) -> int:
    """Count individual gene symbols, expanding multi-gene source values."""
    return len(_expanded_gene_set(genes))


def _connected_gene_groups(genes: pd.Series) -> pd.Series:
    unique_values = genes.astype("string").drop_duplicates().tolist()
    tokens_by_value = {value: _gene_tokens(value) for value in unique_values}
    parent: dict[str, str] = {}

    def find(gene: str) -> str:
        parent.setdefault(gene, gene)
        while parent[gene] != gene:
            parent[gene] = parent[parent[gene]]
            gene = parent[gene]
        return gene

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            first, second = sorted((left_root, right_root))
            parent[second] = first

    for tokens in tokens_by_value.values():
        for token in tokens[1:]:
            union(tokens[0], token)

    mapping = {value: find(tokens[0]) for value, tokens in tokens_by_value.items()}
    return genes.astype("string").map(mapping)


def _gene_tokens(value: str) -> tuple[str, ...]:
    tokens = tuple(token.strip() for token in GENE_SEPARATOR.split(value) if token.strip())
    if not tokens:
        raise ValueError("gene-aware split requires non-empty gene symbols")
    return tokens


def _expanded_gene_set(genes: pd.Series) -> set[str]:
    expanded: set[str] = set()
    for value in genes.astype("string").drop_duplicates():
        expanded.update(_gene_tokens(value))
    return expanded


def _assert_no_gene_overlap(
    genes: pd.Series,
    train: np.ndarray,
    validation: np.ndarray,
    test: np.ndarray,
) -> None:
    train_genes = _expanded_gene_set(genes.iloc[train])
    validation_genes = _expanded_gene_set(genes.iloc[validation])
    test_genes = _expanded_gene_set(genes.iloc[test])
    if train_genes & validation_genes or train_genes & test_genes or validation_genes & test_genes:
        raise RuntimeError("gene-aware split contains overlapping genes")
