import numpy as np
import pandas as pd


def _clip(p):
    return np.clip(np.asarray(p, dtype=float), 1e-9, 1 - 1e-9)


def log_loss(p, y) -> float:
    p, y = _clip(p), np.asarray(y, dtype=float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def brier(p, y) -> float:
    return float(np.mean((np.asarray(p, dtype=float) - np.asarray(y, dtype=float)) ** 2))


def accuracy(p, y) -> float:
    return float(np.mean((np.asarray(p) > 0.5) == np.asarray(y).astype(bool)))


def calibration_table(p, y, bins: int = 10) -> pd.DataFrame:
    df = pd.DataFrame({"p": np.asarray(p, dtype=float), "y": np.asarray(y, dtype=float)})
    df["bin"] = pd.cut(df["p"], np.linspace(0, 1, bins + 1), include_lowest=True)
    return (
        df.groupby("bin", observed=True)
        .agg(mean_pred=("p", "mean"), observed=("y", "mean"), n=("y", "size"))
        .reset_index()
    )


def symmetric(p_winner) -> tuple[np.ndarray, np.ndarray]:
    """Sackmann rows always list the winner first, so p_winner alone has y == 1 everywhere.
    Score both orientations so metrics aren't trivially biased."""
    p = np.asarray(p_winner, dtype=float)
    return np.concatenate([p, 1 - p]), np.concatenate([np.ones_like(p), np.zeros_like(p)])
