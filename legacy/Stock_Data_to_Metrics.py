"""Configurable OHLCV -> multi-instrument musical-event CSV. Python 3.10+.
Run: pip install -r requirements-stock-music.txt
     python Stock_Data_to_Metrics.py
No audio/MIDI generated. Timestamp means candle START, in one consistent timezone.
Daily timestamps are trading-session labels. End date filters are exclusive.
"""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
CONFIG = {
    "input": ROOT / "data/sp500_2008_10_daily.csv",
    "output": ROOT / "data/stock_music_events.csv",
    "base_interval": "1D",  # actual source candle size; never upsample
    "beats_per_source_candle": 2.0,
    "bpm": 100,
    "volume_window": 20,
    "pitch_metric": "return_pct",
    "rhythm_metric": "range_pct",
    "velocity_metric": "relative_volume",
    "tracks": [
        {"name": "daily_guitar", "instrument": "acoustic_guitar", "rule": "1D",
         "pitch_range": (60, 84), "pitch_limits": (-0.10, 0.10), "range_limit": 0.12},
        {"name": "weekly_strings", "instrument": "strings", "rule": "W-MON",
         "pitch_range": (48, 72), "pitch_limits": (-0.25, 0.25), "range_limit": 0.30},
        {"name": "monthly_bass", "instrument": "bass", "rule": "MS",
         "pitch_range": (28, 48), "pitch_limits": (-0.40, 0.40), "range_limit": 0.50},
    ],
}


def read_data(path):
    frame = pd.read_csv(path)
    frame.columns = frame.columns.str.strip().str.lower()
    if "timestamp" not in frame and "date" in frame:
        frame = frame.rename(columns={"date": "timestamp"})
    if "symbol" not in frame:
        frame["symbol"] = "UNKNOWN"
    required = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]
    if set(required) - set(frame):
        raise ValueError(f"Required columns: {required}")
    frame = frame[required].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="raise", utc=True)
    if frame[required].isna().any().any() or frame.empty:
        raise ValueError("Input is empty or contains missing values")
    for column in required[2:]:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    values = frame[required[2:]]
    if not np.isfinite(values.to_numpy()).all():
        raise ValueError("Non-finite OHLCV values")
    if (frame[["open", "high", "low", "close"]] <= 0).any().any() or (frame.volume < 0).any():
        raise ValueError("Prices must be positive and volume nonnegative")
    if ((frame.high < frame[["open", "close", "low"]].max(axis=1)) |
        (frame.low > frame[["open", "close", "high"]].min(axis=1))).any():
        raise ValueError("Invalid OHLC ordering")
    if frame.duplicated(["symbol", "timestamp"]).any():
        raise ValueError("Duplicate symbol/timestamp rows")
    return frame.sort_values(["symbol", "timestamp"])


def metrics(candles, window):
    """Edit here to add metrics; returns/ranges are fractions, not percentage points."""
    result = candles.copy()
    result["return_pct"] = result.close / result.open - 1
    result["range_pct"] = (result.high - result.low) / result.open
    # Compare average activity per input candle, avoiding unequal week/month lengths.
    activity = result.volume / result.source_count
    baseline = activity.shift(1).rolling(window, min_periods=1).mean()
    result["relative_volume"] = (activity / baseline.replace(0, np.nan)).fillna(1.0)
    return result


def unit(value, limits):
    low, high = limits
    if high <= low:
        raise ValueError("Mapping upper limit must exceed lower limit")
    return float(np.clip((value - low) / (high - low), 0, 1))


def build_events(frame, config):
    """One row per note; all symbols/tracks share a compressed trading-time axis.
    Weekends/overnights absent from the source have no added silence. Missing bars
    are NOT fabricated. Partial edge weeks/months use only available source rows.
    """
    base = pd.Timedelta(config["base_interval"])
    timeline = sorted(frame.timestamp.unique())
    positions = {time: i for i, time in enumerate(timeline)}
    frame = frame.copy()
    frame["position"] = frame.timestamp.map(positions)
    for _, group in frame.groupby("symbol"):
        differences = group.timestamp.diff().dropna()
        if (differences < base).any():
            raise ValueError("Source timestamps are closer than base_interval")
    events = []
    for symbol, group in frame.groupby("symbol", sort=True):
        source = group.set_index("timestamp")
        for track in config["tracks"]:
            offset = pd.tseries.frequencies.to_offset(track["rule"])
            try:
                if pd.Timedelta(offset.nanos, unit="ns") < base:
                    raise ValueError("Cannot create candles shorter than source data")
            except ValueError as error:
                if "non-fixed" not in str(error):
                    raise
                if base > pd.Timedelta(days=1):
                    raise ValueError("Calendar aggregation requires daily or finer input") from error
            candles = source.resample(track["rule"], closed="left", label="left").agg(
                open=("open", "first"), high=("high", "max"), low=("low", "min"),
                close=("close", "last"), volume=("volume", "sum"),
                source_count=("close", "count"), first_position=("position", "min"),
                last_position=("position", "max"))
            candles = metrics(candles[candles.source_count > 0], config["volume_window"])
            for timestamp, candle in candles.iterrows():
                pitch = int(round(np.interp(
                    unit(candle[config["pitch_metric"]], track["pitch_limits"]),
                    [0, 1], track["pitch_range"])))
                intensity = unit(candle[config["rhythm_metric"]], (0, track["range_limit"]))
                repeats = (1, 2, 4, 8)[min(3, int(intensity * 4))]
                velocity = int(round(35 + 92 * unit(candle[config["velocity_metric"]], (0, 3))))
                start = candle.first_position * config["beats_per_source_candle"]
                span = (candle.last_position + 1 - candle.first_position) * config["beats_per_source_candle"]
                for note in range(repeats):
                    beat = start + note * span / repeats
                    duration = 0.9 * span / repeats
                    events.append({"symbol": symbol, "track": track["name"],
                        "instrument": track["instrument"], "candle_interval": track["rule"],
                        "candle_start": timestamp.isoformat(), **candle.to_dict(),
                        "pitch_midi": pitch, "rhythm_subdivisions": repeats,
                        "velocity": velocity, "start_beat": beat, "duration_beats": duration,
                        "bpm": config["bpm"], "start_seconds": beat * 60 / config["bpm"],
                        "duration_seconds": duration * 60 / config["bpm"]})
    if not events:
        raise ValueError("No events produced")
    return pd.DataFrame(events).sort_values(["start_beat", "symbol", "track"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(CONFIG["input"]))
    parser.add_argument("--output", default=str(CONFIG["output"]))
    parser.add_argument("--symbols", nargs="+", help="Optional exact symbols to select")
    parser.add_argument("--start", help="Inclusive date/time")
    parser.add_argument("--end", help="Exclusive date/time")
    args = parser.parse_args()
    frame = read_data(args.input)
    if args.symbols:
        frame = frame[frame.symbol.isin(args.symbols)]
    if args.start:
        frame = frame[frame.timestamp >= pd.to_datetime(args.start, utc=True)]
    if args.end:
        frame = frame[frame.timestamp < pd.to_datetime(args.end, utc=True)]
    if frame.empty:
        raise ValueError("No data matches filters")
    events = build_events(frame, CONFIG)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(destination, index=False, float_format="%.8f")
    print(f"Saved {len(events)} note events to {destination}")


if __name__ == "__main__":
    main()
