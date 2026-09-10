"""Native-categorical CatBoost candidate model."""

from dataclasses import asdict, dataclass

from catboost import CatBoostClassifier
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline


@dataclass(frozen=True, slots=True)
class CatBoostConfig:
    """Reproducible CPU-first CatBoost hyperparameters."""

    iterations: int = 1000
    depth: int = 7
    learning_rate: float = 0.05
    loss_function: str = "Logloss"
    eval_metric: str = "PRAUC"

    def as_dict(self) -> dict[str, int | float | str]:
        """Return JSON-serializable configuration metadata."""
        return asdict(self)


def build_catboost_model(
    *,
    numeric_features: list[str],
    categorical_features: list[str],
    random_seed: int = 42,
    config: CatBoostConfig | None = None,
) -> Pipeline:
    """Build a pipeline that preserves native categorical CatBoost features."""
    settings = config or CatBoostConfig()
    preprocess = ColumnTransformer(
        [
            ("numeric", SimpleImputer(strategy="median"), numeric_features),
            (
                "categorical",
                SimpleImputer(
                    strategy="constant",
                    fill_value="__MISSING__",
                    missing_values=None,
                ),
                categorical_features,
            ),
        ],
        verbose_feature_names_out=False,
    ).set_output(transform="pandas")
    classifier = CatBoostClassifier(
        **settings.as_dict(),
        cat_features=categorical_features,
        auto_class_weights="Balanced",
        random_seed=random_seed,
        thread_count=-1,
        allow_writing_files=False,
        verbose=False,
    )
    return Pipeline([("preprocess", preprocess), ("classifier", classifier)])
