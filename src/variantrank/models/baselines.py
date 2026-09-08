"""Leakage-safe baseline estimators."""

from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from variantrank.features import BASIC_CATEGORICAL_FEATURES, BASIC_NUMERIC_FEATURES


def build_preprocessor() -> ColumnTransformer:
    """Create a reusable transformer for heterogeneous basic features."""
    numeric = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("encode", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    return ColumnTransformer(
        [
            ("numeric", numeric, BASIC_NUMERIC_FEATURES),
            ("categorical", categorical, BASIC_CATEGORICAL_FEATURES),
        ]
    )


def build_baseline_models(*, random_seed: int = 42) -> dict[str, Pipeline]:
    """Return comparable dummy and logistic baseline pipelines."""
    return {
        "dummy": Pipeline(
            [
                ("preprocess", build_preprocessor()),
                ("classifier", DummyClassifier(strategy="prior", random_state=random_seed)),
            ]
        ),
        "logistic_regression": Pipeline(
            [
                ("preprocess", build_preprocessor()),
                (
                    "classifier",
                    LogisticRegression(
                        class_weight="balanced",
                        max_iter=300,
                        random_state=random_seed,
                    ),
                ),
            ]
        ),
    }
