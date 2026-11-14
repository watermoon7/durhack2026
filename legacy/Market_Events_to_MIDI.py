"""Download SPY minute data and create ten 120-second MIDI sonifications.
Python 3.11+. pip install numpy pandas; python Market_Events_to_MIDI.py
Alternative: python Market_Events_to_MIDI.py --source your_minute_data.csv
"""
from pathlib import Path
import argparse, hashlib, struct, urllib.request, zipfile
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
SOURCE_URL = "https://www.kaggle.com/api/v1/datasets/download/gratefuldata/intraday-stock-data-1-min-sp-500-200821"
PROVENANCE = "https://www.kaggle.com/datasets/gratefuldata/intraday-stock-data-1-min-sp-500-200821"
# Context windows; start inclusive, end exclusive, in the source clock.
EVENTS = [
    ("2010_flash_crash", "2010-04-01", "2010-12-01"),
    ("2011_debt_ceiling_euro_crisis", "2011-04-01", "2012-04-01"),
    ("2013_taper_tantrum", "2013-04-01", "2013-10-01"),
    ("2015_china_devaluation", "2015-06-01", "2015-12-01"),
    ("2016_oil_growth_scare", "2015-12-01", "2016-06-01"),
    ("2016_brexit_us_equities", "2016-06-01", "2016-09-01"),
    ("2016_us_election", "2016-09-01", "2017-02-01"),
    ("2018_february_volatility", "2018-01-01", "2018-10-01"),
    ("2018_q4_selloff", "2018-09-01", "2019-06-01"),
    ("2020_covid_crash_rebound", "2019-12-01", "2021-03-01"),
]
BARS, BPM, TPB = 60, 120, 480
TRACKS = [("bass", 60, 0, 33, 28, 48),
          ("synth", 240, 1, 81, 55, 84),
          ("drums", 960, 9, None, 0, 0)]
EMA_SPAN, VOL_WINDOW, VOLUME_WINDOW = 12, 12, 20
MAX_DISPLACEMENT = 0.08  # Only offbeat hats/synth; strong beats stay fixed.
VELOCITY_MIN, VELOCITY_MAX = 35, 115
GRADIENT_QUANTILE = 0.95
SCALE_CLASSES = (0, 2, 3, 5, 7, 8, 10)  # C natural minor
ROOT_DEGREES = (0, 3, 4, 5)  # C, F, G, Ab: choices, NOT a chord progression.
SCALE = [n for n in range(128) if n % 12 in SCALE_CLASSES]
DRUM_KICK, DRUM_SNARE, DRUM_HAT = 36, 38, 42


