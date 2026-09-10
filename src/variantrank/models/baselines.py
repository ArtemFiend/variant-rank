"""Leakage-safe baseline estimators."""

from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from variantrank.features import BASIC_CATEGORICAL_FEATURES, BASIC_NUMERIC_FEATURES


def build_preprocessor(
    *,
    numeric_features: list[str] | None = None,
    categorical_features: list[str] | None = None,
) -> ColumnTransformer:
    """Create a reusable transformer for heterogeneous model features."""
    numeric_columns = numeric_features or BASIC_NUMERIC_FEATURES
    categorical_columns = categorical_features or BASIC_CATEGORICAL_FEATURES
    numeric = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent", missing_values=None)),
            ("encode", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    return ColumnTransformer(
        [
            ("numeric", numeric, numeric_columns),
            ("categorical", categorical, categorical_columns),
        ]
    )


def build_baseline_models(
    *,
    numeric_features: list[str] | None = None,
    categorical_features: list[str] | None = None,
    random_seed: int = 42,
) -> dict[str, Pipeline]:
    """Return comparable dummy, linear, and tree baseline pipelines."""

    def preprocessor() -> ColumnTransformer:
        return build_preprocessor(
            numeric_features=numeric_features,
            categorical_features=categorical_features,
        )

    return {
        "dummy": Pipeline(
            [
                ("preprocess", preprocessor()),
                ("classifier", DummyClassifier(strategy="prior", random_state=random_seed)),
            ]
        ),
        "logistic_regression": Pipeline(
            [
                ("preprocess", preprocessor()),
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
        "random_forest": Pipeline(
            [
                ("preprocess", preprocessor()),
                (
                    "classifier",
                    RandomForestClassifier(
                        n_estimators=100,
                        max_depth=20,
                        min_samples_leaf=5,
                        class_weight="balanced_subsample",
                        n_jobs=-1,
                        random_state=random_seed,
                    ),
                ),
            ]
        ),
    }
