"""Intermediate representation (IR) and the raw-stock -> IR adapter.

The IR is source-agnostic: one row per beat, three channels each normalised to [0, 1].
Any future source (tweets, weather, ...) only needs its own adapter producing an
``IRSeries``; the music algorithm never sees source-specific fields.

- ``level``     -> pitch      (where the series is within its range)
- ``activity``  -> rhythm     (how agitated this beat is)
- ``intensity`` -> velocity + brightness (how much is happening)
"""

from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from market_band.config import MIN_BEATS

RAW_COLUMNS = ("date", "open", "high", "low", "close", "adj_close", "volume")
NEUTRAL = 0.5  # channel value when a series has no variation to normalise


class IRBeat(BaseModel):
    """One beat of the IR."""

    date: str
    level: float = Field(ge=0.0, le=1.0)
    activity: float = Field(ge=0.0, le=1.0)
    intensity: float = Field(ge=0.0, le=1.0)


class IRSeries(BaseModel):
    """A full IR series for one source over the demo period."""

    source: str
    beats: list[IRBeat] = Field(min_length=MIN_BEATS)


def load_raw_stock(path: Path) -> pd.DataFrame:
    """Read a cached OHLCV CSV and validate its shape and values."""
    if not path.is_file():
        raise FileNotFoundError(f"raw data missing: {path} (run `uv run market-band-fetch`)")
    frame = pd.read_csv(path)
    missing = set(RAW_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"{path.name}: missing columns {sorted(missing)}")
    if len(frame) < MIN_BEATS:
        raise ValueError(f"{path.name}: {len(frame)} rows, need at least {MIN_BEATS}")
    if frame[list(RAW_COLUMNS[1:])].isna().to_numpy().any():
        raise ValueError(f"{path.name}: contains NaN values")
    return frame


def min_max(values: pd.Series) -> pd.Series:
    """Scale values linearly onto [0, 1]; a flat series maps to NEUTRAL."""
    assert len(values) > 0, "cannot normalise an empty series"
    low, high = float(values.min()), float(values.max())
    if high == low:
        return pd.Series(NEUTRAL, index=values.index)
    return (values - low) / (high - low)


def percentile_rank(values: pd.Series) -> pd.Series:
    """Rank values onto [0, 1] (lowest -> 0, highest -> 1); a flat series maps to NEUTRAL."""
    assert len(values) > 0, "cannot rank an empty series"
    if values.nunique() == 1:
        return pd.Series(NEUTRAL, index=values.index)
    ranks = values.rank(method="average")
    return (ranks - 1.0) / (len(values) - 1.0)


def stock_to_ir(source: str, frame: pd.DataFrame) -> IRSeries:
    """Translate validated daily OHLCV rows into an IR series.

    level     = min-max of log adjusted close over the window (matches the price chart)
    activity  = percentile rank of the daily range (high - low) / close
    intensity = percentile rank of volume
    """
    if (frame[["open", "high", "low", "close", "adj_close"]] <= 0).to_numpy().any():
        raise ValueError(f"{source}: prices must be positive")
    if (frame["high"] < frame["low"]).any():
        raise ValueError(f"{source}: high below low on some rows")

    level = min_max(pd.Series(np.log(frame["adj_close"].to_numpy()), index=frame.index))
    activity = percentile_rank((frame["high"] - frame["low"]) / frame["close"])
    intensity = percentile_rank(frame["volume"].astype(float))

    beats = [
        IRBeat(date=str(date), level=float(lv), activity=float(ac), intensity=float(it))
        for date, lv, ac, it in zip(frame["date"], level, activity, intensity, strict=True)
    ]
    return IRSeries(source=source, beats=beats)
