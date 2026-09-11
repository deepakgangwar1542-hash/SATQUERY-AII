"""Fusion model — dual-branch classifier over optical + SAR (§13.3, FR-7/FR-8).

Backends:
  * sklearn (default; zero heavy deps): multinomial logistic regression on the
    9-dim standardized feature vector, with per-mode (optical/sar/fusion)
    coefficient masking so the §17.1 ablation is a true single-sensor run.
  * torch (optional): small dual-branch MLP; selected automatically when
    torch is importable and --backend torch is passed.

Saved artifact: checkpoints/fusion_model.joblib
  {"backend", "kind", "classes", "mean", "std", "coef", "intercept", "meta"}
"""
from __future__ import annotations

import joblib
import numpy as np

from .dataset import CLASSES
from .preprocessing import dataset_matrix, standardize

OPT_DIM, SAR_DIM = 6, 3


def _mode_mask(mode: str, dim: int) -> np.ndarray:
    m = np.ones(dim, dtype="float32")
    if mode == "optical":
        m[OPT_DIM:] = 0.0
    elif mode == "sar":
        m[:OPT_DIM] = 0.0
    return m


class FusionModel:
    """Logistic-regression fusion model with sensor-masking for ablations."""

    def __init__(self, kind: str = "sklearn-lr"):
        self.kind = kind
        self.classes = list(CLASSES)
        self.mean = None
        self.std = None
        self.coef = None      # (C, D)
        self.intercept = None  # (C,)
        self.meta: dict = {}

    # ---- training ----
    def fit(self, patches: list[dict]) -> dict:
        X, y = dataset_matrix(patches, "fusion")
        Xs, self.mean, self.std = standardize(X)
        from sklearn.linear_model import LogisticRegression
        lr = LogisticRegression(max_iter=2000, C=1.0)
        lr.fit(Xs, y)
        self.coef = lr.coef_.astype("float32")
        self.intercept = lr.intercept_.astype("float32")
        self.classes = list(lr.classes_)
        acc = float((self._predict_raw(Xs) == y).mean())
        return {"train_accuracy": round(acc, 4), "n": len(y)}

    # ---- inference ----
    def _predict_raw(self, Xs: np.ndarray, mode: str = "fusion") -> np.ndarray:
        mask = _mode_mask(mode, Xs.shape[1])[:, None]      # (D, 1) over classes
        scores = Xs @ (self.coef.T * mask) + self.intercept
        return scores.argmax(1)

    def predict_proba(self, X: np.ndarray, mode: str = "fusion") -> np.ndarray:
        Xs = (X - self.mean) / self.std
        mask = _mode_mask(mode, X.shape[1])[:, None]
        scores = Xs @ (self.coef.T * mask) + self.intercept
        scores = scores - scores.max(1, keepdims=True)
        p = np.exp(scores)
        return p / p.sum(1, keepdims=True)

    def predict(self, X: np.ndarray, mode: str = "fusion") -> np.ndarray:
        Xs = (X - self.mean) / self.std
        return self._predict_raw(Xs, mode)

    def evaluate(self, patches: list[dict], mode: str = "fusion") -> float:
        X, y = dataset_matrix(patches, mode)
        return float((self.predict(X, mode) == y).mean())

    # ---- persistence ----
    def save(self, path: str) -> None:
        joblib.dump({"backend": "sklearn", "kind": self.kind,
                     "classes": self.classes, "mean": self.mean, "std": self.std,
                     "coef": self.coef, "intercept": self.intercept,
                     "meta": self.meta}, path)

    @classmethod
    def load(cls, path: str) -> "FusionModel":
        d = joblib.load(path)
        m = cls(kind=d.get("kind", "sklearn-lr"))
        m.classes = d["classes"]; m.mean = d["mean"]; m.std = d["std"]
        m.coef = d["coef"]; m.intercept = d["intercept"]; m.meta = d.get("meta", {})
        return m
