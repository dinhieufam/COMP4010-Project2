from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.config import INTERIM_DIR, REPORTS_DIR, ensure_dirs
from pipeline.io import write_parquet

_LOG = logging.getLogger(__name__)


def _linear_forecast(counts: np.ndarray, horizon: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(counts)
    idx = np.arange(n, dtype=float)
    if n >= 2:
        slope, intercept = np.polyfit(idx, counts, 1)
        resid_std = float(np.std(counts - (slope * idx + intercept))) if n > 2 else 1.0
    else:
        slope, intercept, resid_std = 0.0, float(counts[-1] if n else 0), 1.0
    future_idx = np.arange(n, n + horizon, dtype=float)
    point = np.maximum(0.0, slope * future_idx + intercept)
    return point, np.maximum(0.0, point - 1.96 * resid_std), point + 1.96 * resid_std


def _fit_forecast(counts: np.ndarray, horizon: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (point, lower_95, upper_95) for `horizon` future steps.

    Tiered strategy:
    - n < 3: linear polyfit fallback
    - 3 <= n < 6: SimpleExpSmoothing (level only, stable with few points)
    - n >= 6: ExponentialSmoothing(trend='add') — Holt's linear method
    Falls back to linear if statsmodels raises.
    """
    from statsmodels.tsa.holtwinters import ExponentialSmoothing, SimpleExpSmoothing

    n = len(counts)
    if n < 3:
        return _linear_forecast(counts, horizon)

    try:
        if n < 6:
            model = SimpleExpSmoothing(counts, initialization_method="estimated")
            fit = model.fit(optimized=True)
        else:
            model = ExponentialSmoothing(counts, trend="add", initialization_method="estimated")
            fit = model.fit(optimized=True)
        point = np.maximum(0.0, fit.forecast(horizon))
        resid_std = float(np.std(fit.resid)) if len(fit.resid) > 1 else 1.0
        return point, np.maximum(0.0, point - 1.96 * resid_std), point + 1.96 * resid_std
    except Exception as exc:
        _LOG.debug("Holt-Winters failed (%s), using linear fallback.", exc)
        return _linear_forecast(counts, horizon)


def _backtest_mape(counts: np.ndarray, holdout: int = 2) -> float | None:
    """Hold out last `holdout` years, fit, forecast, return MAPE in percent."""
    from statsmodels.tsa.holtwinters import ExponentialSmoothing, SimpleExpSmoothing

    train = counts[:-holdout]
    test = counts[-holdout:]
    if len(train) < 3:
        return None
    try:
        if len(train) < 6:
            model = SimpleExpSmoothing(train, initialization_method="estimated")
        else:
            model = ExponentialSmoothing(train, trend="add", initialization_method="estimated")
        fit = model.fit(optimized=True)
        pred = np.maximum(0.0, fit.forecast(holdout))
        return float(np.mean(np.abs((test - pred) / np.maximum(test, 1)))) * 100
    except Exception:
        return None


def forecast_topic(topic_df: pd.DataFrame, horizon: int = 2) -> list[dict]:
    """Forecast future paper counts for a single topic using Holt-Winters."""
    topic_df = topic_df.sort_values("year")
    years = topic_df["year"].astype(int).to_numpy()
    counts = topic_df["paper_count"].astype(float).to_numpy()
    point, lower, upper = _fit_forecast(counts, horizon)
    rows = []
    for i, year in enumerate(range(int(years.max()) + 1, int(years.max()) + horizon + 1)):
        rows.append(
            {
                "venue": topic_df["venue"].iloc[0],
                "year": year,
                "topic_id": int(topic_df["topic_id"].iloc[0]),
                "topic_label": topic_df["topic_label"].iloc[0],
                "forecast_count": float(point[i]),
                "lower": float(lower[i]),
                "upper": float(upper[i]),
            }
        )
    return rows


def main() -> None:
    ensure_dirs()
    path = INTERIM_DIR / "topics.parquet"
    if not path.exists():
        raise RuntimeError("Missing data/interim/topics.parquet. Run 04_topic_modeling.py first.")

    papers = pd.read_parquet(path)
    topic_year = (
        papers.groupby(["venue", "year", "topic_id", "topic_label"], as_index=False)
        .agg(paper_count=("paper_id", "count"))
    )

    rows: list[dict] = []
    backtest_rows: list[dict] = []
    for _, topic_df in topic_year.groupby(["venue", "topic_id", "topic_label"], dropna=False):
        topic_df = topic_df.sort_values("year")
        counts = topic_df["paper_count"].astype(float).to_numpy()
        n = len(counts)

        rows.extend(forecast_topic(topic_df))

        mape = _backtest_mape(counts) if n >= 5 else None
        if n < 3:
            model_name = "linear"
        elif n < 6:
            model_name = "ses"
        else:
            model_name = "holt_winters_add"
        backtest_rows.append(
            {
                "topic_label": topic_df["topic_label"].iloc[0],
                "n_years": n,
                "model": model_name,
                "backtest_mape_pct": round(mape, 2) if mape is not None else None,
            }
        )

    write_parquet(pd.DataFrame(rows), INTERIM_DIR / "forecast.parquet")

    backtest_df = pd.DataFrame(backtest_rows).sort_values("topic_label")
    backtest_df.to_csv(REPORTS_DIR / "forecast_backtest.csv", index=False)

    print(f"Wrote {len(rows)} forecast rows.")
    valid_mapes = backtest_df["backtest_mape_pct"].dropna()
    if len(valid_mapes):
        print(f"Median MAPE across {len(valid_mapes)} topics with backtest: {valid_mapes.median():.1f}%")


if __name__ == "__main__":
    main()
