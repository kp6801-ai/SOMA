"""
transition_model.py — LightGBM-based DJ transition quality predictor.

Predicts P(good transition) for a pair of tracks based on audio features.
Works alongside the rule-based transitions.py scorer — replaces the
neutral 0.5 fallback for track pairs with no DJ history.

Usage (in transitions.py):
    from transition_model import get_model
    model = get_model()
    if model.is_loaded():
        learned = model.predict(track_a, track_b)
"""

import logging
import os
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

# Path where trained model is saved
DEFAULT_MODEL_PATH = str(Path(__file__).parent / "models" / "transition_model.pkl")


def _camelot_distance(a: str, b: str) -> int:
    """Inline camelot distance to avoid circular imports."""
    if not a or not b or a in ("?", "Unknown") or b in ("?", "Unknown"):
        return 3
    try:
        mode_a, mode_b = a[-1], b[-1]
        num_a, num_b = int(a[:-1]), int(b[:-1])
        if mode_a != mode_b:
            return 2
        return min(abs(num_a - num_b), 12 - abs(num_a - num_b))
    except Exception:
        return 3


FEATURE_NAMES = [
    "bpm_delta",
    "bpm_ratio",
    "bpm_a",
    "bpm_b",
    "key_distance",
    "same_key_flag",
    "energy_delta",
    "energy_ratio",
    "energy_a",
    "energy_b",
    "mfcc_cosine_sim",
    "has_mfcc",
    "spectral_centroid_delta",
    "brightness_delta",
    "danceability_delta",
    "rhythm_strength_delta",
    "onset_rate_delta",
    "loudness_delta",
    "energy_tag_match",
    "bpm_compatible_flag",
]


