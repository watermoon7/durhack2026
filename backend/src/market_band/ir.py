"""Intermediate representation (IR) and the raw-stock -> IR adapter.

The IR is source-agnostic: one row per beat and one row per bar on a fixed song grid
(SONG_BEATS beats), every channel normalised to [0, 1]. Any future source (tweets,
weather, ...) only needs its own adapter producing an ``IRSeries``; the music algorithm
never sees source-specific fields.

Per beat:
- ``level``     -> register of the melody (where the series is within its range; per stock)
- ``swing``     -> melodic jumps (series minus its recent average, ranked; per stock)
- ``activity``  -> rhythm (how agitated this beat is; fixed scale)
- ``intensity`` -> velocity + brightness (how much is happening; fixed scale)

Per bar:
- ``mood``      -> chord (bar return on a fixed scale: 0 = falling hard, 1 = rising hard)
"""

from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from market_band.config import (
    ACTIVITY_RANGE_CAP,
    BEATS_PER_BAR,
    INTENSITY_VOLUME_CAP,
    MAX_RESAMPLE_RATIO,
    MIN_BEATS,
    MOOD_RETURN_BOUND,
    SONG_BEATS,
    SWING_WINDOW_BEATS,
)

RAW_COLUMNS = ("date", "open", "high", "low", "close", "adj_close", "volume")
NEUTRAL = 0.5  # channel value when a series has no variation to normalise


class IRBeat(BaseModel):
    """One beat of the IR."""

    date: str
    level: float = Field(ge=0.0, le=1.0)
    swing: float = Field(ge=0.0, le=1.0)
    activity: float = Field(ge=0.0, le=1.0)
    intensity: float = Field(ge=0.0, le=1.0)


class IRBar(BaseModel):
    """One bar of the IR."""

    mood: float = Field(ge=0.0, le=1.0)


class IRSeries(BaseModel):
    """A full IR series for one source, resampled onto the song grid."""

    source: str
    beats: list[IRBeat] = Field(min_length=MIN_BEATS)
    bars: list[IRBar] = Field(min_length=1)


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


def resample_frame(frame: pd.DataFrame, beats: int) -> pd.DataFrame:
    """Resample validated OHLCV rows onto ``beats`` evenly spaced points.

    Returns columns ``date`` (nearest source row), ``log_close``, ``range`` ((high - low) /
    close) and ``volume``, each linearly interpolated. Shrinking by more than
    MAX_RESAMPLE_RATIO is refused: that needs aggregation (max high, summed volume) instead.
    """
    rows = len(frame)
    if beats < MIN_BEATS:
        raise ValueError(f"need at least {MIN_BEATS} beats, got {beats}")
    if rows > beats * MAX_RESAMPLE_RATIO:
        raise ValueError(
            f"{rows} rows is more than {MAX_RESAMPLE_RATIO:g}x the {beats} beats; "
            "aggregate long datasets before resampling"
        )
    source_x = np.arange(rows, dtype=float)
    target_x = np.linspace(0.0, rows - 1.0, beats)
    columns = {
        "log_close": np.log(frame["adj_close"].to_numpy(dtype=float)),
        "range": ((frame["high"] - frame["low"]) / frame["close"]).to_numpy(dtype=float),
        "volume": frame["volume"].to_numpy(dtype=float),
    }
    nearest = np.rint(target_x).astype(int)
    resampled = {name: np.interp(target_x, source_x, values) for name, values in columns.items()}
    dates = frame["date"].astype(str).to_numpy()[nearest]
    return pd.DataFrame({"date": dates, **resampled})


def bar_moods(log_close: pd.Series, beats_per_bar: int) -> list[float]:
    """Map each bar's log return onto [0, 1]: 0 at -MOOD_RETURN_BOUND, 1 at +MOOD_RETURN_BOUND.

    A bar's return runs from the last beat of the previous bar to its own last beat; the
    first bar starts at its own first beat.
    """
    assert len(log_close) % beats_per_bar == 0, "beats must fill whole bars"
    assert MOOD_RETURN_BOUND > 0, "mood bound must be positive"
    values = log_close.to_numpy(dtype=float)
    ends = values[beats_per_bar - 1 :: beats_per_bar]
    starts = np.concatenate(([values[0]], ends[:-1]))
    returns = np.clip((ends - starts) / MOOD_RETURN_BOUND, -1.0, 1.0)
    return [float(r) / 2.0 + 0.5 for r in returns]


def scaled_channels(grid: pd.DataFrame) -> dict[str, pd.Series]:
    """Turn a resampled grid into the four per-beat channels, each in [0, 1]."""
    assert len(grid) > 0, "grid must not be empty"
    assert ACTIVITY_RANGE_CAP > 0 and INTENSITY_VOLUME_CAP > 0, "caps must be positive"
    log_close = grid["log_close"]
    trend = log_close.rolling(SWING_WINDOW_BEATS, min_periods=1).mean()
    median_volume = float(grid["volume"].median())
    if median_volume > 0:
        intensity = (grid["volume"] / median_volume / INTENSITY_VOLUME_CAP).clip(0.0, 1.0)
    else:
        intensity = pd.Series(NEUTRAL, index=grid.index)
    return {
        "level": min_max(log_close),
        "swing": percentile_rank((log_close - trend).round(9)),
        "activity": np.sqrt((grid["range"] / ACTIVITY_RANGE_CAP).clip(0.0, 1.0)),
        "intensity": intensity,
    }


def stock_to_ir(source: str, frame: pd.DataFrame, beats: int = SONG_BEATS) -> IRSeries:
    """Translate validated daily OHLCV rows into an IR series of exactly ``beats`` beats."""
    if beats % BEATS_PER_BAR != 0:
        raise ValueError(f"{beats} beats do not fill whole bars of {BEATS_PER_BAR}")
    if (frame[["open", "high", "low", "close", "adj_close"]] <= 0).to_numpy().any():
        raise ValueError(f"{source}: prices must be positive")
    if (frame["high"] < frame["low"]).any():
        raise ValueError(f"{source}: high below low on some rows")

    grid = resample_frame(frame, beats)
    channels = scaled_channels(grid)
    beat_rows = [
        IRBeat(
            date=str(date),
            level=float(level),
            swing=float(swing),
            activity=float(activity),
            intensity=float(intensity),
        )
        for date, level, swing, activity, intensity in zip(
            grid["date"],
            channels["level"],
            channels["swing"],
            channels["activity"],
            channels["intensity"],
            strict=True,
        )
    ]
    bars = [IRBar(mood=mood) for mood in bar_moods(grid["log_close"], BEATS_PER_BAR)]
    return IRSeries(source=source, beats=beat_rows, bars=bars)
