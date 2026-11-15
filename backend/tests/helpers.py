"""Shared test fixtures: synthetic OHLCV frames and hand-built IR series."""

import pandas as pd

from market_band.config import BEATS_PER_BAR
from market_band.ir import IRBar, IRBeat, IRSeries


def make_frame(closes: list[float], volumes: list[float]) -> pd.DataFrame:
    """Daily OHLCV rows with a 2% daily range around each close."""
    return pd.DataFrame(
        {
            "date": [f"2020-01-{i + 1:02d}" for i in range(len(closes))],
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "adj_close": closes,
            "volume": volumes,
        }
    )


def ir_with_activity(values: list[float]) -> IRSeries:
    """An IR with the given activity per beat; every other channel and every mood at 0.5."""
    assert len(values) % BEATS_PER_BAR == 0, "values must fill whole bars"
    beats = [
        IRBeat(date=f"d{i}", level=0.5, swing=0.5, activity=value, intensity=0.5)
        for i, value in enumerate(values)
    ]
    bars = [IRBar(mood=0.5) for _ in range(len(values) // BEATS_PER_BAR)]
    return IRSeries(source="T", beats=beats, bars=bars)
