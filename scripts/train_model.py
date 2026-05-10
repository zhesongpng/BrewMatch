"""Train the BrewMatch taste prediction model on synthetic data.

NOTE: Synthetic data provides bean/recipe features but zero real user
interaction signals. User features (avg_rating, roast_pref, temp_pref,
grind_pref, ratio_pref, acidity/body/sweetness bias) are all zero-filled.
Personalization phases 2-4 (directional, content-based, full hybrid)
require real user brewing history to produce meaningful predictions.
The model trained here establishes the baseline bean_aware phase only.

Usage: uv run python scripts/train_model.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data_models import FLAVOR_CLUSTERS, Process, RoastLevel
from src.taste_predictor.encoder import ORIGIN_MAP, ROAST_ORDINAL
from src.taste_predictor.model import MODELS_DIR, TastePredictor

DATA_DIR = ROOT / "data" / "synthetic"

ORIGIN_MAP_LOWER = {k.lower(): v for k, v in ORIGIN_MAP.items()}
PROCESS_MAP = {p.value: i for i, p in enumerate([Process.WASHED, Process.NATURAL, Process.HONEY, Process.ANAEROBIC])}
ROAST_MAP = {
    "light": 1.0, "medium-light": 2.0, "medium": 3.0,
    "medium-dark": 4.0, "dark": 5.0,
}
CLUSTER_SET = set(FLAVOR_CLUSTERS)


def _encode_row_raw(row: dict) -> np.ndarray | None:
    """Encode a CSV row into a 45-element feature vector directly."""
    try:
        features = [0.0] * 45

        # [0] origin
        origin = str(row.get("origin_country", "")).strip()
        features[0] = float(ORIGIN_MAP_LOWER.get(origin.lower(), 0))

        # [1-5] process one-hot
        process = str(row.get("process", "unknown")).strip()
        if process in PROCESS_MAP:
            features[1 + PROCESS_MAP[process]] = 1.0
        elif process in ("wet-hulled", "unknown"):
            features[5] = 1.0

        # [6] roast ordinal
        roast = str(row.get("roast_level", "medium")).strip()
        features[6] = ROAST_MAP.get(roast, 3.0)

        # [7-21] flavor clusters
        clusters_str = str(row.get("flavor_clusters", "Balanced"))
        clusters = [c.strip() for c in clusters_str.split("|") if c.strip()]
        if not clusters:
            clusters = ["Balanced"]
        for c in clusters:
            if c in CLUSTER_SET:
                idx = FLAVOR_CLUSTERS.index(c)
                features[7 + idx] = 1.0
            else:
                features[7 + FLAVOR_CLUSTERS.index("Balanced")] = 1.0

        # [22] altitude mean
        alt = row.get("altitude_min_m")
        features[22] = float(alt) if pd.notna(alt) else 0.0

        # [23-29] recipe features
        features[23] = float(row["dose_g"])
        features[24] = float(row["ratio"])
        features[25] = float(row["grind_setting"])
        features[26] = float(row["water_temp_c"])
        features[27] = float(row["bloom_time_s"])
        features[28] = float(row["total_time_s"])
        features[29] = float(row.get("pour_count", 4))

        # [39-44] interaction features
        features[39] = features[6] * features[26]  # roast_x_temp
        features[40] = features[25] * features[28]  # grind_x_time
        features[41] = features[25] * features[26]  # grind_x_temp
        features[42] = features[24] * features[23]  # ratio_x_dose
        features[43] = features[6] * features[25]   # roast_x_grind
        features[44] = sum(features[7:22])           # cluster_count

        return np.array(features, dtype=np.float64)
    except (KeyError, ValueError, TypeError):
        return None


def load_and_encode() -> tuple[np.ndarray, np.ndarray]:
    ratings_path = DATA_DIR / "ratings.csv"
    if not ratings_path.exists():
        print(f"ERROR: {ratings_path} not found. Run data generator first.")
        sys.exit(1)

    df = pd.read_csv(ratings_path)
    print(f"Loaded {len(df)} rows from {ratings_path}")

    X_list, y_list = [], []
    skipped = 0
    for _, row in df.iterrows():
        vec = _encode_row_raw(row)
        if vec is not None:
            X_list.append(vec)
            y_list.append(float(row["rating"]))
        else:
            skipped += 1

    X = np.array(X_list, dtype=np.float64)
    y = np.array(y_list, dtype=np.float64)
    print(f"Encoded {len(X)}/{len(df)} rows (skipped {skipped}) -> shape {X.shape}")
    return X, y


def train_model() -> TastePredictor:
    X, y = load_and_encode()

    # 70/15/15 stratified split
    y_bins = pd.qcut(y, q=5, labels=False, duplicates="drop")
    X_train_val, X_test, y_train_val, y_test = train_test_split(
        X, y, test_size=0.15, random_state=42, stratify=y_bins,
    )
    y_bins_tv = pd.qcut(y_train_val, q=5, labels=False, duplicates="drop")
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_val, y_train_val, test_size=0.176, random_state=42, stratify=y_bins_tv,
    )

    print(f"Split: train={len(X_train)}, val={len(X_val)}, test={len(X_test)}")

    predictor = TastePredictor()
    result = predictor.train(X_train, y_train, X_val, y_val)
    print(f"Training complete. Backend: {result['backend']}, "
          f"Best iteration: {result['best_iteration']}, "
          f"Val RMSE: {result['val_rmse']:.4f}")

    y_pred = predictor.predict_batch(X_test)
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    mae = float(mean_absolute_error(y_test, y_pred))
    r2 = float(r2_score(y_test, y_pred))

    print(f"\nTest set results:")
    print(f"  RMSE:  {rmse:.4f} (target < 1.5)")
    print(f"  MAE:   {mae:.4f} (target < 1.0)")
    print(f"  R^2:   {r2:.4f} (target > 0.5)")

    target_status = []
    if rmse < 1.5:
        target_status.append("RMSE PASS")
    else:
        target_status.append("RMSE MISS")
    if mae < 1.0:
        target_status.append("MAE PASS")
    else:
        target_status.append("MAE MISS")
    if r2 > 0.5:
        target_status.append("R2 PASS")
    else:
        target_status.append("R2 MISS")
    print(f"  Targets: {', '.join(target_status)}")

    predictor.save()
    print(f"\nModel saved to {MODELS_DIR}/")

    loaded = TastePredictor()
    loaded.load()
    y_loaded = loaded.predict_batch(X_test[:5])
    y_orig = predictor.predict_batch(X_test[:5])
    assert np.allclose(y_loaded, y_orig), "Save/load round-trip mismatch!"
    print("Save/load round-trip verified.")

    return predictor


if __name__ == "__main__":
    train_model()