def get_source(supplied):
    if supplied:
        return Path(supplied)
    cache = ROOT / ".market_cache"
    cache.mkdir(exist_ok=True)
    archive = cache / "spy_minutes.zip"
    if not archive.exists():
        print("Downloading public minute archive; this may take several minutes...")
        temporary = archive.with_suffix(".part")
        try:
            request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "StockMusic/1.0"})
            with urllib.request.urlopen(request, timeout=180) as response, temporary.open("wb") as output:
                while block := response.read(1024 * 1024):
                    output.write(block)
            if not zipfile.is_zipfile(temporary):
                raise ValueError("Download is not a ZIP; Kaggle may require a browser login")
            temporary.replace(archive)
        finally:
            temporary.unlink(missing_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        choices = [n for n in bundle.namelist() if n.lower().endswith(".csv")]
        if len(choices) != 1:
            raise ValueError(f"Expected one source CSV, found {choices}")
        destination = cache / "spy_minutes.csv"
        if not destination.exists():
            with bundle.open(choices[0]) as source, destination.open("wb") as output:
                while block := source.read(1024 * 1024):
                    output.write(block)
    return destination


def read_source(path):
    frame = pd.read_csv(path)
    frame.columns = frame.columns.str.strip().str.lower()
    frame = frame.rename(columns={"date": "timestamp", "datetime": "timestamp"})
    columns = ["timestamp", "open", "high", "low", "close", "volume"]
    if set(columns) - set(frame):
        raise ValueError(f"Required columns: {columns}")
    frame = frame[columns].copy()
    text = frame.timestamp.astype(str).str.strip()
    compact = text.str.match(r"^\d{8} ")
    frame.timestamp = pd.to_datetime(text, format="%Y%m%d %H:%M:%S" if compact.all() else "mixed", errors="raise")
    for field in columns[1:]:
        frame[field] = pd.to_numeric(frame[field], errors="raise")
    frame = frame.drop_duplicates().sort_values("timestamp")
    if frame.timestamp.duplicated().any():
        raise ValueError("Conflicting duplicate timestamps; resolve before generating music")
    return frame.set_index("timestamp")


def validate(frame, start, end):
    if len(frame) < 960:
        raise ValueError(f"Only {len(frame)} source bars; need at least 960")
    if frame.index[0] > pd.Timestamp(start) + pd.Timedelta(days=7) or frame.index[-1] < pd.Timestamp(end) - pd.Timedelta(days=7):
        raise ValueError("Data does not cover requested event boundaries")
    if not np.isfinite(frame.to_numpy()).all() or (frame[["open", "high", "low", "close"]] <= 0).any().any() or (frame.volume < 0).any():
        raise ValueError("Invalid/missing/non-finite OHLCV")
    if ((frame.high < frame[["open", "close", "low"]].max(axis=1)) | (frame.low > frame[["open", "close", "high"]].min(axis=1))).any():
        raise ValueError("Invalid OHLC ordering")
    stamps = pd.Series(frame.index)
    differences = stamps.diff()
    if (differences.dropna() < pd.Timedelta(minutes=1)).any():
        raise ValueError("Expected one-minute-or-coarser distinct source timestamps")
    same_date = stamps.dt.date.eq(stamps.shift().dt.date)
    gaps = same_date & (differences > pd.Timedelta(minutes=1))
    if gaps.sum() / len(frame) > 0.01 or (differences[gaps] > pd.Timedelta(minutes=5)).any():
        raise ValueError("Intraday gaps exceed tolerance; inspect source/session structure")
    dates = pd.DatetimeIndex(frame.index.normalize().unique())
    if (dates.to_series().diff().dropna() > pd.Timedelta(days=5)).any():
        raise ValueError("Possible missing trading sessions")
    return int(gaps.sum())


def candles(frame, count):
    # Equal observed-minute windows; no invented/reused bars.
    boundaries = np.arange(count + 1) * len(frame) // count
    rows = []
    for index, (left, right) in enumerate(zip(boundaries[:-1], boundaries[1:])):
        chunk = frame.iloc[left:right]
        rows.append(dict(candle=index, source_start=chunk.index[0], source_end=chunk.index[-1],
            source_count=len(chunk), open=chunk.open.iloc[0], high=chunk.high.max(),
            low=chunk.low.min(), close=chunk.close.iloc[-1], volume=chunk.volume.sum()))
    result = pd.DataFrame(rows)
    result["ema"] = result.close.ewm(span=EMA_SPAN, adjust=False).mean()
    result["trend"] = np.log(result.ema / frame.open.iloc[0])
    result["volatility"] = np.log(result.high / result.low).rolling(VOL_WINDOW, min_periods=1).mean()
    activity = result.volume / result.source_count
    baseline = activity.shift().rolling(VOLUME_WINDOW, min_periods=1).mean()
    result["relative_volume"] = (activity / baseline.replace(0, np.nan)).fillna(1).clip(0, 10)
    # Fractional EMA slope magnitude; each track/event has its own robust scale.
    # Offline percentile normalisation; NOT directly comparable across events.
    result["ema_gradient"] = np.log(result["ema"]).diff().abs().fillna(0.0)
    gradient_scale = float(result["ema_gradient"].quantile(GRADIENT_QUANTILE))
    result["gradient_strength"] = ((result["ema_gradient"] / gradient_scale).clip(0.0, 1.0)
                                   if gradient_scale > 0 else 0.0)
    return result


def variable_length(number):
    parts = [number & 127]
    while number >> 7:
        number >>= 7
        parts.insert(0, (number & 127) | 128)
    return bytes(parts)


def midi_track(messages, end_tick):
    data, previous = bytearray(), 0
    for tick, priority, message in sorted(messages, key=lambda item: (item[0], item[1])):
        data.extend(variable_length(tick - previous)); data.extend(message)
        previous = tick
    data.extend(variable_length(end_tick - previous)); data.extend(b"\xff\x2f\x00")
    return b"MTrk" + struct.pack(">I", len(data)) + data


def chord_classes(root):
    """Diatonic root, third, fifth AND seventh in C natural minor."""
    degree = SCALE_CLASSES.index(root % 12)
    return tuple(SCALE_CLASSES[(degree + step) % 7] for step in (0, 2, 4, 6))


def bass_roots(table, extent, low, high):
    allowed = [n for n in range(low, high + 1)
               if n % 12 in [SCALE_CLASSES[d] for d in ROOT_DEGREES]]
    return [min(allowed, key=lambda n: abs(n - (low + (np.clip(t / extent, -1, 1) + 1) * 0.5 * (high-low))))
            for t in table.trend]


def make_song(frame):
    metrics = {name: candles(frame, count) for name, count, *_ in TRACKS}
    extent = max(abs(table.trend).max() for table in metrics.values()) or 1.0
    bass_config = next(t for t in TRACKS if t[0] == "bass")
    roots = bass_roots(metrics["bass"], extent, bass_config[4], bass_config[5])
    end_tick = BARS * 4 * TPB
    tempo = int(round(60_000_000 / BPM))
    seconds_per_tick = tempo / 1_000_000 / TPB
    tracks = [midi_track([(0, 0, b"\xff\x51\x03" + tempo.to_bytes(3, "big")),
                          (0, 0, b"\xff\x58\x04\x04\x02\x18\x08")], end_tick)]
    rows = []
    for name, count, channel, program, low, high in TRACKS:
        table = metrics[name]
        volatility_limit = float(table.volatility.quantile(0.95)) or 1.0
        messages = [] if program is None else [(0, 0, bytes([0xC0 | channel, program]))]
        slot = end_tick / count
        notes_per_bar = count // BARS
        previous_pitch = None
        for i, candle in table.iterrows():
            trend = float(np.clip(candle.trend / extent, -1, 1))
            stress = float(np.clip(candle.volatility / volatility_limit, 0, 1))
            position, bar = i % notes_per_bar, i // notes_per_bar
            root = int(roots[bar])
            chord = chord_classes(root)
            # Shared small swing rule, no arbitrary early notes. Bass/main beats fixed.
            shift = MAX_DISPLACEMENT * stress if name != "bass" and position % 2 else 0.0
            tick = int(round((i + shift) * slot))
            duration = max(1, int(slot * (0.35 if name == "drums" else 0.60)))
            stop = min(end_tick, tick + duration)
            accent = 1.0
            strong_beat = position % 2 == 0
            if name == "drums":
                if position in (0, 8):
                    pitch, accent = DRUM_KICK, 1.0
                elif position in (4, 12):
                    pitch, accent = DRUM_SNARE, 0.95
                else:
                    pitch = DRUM_HAT
                    accent = 0.68 if position % 2 == 0 else 0.45
                strong_beat = position % 4 == 0
            elif name == "bass":
                pitch = root
            else:
                target = low + (trend + 1) * 0.5 * (high - low)
                candidates = [n for n in SCALE if low <= n <= high and
                              (not strong_beat or n % 12 in chord)]
                if previous_pitch is not None:
                    nearby = [n for n in candidates if abs(n - previous_pitch) <= 5]
                    candidates = nearby or candidates
                pitch = min(candidates, key=lambda n: abs(n-target) +
                            (0.6 * abs(n-previous_pitch) if previous_pitch is not None else 0))
                previous_pitch = pitch
            base_velocity = VELOCITY_MIN + (VELOCITY_MAX-VELOCITY_MIN) * candle.gradient_strength
            velocity = int(np.clip(round(base_velocity * accent), 1, 127))
            messages += [(tick, 2, bytes([0x90 | channel, pitch, velocity])),
                         (stop, 1, bytes([0x80 | channel, pitch, 0]))]
            rows.append(dict(track=name, instrument=name, bar=bar + 1,
                pitch_midi=int(pitch), velocity=velocity, velocity_base=base_velocity,
                drum_accent=accent, harmony_root_midi=root,
                chord_pitch_classes=";".join(map(str, chord)), strong_beat=strong_beat,
                start_seconds=tick * seconds_per_tick, duration_seconds=(stop-tick) * seconds_per_tick,
                rhythm_offset_fraction=shift, trend_normalised=trend,
                volatility_normalised=stress, **candle.to_dict()))
        tracks.append(midi_track(messages, end_tick))
    binary = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), TPB) + b"".join(tracks)
    return binary, pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", help="Use local SPY one-minute OHLCV CSV")
    parser.add_argument("--output", default=str(ROOT / "data/market_events"))
    args = parser.parse_args()
    source = get_source(args.source)
    with source.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    data = read_source(source)
    output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, start, end in EVENTS:
        record = dict(event=name, requested_start=start, requested_end_exclusive=end,
                      symbol="SPY", source=PROVENANCE if not args.source else str(source), sha256=digest)
        destination = output / name
        destination.mkdir(exist_ok=True)
        for old in destination.glob("*"):
            if old.name in ("song.mid", "metrics.csv", "source.csv"):
                old.unlink()
        try:
            frame = data.loc[(data.index >= start) & (data.index < end)]
            gap_count = validate(frame, start, end)
            binary, events = make_song(frame)
            assert events.groupby("track").size().to_dict() == {"bass": 60, "drums": 960, "synth": 240}
            assert events.groupby(["track", "bar"]).size().groupby(level=0).nunique().eq(1).all()
            frame.to_csv(destination / "source.csv", index_label="timestamp")
            events.to_csv(destination / "metrics.csv", index=False)
            (destination / "song.mid").write_bytes(binary)
            record.update(status="ok", source_rows=len(frame), first=str(frame.index[0]),
                          last=str(frame.index[-1]), tolerated_intraday_gaps=gap_count,
                          duration_seconds=BARS * 4 * 60 / BPM, notes=len(events),
                          arrangement="ema_gradient_seventh_harmony_v2")
            print(f"OK {name}: {len(frame)} genuine bars -> {len(events)} notes")
        except (ValueError, AssertionError) as error:
            record.update(status="FAILED", reason=str(error))
            print(f"FAILED {name}: {error}")
        manifest.append(record)
    pd.DataFrame(manifest).to_csv(output / "manifest.csv", index=False)
    print(f"Successful events: {sum(r['status']=='ok' for r in manifest)}/{len(EVENTS)}")
    if any(r["status"] != "ok" for r in manifest):
        raise SystemExit("Some events failed. Inspect manifest.csv; do not claim ten completed files.")


if __name__ == "__main__":
    main()