class TransitionModel:
    """LightGBM binary classifier for DJ transition quality."""

    def __init__(self):
        self._model = None
        self._model_path = DEFAULT_MODEL_PATH

    def is_loaded(self) -> bool:
        return self._model is not None

    def pair_features(self, track_a, track_b) -> np.ndarray:
        """
        Build 20-dim feature vector from two Track ORM objects (or dicts).
        Safe to call with partial/missing feature data.
        """
        def g(obj, attr, default=0.0):
            val = getattr(obj, attr, None) if not isinstance(obj, dict) else obj.get(attr)
            return float(val) if val is not None else default

        bpm_a = g(track_a, "bpm", 130.0)
        bpm_b = g(track_b, "bpm", 130.0)
        bpm_delta = abs(bpm_a - bpm_b)
        bpm_ratio = bpm_b / bpm_a if bpm_a > 0 else 1.0

        camelot_a = (getattr(track_a, "camelot_code", None) or
                     (track_a.get("camelot_code") if isinstance(track_a, dict) else None) or "")
        camelot_b = (getattr(track_b, "camelot_code", None) or
                     (track_b.get("camelot_code") if isinstance(track_b, dict) else None) or "")
        key_dist = _camelot_distance(camelot_a, camelot_b)
        same_key = float(key_dist == 0)

        energy_a = g(track_a, "energy", 0.5)
        energy_b = g(track_b, "energy", 0.5)
        energy_delta = abs(energy_a - energy_b)
        energy_ratio = energy_b / energy_a if energy_a > 0 else 1.0

        # MFCC cosine similarity
        mfcc_a = getattr(track_a, "mfcc_vector", None) or (track_a.get("mfcc_vector") if isinstance(track_a, dict) else None)
        mfcc_b = getattr(track_b, "mfcc_vector", None) or (track_b.get("mfcc_vector") if isinstance(track_b, dict) else None)
        has_mfcc = float(mfcc_a is not None and mfcc_b is not None and len(mfcc_a) == len(mfcc_b))
        mfcc_sim = 0.5
        if has_mfcc:
            va = np.array(mfcc_a, dtype=np.float32)
            vb = np.array(mfcc_b, dtype=np.float32)
            na, nb = np.linalg.norm(va), np.linalg.norm(vb)
            if na > 0 and nb > 0:
                mfcc_sim = float(np.dot(va, vb) / (na * nb))

        sc_a = g(track_a, "spectral_centroid", 0.0)
        sc_b = g(track_b, "spectral_centroid", 0.0)
        br_a = g(track_a, "brightness", 0.0)
        br_b = g(track_b, "brightness", 0.0)
        da_a = g(track_a, "danceability", 0.0)
        da_b = g(track_b, "danceability", 0.0)
        rs_a = g(track_a, "rhythm_strength", 0.0)
        rs_b = g(track_b, "rhythm_strength", 0.0)
        or_a = g(track_a, "onset_rate", 0.0)
        or_b = g(track_b, "onset_rate", 0.0)
        lo_a = g(track_a, "loudness", 0.0)
        lo_b = g(track_b, "loudness", 0.0)

        etag_a = getattr(track_a, "energy_tag", None) or (track_a.get("energy_tag") if isinstance(track_a, dict) else None)
        etag_b = getattr(track_b, "energy_tag", None) or (track_b.get("energy_tag") if isinstance(track_b, dict) else None)
        energy_tag_match = float(etag_a is not None and etag_a == etag_b)

        bpm_compatible = float(bpm_delta <= 5 and key_dist <= 1)

        return np.array([
            bpm_delta,
            bpm_ratio,
            bpm_a,
            bpm_b,
            float(key_dist),
            same_key,
            energy_delta,
            energy_ratio,
            energy_a,
            energy_b,
            mfcc_sim,
            has_mfcc,
            abs(sc_a - sc_b),
            abs(br_a - br_b),
            abs(da_a - da_b),
            abs(rs_a - rs_b),
            abs(or_a - or_b),
            abs(lo_a - lo_b),
            energy_tag_match,
            bpm_compatible,
        ], dtype=np.float32)

    def predict(self, track_a, track_b) -> float:
        """Predict transition quality 0.0–1.0. Falls back to rule-based if model not loaded."""
        if not self.is_loaded():
            return self._fallback_score(track_a, track_b)

        features = self.pair_features(track_a, track_b).reshape(1, -1)
        try:
            prob = self._model.predict_proba(features)[0][1]
            return float(np.clip(prob, 0.0, 1.0))
        except Exception as e:
            log.warning(f"Model predict error: {e}, using fallback")
            return self._fallback_score(track_a, track_b)

    def predict_batch(self, pairs: list[tuple]) -> list[float]:
        """Batch predict for a list of (track_a, track_b) tuples."""
        if not pairs:
            return []
        if not self.is_loaded():
            return [self._fallback_score(a, b) for a, b in pairs]

        X = np.stack([self.pair_features(a, b) for a, b in pairs])
        probs = self._model.predict_proba(X)[:, 1]
        return [float(p) for p in np.clip(probs, 0.0, 1.0)]

    def _fallback_score(self, track_a, track_b) -> float:
        """Rule-based score when model not loaded."""
        def g(obj, attr, default=0.0):
            val = getattr(obj, attr, None) if not isinstance(obj, dict) else obj.get(attr)
            return float(val) if val is not None else default

        bpm_a = g(track_a, "bpm", 130.0)
        bpm_b = g(track_b, "bpm", 130.0)
        bpm_delta = abs(bpm_a - bpm_b)
        bpm_score = max(0.0, 1.0 - bpm_delta / 20.0)

        camelot_a = getattr(track_a, "camelot_code", "") or ""
        camelot_b = getattr(track_b, "camelot_code", "") or ""
        key_dist = _camelot_distance(camelot_a, camelot_b)
        key_score = {0: 1.0, 1: 0.85, 2: 0.5, 3: 0.2}.get(key_dist, 0.05)

        return 0.5 * bpm_score + 0.5 * key_score

    def train(self, pairs: list[dict]) -> dict:
        """
        Train model on labeled pairs.
        pairs: [{track_a: Track, track_b: Track, label: int (0/1)}, ...]
        Returns metrics dict.
        """
        try:
            import lightgbm as lgb
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import roc_auc_score, accuracy_score
        except ImportError:
            log.error("Install lightgbm and scikit-learn: pip install lightgbm scikit-learn")
            return {"error": "lightgbm not installed"}

        if len(pairs) < 10:
            return {"error": f"Need at least 10 pairs, got {len(pairs)}"}

        X = np.stack([self.pair_features(p["track_a"], p["track_b"]) for p in pairs])
        y = np.array([p["label"] for p in pairs], dtype=np.int32)

        n_pos = int(y.sum())
        n_neg = len(y) - n_pos
        log.info(f"Training on {len(pairs)} pairs ({n_pos} positive, {n_neg} negative)")

        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y if n_pos > 1 else None
        )

        model = lgb.LGBMClassifier(
            n_estimators=200,
            learning_rate=0.05,
            num_leaves=31,
            max_depth=6,
            min_child_samples=5,
            subsample=0.8,
            colsample_bytree=0.8,
            class_weight="balanced",
            random_state=42,
            verbose=-1,
        )
        model.fit(X_train, y_train,
                  eval_set=[(X_val, y_val)],
                  callbacks=[lgb.early_stopping(20, verbose=False), lgb.log_evaluation(period=-1)])

        self._model = model

        y_pred_proba = model.predict_proba(X_val)[:, 1]
        y_pred = (y_pred_proba >= 0.5).astype(int)
        auc = roc_auc_score(y_val, y_pred_proba) if len(set(y_val)) > 1 else 0.0
        acc = accuracy_score(y_val, y_pred)

        # Feature importance
        importances = sorted(
            zip(FEATURE_NAMES, model.feature_importances_),
            key=lambda x: x[1], reverse=True
        )

        metrics = {
            "n_train": len(X_train),
            "n_val": len(X_val),
            "n_positive": n_pos,
            "n_negative": n_neg,
            "val_auc": round(float(auc), 4),
            "val_accuracy": round(float(acc), 4),
            "top_features": importances[:5],
        }
        return metrics

    def save(self, path: str = DEFAULT_MODEL_PATH):
        if not self.is_loaded():
            raise ValueError("No model to save — train first")
        import pickle
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self._model, f)
        log.info(f"Model saved to {path}")

    def load(self, path: str = DEFAULT_MODEL_PATH):
        if not Path(path).exists():
            log.info(f"No trained model at {path} — using rule-based fallback")
            return
        import pickle
        with open(path, "rb") as f:
            self._model = pickle.load(f)
        log.info(f"Transition model loaded from {path}")


# Module-level singleton — load at import time if model file exists
_instance = TransitionModel()
_instance.load(DEFAULT_MODEL_PATH)


def get_model() -> TransitionModel:
    return _instance
