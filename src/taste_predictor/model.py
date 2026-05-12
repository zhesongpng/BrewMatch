"""Gradient-boosted taste prediction model for BrewMatch.

Predicts a rating (1-10) given bean profile, recipe parameters, and optional
user history. Includes per-user bias layer and feature importance.

Uses LightGBM when available (faster, more accurate); falls back to
sklearn GradientBoostingRegressor when libomp is not installed.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

import joblib
import numpy as np

try:
    import lightgbm as lgb
    _HAS_LGBM = True
except (ImportError, OSError):
    _HAS_LGBM = False

from sklearn.ensemble import GradientBoostingRegressor

from src.taste_predictor.encoder import FeatureEncoder, encode_features
from src.data_models import BeanProfile, Recipe

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models"


def _sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

# Hyperparameters from spec §4.1, mapped to both backends
_MODEL_PARAMS = {
    "max_depth": 6,
    "learning_rate": 0.05,
    "n_estimators": 500,
    "min_samples_leaf": 20,
    "subsample": 0.8,
    "random_state": 42,
}


@dataclass
class PredictionResult:
    predicted_rating: float
    confidence_interval: tuple[float, float]
    user_bias: float
    base_prediction: float
    feature_importance: dict[str, float]


@dataclass
class TrainingResult:
    rmse_test: float
    mae_test: float
    r2_test: float
    rmse_val: float
    best_iteration: int
    train_size: int
    val_size: int
    test_size: int


FEATURE_NAMES = [
    "origin_encoded", "process_washed", "process_natural", "process_honey",
    "process_anaerobic", "process_other", "roast_ordinal",
    "cluster_floral", "cluster_berry", "cluster_citrus", "cluster_stone_fruit",
    "cluster_tropical", "cluster_sweet", "cluster_chocolate", "cluster_nutty",
    "cluster_spice", "cluster_roasted", "cluster_vegetal", "cluster_tea_like",
    "cluster_fermented", "cluster_syrupy", "cluster_balanced", "altitude_mean",
    "dose_g", "ratio", "grind_setting", "water_temp_c",
    "bloom_time_s", "total_time_s", "pour_count",
    "user_avg_rating", "user_rating_count", "user_roast_pref",
    "user_temp_pref", "user_grind_pref", "user_ratio_pref",
    "user_acidity_bias", "user_body_bias", "user_sweetness_bias",
    "roast_x_temp", "grind_x_time", "grind_x_temp",
    "ratio_x_dose", "roast_x_grind", "cluster_count",
]


def _create_model() -> object:
    """Create the best available gradient boosting model."""
    if _HAS_LGBM:
        return lgb.LGBMRegressor(
            objective="regression",
            metric="rmse",
            num_leaves=31,
            max_depth=_MODEL_PARAMS["max_depth"],
            learning_rate=_MODEL_PARAMS["learning_rate"],
            n_estimators=_MODEL_PARAMS["n_estimators"],
            min_child_samples=_MODEL_PARAMS["min_samples_leaf"],
            subsample=_MODEL_PARAMS["subsample"],
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=_MODEL_PARAMS["random_state"],
            verbose=-1,
        )
    return GradientBoostingRegressor(
        loss="squared_error",
        max_depth=_MODEL_PARAMS["max_depth"],
        learning_rate=_MODEL_PARAMS["learning_rate"],
        n_estimators=_MODEL_PARAMS["n_estimators"],
        min_samples_leaf=_MODEL_PARAMS["min_samples_leaf"],
        subsample=_MODEL_PARAMS["subsample"],
        random_state=_MODEL_PARAMS["random_state"],
    )


class TastePredictor:
    """Gradient-boosted taste predictor with per-user bias layer."""

    def __init__(self):
        self._model: Optional[object] = None
        self._backend: str = "lgbm" if _HAS_LGBM else "sklearn"
        self._encoder = FeatureEncoder()
        self._user_biases: dict[str, float] = {}
        self._global_mean: float = 6.0
        self._val_std: float = 1.5
        self._trained: bool = False
        self._best_iteration: int = 0

    @property
    def is_trained(self) -> bool:
        return self._trained and self._model is not None

    @property
    def backend(self) -> str:
        return self._backend

    def encode_features(
        self,
        bean_profile: BeanProfile,
        recipe: Recipe,
        **user_kwargs: float,
    ) -> np.ndarray:
        """Encode bean, recipe, and user features into a 45-element array.

        Public API for downstream consumers (optimizer, diagnosis engine).
        Delegates to the encoder module.
        """
        return self._encoder.encode(bean_profile, recipe, **user_kwargs)

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
    ) -> dict:
        """Train the model with early stopping."""
        self._model = _create_model()

        if _HAS_LGBM:
            self._model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)],
            )
            self._best_iteration = self._model.best_iteration_
        else:
            # sklearn: use validation-based early stopping via n_iter_no_change
            self._model.n_iter_no_change = 50
            self._model.validation_fraction = len(X_val) / (len(X_train) + len(X_val))
            self._model.fit(X_train, y_train)
            self._best_iteration = getattr(self._model, "n_estimators_", self._model.n_estimators)

        self._global_mean = float(np.mean(y_train))
        self._trained = True

        val_pred = self._model.predict(X_val)
        self._val_std = float(np.std(y_val - val_pred))

        val_rmse = float(np.sqrt(np.mean((y_val - val_pred) ** 2)))
        logger.info(
            "model.train.complete n_train=%d n_val=%d val_rmse=%.4f backend=%s best_iteration=%d",
            len(y_train), len(y_val), round(val_rmse, 4),
            self._backend, self._best_iteration,
        )

        return {
            "best_iteration": self._best_iteration,
            "val_rmse": val_rmse,
            "backend": self._backend,
        }

    def predict(
        self,
        bean_profile: BeanProfile,
        recipe: Recipe,
        user_id: str | None = None,
        **user_features: float,
    ) -> PredictionResult:
        """Predict rating for a bean+recipe combination."""
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() or load() first.")

        features = self._encoder.encode(bean_profile, recipe, **user_features)
        base_pred = float(self._model.predict(features.reshape(1, -1))[0])

        user_bias = self._get_user_bias(user_id)
        predicted = float(np.clip(base_pred + user_bias, 1.0, 10.0))

        ci_half = min(1.5, self._val_std * 0.5)
        ci_lower = float(np.clip(predicted - ci_half, 1.0, 10.0))
        ci_upper = float(np.clip(predicted + ci_half, 1.0, 10.0))

        importance = self._top_features(features)

        logger.info(
            "model.predict predicted_rating=%.1f user_id=%s user_bias=%.3f",
            round(predicted, 1), user_id, round(user_bias, 3),
        )

        return PredictionResult(
            predicted_rating=round(predicted, 1),
            confidence_interval=(round(ci_lower, 1), round(ci_upper, 1)),
            user_bias=round(user_bias, 3),
            base_prediction=round(base_pred, 1),
            feature_importance=importance,
        )

    def predict_batch(
        self,
        features_array: np.ndarray,
        user_ids: list[str | None] | None = None,
    ) -> np.ndarray:
        """Predict ratings for a batch of feature arrays."""
        if not self.is_trained:
            raise RuntimeError("Model not trained.")
        base_preds = self._model.predict(features_array)
        if user_ids is not None:
            biases = np.array([self._get_user_bias(uid) for uid in user_ids])
            base_preds = base_preds + biases
        return np.clip(base_preds, 1.0, 10.0)

    def update_user_bias(
        self,
        user_id: str,
        features: np.ndarray,
        actual_rating: float,
        n_prior_ratings: int,
    ):
        """Update per-user bias after observing a new rating."""
        if not self.is_trained:
            return
        base_pred = float(self._model.predict(features.reshape(1, -1))[0])
        residual = actual_rating - base_pred

        if n_prior_ratings <= 4:
            weight = 0.3
            old_bias = self._user_biases.get(user_id, 0.0)
            self._user_biases[user_id] = old_bias * (1 - weight) + residual * weight
        else:
            old_bias = self._user_biases.get(user_id, 0.0)
            decay = 0.8
            self._user_biases[user_id] = old_bias * decay + residual * (1 - decay)

    def _get_user_bias(self, user_id: str | None) -> float:
        if user_id is None:
            return 0.0
        return self._user_biases.get(user_id, 0.0)

    def _top_features(self, features: np.ndarray) -> dict[str, float]:
        """Get top 10 features by importance."""
        if self._model is None:
            return {}
        importances = self._model.feature_importances_
        abs_imp = np.abs(importances)
        top_indices = np.argsort(abs_imp)[-10:][::-1]
        total = abs_imp.sum() if abs_imp.sum() > 0 else 1.0
        return {
            FEATURE_NAMES[i]: round(float(abs_imp[i] / total), 4)
            for i in top_indices
            if i < len(FEATURE_NAMES)
        }

    def save(self, path: Path | None = None):
        """Save model, encoder state, and biases to disk with hash verification."""
        path = path or MODELS_DIR
        logger.info("model.save path=%s", path)
        path.mkdir(parents=True, exist_ok=True)

        model_path = path / "taste_predictor.joblib"
        encoder_path = path / "feature_encoder.joblib"

        joblib.dump(self._model, model_path)
        joblib.dump(self._encoder, encoder_path)

        model_hash = _sha256_file(model_path)
        encoder_hash = _sha256_file(encoder_path)

        with open(path / "user_biases.json", "w") as f:
            json.dump(self._user_biases, f, indent=2)
        meta = {
            "global_mean": self._global_mean,
            "val_std": self._val_std,
            "trained": self._trained,
            "backend": self._backend,
            "best_iteration": self._best_iteration,
            "model_sha256": model_hash,
            "encoder_sha256": encoder_hash,
        }
        with open(path / "training_metadata.json", "w") as f:
            json.dump(meta, f, indent=2)

    def load(self, path: Path | None = None):
        """Load model, encoder state, and biases from disk with hash verification."""
        path = path or MODELS_DIR
        logger.info("model.load path=%s", path)

        model_path = path / "taste_predictor.joblib"
        encoder_path = path / "feature_encoder.joblib"

        # Verify hashes before deserialization to prevent arbitrary code execution
        with open(path / "training_metadata.json") as f:
            meta = json.load(f)

        expected_model_hash = meta.get("model_sha256")
        expected_encoder_hash = meta.get("encoder_sha256")

        if expected_model_hash:
            actual_hash = _sha256_file(model_path)
            if actual_hash != expected_model_hash:
                raise ValueError(
                    f"Model file hash mismatch. Expected {expected_model_hash[:16]}..., "
                    f"got {actual_hash[:16]}... The file may have been tampered with."
                )

        if expected_encoder_hash:
            actual_hash = _sha256_file(encoder_path)
            if actual_hash != expected_encoder_hash:
                raise ValueError(
                    f"Encoder file hash mismatch. Expected {expected_encoder_hash[:16]}..., "
                    f"got {actual_hash[:16]}... The file may have been tampered with."
                )

        self._model = joblib.load(model_path)
        self._encoder = joblib.load(encoder_path)
        with open(path / "user_biases.json") as f:
            self._user_biases = json.load(f)
        self._global_mean = meta["global_mean"]
        self._val_std = meta["val_std"]
        self._trained = meta["trained"]
        self._backend = meta.get("backend", "sklearn")
        self._best_iteration = meta.get("best_iteration", 0)
