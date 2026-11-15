"""Local-market seven-instrument sonification. Simulations are NOT historical trades."""
from pathlib import Path
import argparse, hashlib, json, struct, zipfile
from datetime import datetime, timezone
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
COLS = ["open", "high", "low", "close", "volume"]
ADJUSTMENT = "yahoo_auto_adjust_split_and_dividend"
# onsets, MIDI channel (zero based), GM program, pitch range, gain, pan
TRACKS = {
    "bass": (60, 0, 33, 28, 48, .85, 64),
    "drums": (960, 9, None, 0, 0, .85, 64),
    "synth_lead": (240, 1, 81, 55, 84, .40, 48),
    "synth_pad": (60, 2, 89, 55, 79, .45, 64),
    "guitar": (480, 3, 24, 48, 72, .60, 35),
    "synth_counter": (240, 4, 80, 60, 84, .30, 80),
    "guitar_counter": (480, 5, 26, 52, 76, .45, 95)}
SCALE = (0, 2, 3, 5, 7, 8, 10)
FIELDS = ("momentum", "volatility", "shock", "drawdown", "acceleration", "relative_volume")


def seed_for(*parts):
    return int.from_bytes(hashlib.sha256("|".join(map(str, parts)).encode()).digest()[:8], "big")


def validate(frame):
    if frame.empty or not np.isfinite(frame[COLS].to_numpy()).all():
        raise ValueError("Empty or nonfinite OHLCV")
    if (frame[COLS[:4]] <= 0).any().any() or (frame.volume < 0).any():
        raise ValueError("Invalid prices or volume")
    if (frame.high < frame[["open", "close", "low"]].max(axis=1)).any() or (frame.low > frame[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("Invalid OHLC ordering")
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError("Timestamps must be unique and ordered")


def daily(symbol, start, end, cache):
    import yfinance as yf
    name = hashlib.sha256(f"{symbol}|{start}|{end}|{ADJUSTMENT}".encode()).hexdigest()[:20]
    path = cache/f"{name}.csv"
    if path.exists():
        data = pd.read_csv(path, index_col=0, parse_dates=True)
    else:
        data = yf.Ticker(symbol).history(start=start, end=end, interval="1d", auto_adjust=True, actions=False, raise_errors=True)
        data.columns = data.columns.str.lower()
        data = data[COLS].copy()
        data.index = pd.DatetimeIndex(data.index).tz_localize(None).normalize()
        validate(data)
        data.to_csv(path, index_label="date")
    validate(data)
    return data, path


def session_minutes(schedule_row):
    segments = [(schedule_row.market_open, schedule_row.market_close)]
    if pd.notna(schedule_row.get("break_start", pd.NaT)):
        segments = [(schedule_row.market_open, schedule_row.break_start),
                    (schedule_row.break_end, schedule_row.market_close)]
    stamps = [pd.date_range(a, b, freq="min", inclusive="left") for a, b in segments]
    return stamps[0].append(stamps[1:])


def simulate(anchor, stamps, symbol, market, seed):
    """Constrained random bridge: exact daily OHLC and integer total volume."""
    n = len(stamps)
    if n < 4:
        raise ValueError("Session too short")
    rng = np.random.default_rng(seed_for(seed, symbol, str(stamps[0].date())))
    common = np.random.default_rng(seed_for(seed, market, str(stamps[0].date())))
    lo, hi = np.log(anchor.low), np.log(anchor.high)
    turns = sorted(common.choice(np.arange(1, n), size=2, replace=False))
    times = [0, int(turns[0]), int(turns[1]), n]
    extremes = [lo, hi] if common.random() < .5 else [hi, lo]
    pins = [np.log(anchor.open), *extremes, np.log(anchor.close)]
    path = np.empty(n+1)
    for a, b, p, q in zip(times[:-1], times[1:], pins[:-1], pins[1:]):
        length = b-a
        walk = np.r_[0., np.cumsum(.5*common.normal(size=length)+.5*rng.normal(size=length))]
        bridge = walk-np.linspace(0, walk[-1], length+1)
        path[a:b+1] = np.clip(np.linspace(p, q, length+1)+bridge*(hi-lo)/np.sqrt(n)*.25, lo, hi)
    prices = np.clip(np.exp(path), anchor.low, anchor.high)
    prices[0], prices[-1] = anchor.open, anchor.close
    prices[times[1]], prices[times[2]] = (anchor.low, anchor.high) if extremes[0] == lo else (anchor.high, anchor.low)
    weights = 1+.6*np.abs(np.linspace(-1, 1, n))
    total = int(round(anchor.volume))
    volume = rng.multinomial(total, weights/weights.sum())
    result = pd.DataFrame(dict(open=prices[:-1], high=np.maximum(prices[:-1], prices[1:]),
        low=np.minimum(prices[:-1], prices[1:]), close=prices[1:], volume=volume), index=stamps)
    result["is_simulated"] = True
    result["provenance"] = "daily_constrained_random_bridge_v1"
    validate(result)
    assert np.isclose(result.high.max(), anchor.high) and np.isclose(result.low.min(), anchor.low)
    assert result.volume.sum() == total
    return result


def real_minutes(directory, symbol):
    path = directory/f"{symbol}.csv"
    if not path.exists():
        return None
    info = json.loads(path.with_suffix(".json").read_text())
    if info.get("symbol") != symbol or info.get("interval") != "1min" or info.get("adjustments") != ADJUSTMENT or not info.get("source"):
        raise ValueError(f"Invalid/mismatched minute provenance: {path}")
    frame = pd.read_csv(path)
    frame.columns = frame.columns.str.lower()
    text = frame.pop("timestamp").astype(str)
    if not text.str.contains(r"(?:Z|[+-]\d{2}:\d{2})$", regex=True).all():
        raise ValueError("Real minute timestamps must carry UTC Z or an explicit offset")
    stamps = pd.to_datetime(text, utc=True)
    frame.index = pd.DatetimeIndex(stamps)
    frame = frame[COLS].astype(float).sort_index()
    validate(frame)
    frame["is_simulated"], frame["provenance"] = False, info["source"]
    return frame


def build_frame(anchors, schedule, observed, symbol, market, seed):
    pieces, rejected = [], []
    for date, session in schedule.iterrows():
        day = pd.Timestamp(date).tz_localize(None).normalize()
        if day not in anchors.index:
            raise ValueError(f"Missing real daily anchor for {symbol}: {day.date()}")
        anchor, stamps = anchors.loc[day], session_minutes(session)
        actual = None if observed is None else observed.reindex(stamps)
        complete = actual is not None and actual[COLS].notna().all().all()
        if complete:
            totals = np.array([actual.open.iloc[0], actual.high.max(), actual.low.min(), actual.close.iloc[-1]])
            complete = np.allclose(totals, anchor[COLS[:4]].to_numpy(dtype=float), rtol=.005, atol=1e-8)
            if complete and anchor.volume > 0:
                complete = np.isclose(actual.volume.sum(), anchor.volume, rtol=.02)
        if complete:
            pieces.append(actual)
        else:
            if observed is not None:
                rejected.append(str(day.date()))
            pieces.append(simulate(anchor, stamps, symbol, market, seed))
    result = pd.concat(pieces)
    validate(result)
    return result, rejected


def features(frame, count):
    if len(frame) < count:
        raise ValueError("Insufficient minute candles")
    returns = np.log(frame.close/frame.close.shift()).fillna(np.log(frame.close.iloc[0]/frame.open.iloc[0]))
    highs = frame.high.cummax()
    edges = np.arange(count+1)*len(frame)//count
    rows = []
    for left, right in zip(edges[:-1], edges[1:]):
        chunk, r = frame.iloc[left:right], returns.iloc[left:right]
        rows.append(dict(source_start=str(chunk.index[0]), source_end=str(chunk.index[-1]),
            source_count=len(chunk), simulated_fraction=float(chunk.is_simulated.mean()),
            close=chunk.close.iloc[-1], volume_per_minute=chunk.volume.mean(),
            volatility=float(np.sqrt(np.mean(r*r))), shock=float(r.abs().max()),
            drawdown=float((1-frame.close.iloc[left:right]/highs.iloc[left:right]).max()),
            efficiency=abs(float(r.sum()))/max(1e-12, float(r.abs().sum())), hours=len(chunk)/60))
    out = pd.DataFrame(rows)
    ema = out.close.ewm(span=12, adjust=False).mean()
    out["trend"] = np.log(ema/frame.open.iloc[0])
    out["momentum"] = np.log(ema).diff().fillna(0)/out.hours
    out["acceleration"] = out.momentum.diff().fillna(0)
    baseline = out.volume_per_minute.shift().rolling(20, min_periods=1).median()
    out["relative_volume"] = (out.volume_per_minute/baseline.replace(0, np.nan)).fillna(1).clip(0, 5)
    out["volume_available"] = bool(frame.volume.sum() > 0)
    return out


def calibrate(prepared):
    return {name: {field: max(1e-12, float(np.quantile(np.concatenate([t[name][field].abs().to_numpy() for t in prepared]), .95)))
                   for field in FIELDS} for name in TRACKS}


def vlq(n):
    out = [n & 127]
    while n >> 7:
        n >>= 7
        out.insert(0, (n & 127)|128)
    return bytes(out)


def midi_track(messages, end):
    body, last = bytearray(), 0
    for tick, priority, message in sorted(messages):
        body.extend(vlq(tick-last)+message)
        last = tick
    body.extend(vlq(end-last)+b"\xff\x2f\x00")
    return b"MTrk"+struct.pack(">I", len(body))+body


def song(tables, scales):
    end, slot_seconds = 60*4*480, .5/480
    tracks = [midi_track([(0, 0, b"\xff\x51\x03\x07\xa1\x20")], end)]
    rows = []
    # Fixed percent-return range, not per-song scaling: calm stays calm.
    roots = [min((36, 41, 43, 44, 48), key=lambda x: abs(x-(42+30*np.clip(v, -.2, .2)))) for v in tables["bass"].trend]
    for name, (count, channel, program, low, high, gain, pan) in TRACKS.items():
        label = name.encode()
        messages = [(0, 0, b"\xff\x03"+vlq(len(label))+label),
                    (0, 0, bytes([0xB0|channel, 10, pan]))]
        if program is not None:
            messages += [(0, 0, bytes([0xC0|channel, program])),
                         (0, 0, bytes([0xB0|channel, 7, 35 if name=="synth_lead" else 90]))]
        previous = (low+high)//2
        for i, row in tables[name].iterrows():
            strength = {f: float(np.clip(abs(row[f])/scales[name][f], 0, 1)) for f in FIELDS}
            per_bar = count//60
            bar, position = divmod(i, per_bar)
            root = roots[bar]
            degree = SCALE.index(root%12)
            chord = [SCALE[(degree+j)%7] for j in (0, 2, 4)]
            if strength["drawdown"] > .45:
                chord.append(SCALE[(degree+6)%7])
            energy = .45*strength["momentum"]+.35*strength["volatility"]+.20*strength["shock"]
            gate, accent = .6, 1.
            if name == "drums":
                pitches = [36 if position in (0,8) else 38 if position in (4,12) else 42]
                accent = 1 if position%4==0 else .55
                gate = .25
            elif name == "bass":
                pitches, gate = [root-12], .9
            elif name == "synth_pad":
                pitches, gate = [min((n for n in range(low, high+1) if n%12==pc), key=lambda n: abs(n-67)) for pc in chord], .98
            else:
                signal = float(np.clip(row.trend/.20, -1, 1))
                if name=="synth_counter":
                    signal, energy = float(np.clip(row.acceleration/scales[name]["acceleration"], -1, 1)), strength["acceleration"]
                if name=="guitar_counter":
                    signal, energy = -signal, .5*energy+.5*(strength["relative_volume"] if row.volume_available else strength["volatility"])
                target = low+(signal+1)*.5*(high-low)
                candidates = [n for n in range(low, high+1) if n%12 in (chord if position%2==0 else SCALE)]
                pitch = min(candidates, key=lambda n: abs(n-target)+.7*abs(n-previous))
                pitches, previous = [pitch], pitch
                if "guitar" in name:
                    gate = .25+.5*row.efficiency
            shift = .06*strength["volatility"] if position%2 and name not in ("bass", "synth_pad") else 0
            start = round((i+shift)*end/count)
            stop = min(end, start+max(1, round(gate*end/count)))
            velocity = int(np.clip(round((30+85*energy)*gain*accent), 1, 127))
            for pitch in pitches:
                messages += [(start, 2, bytes([0x90|channel, pitch, velocity])), (stop, 1, bytes([0x80|channel, pitch, 0]))]
                rows.append(dict(track=name, onset=i, bar=bar+1, pitch_midi=pitch, velocity=velocity,
                    start_seconds=start*slot_seconds, duration_seconds=(stop-start)*slot_seconds,
                    **row.to_dict()))
        tracks.append(midi_track(messages, end))
    return b"MThd"+struct.pack(">IHHH", 6, 1, len(tracks), 480)+b"".join(tracks), pd.DataFrame(rows)


def main():
    import pandas_market_calendars as calendars
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minutes", type=Path, default=ROOT/"data/local_minute_inputs")
    parser.add_argument("--output", type=Path, default=ROOT/"data/local_markets_v4")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    config = json.loads((ROOT/"local_market_periods.json").read_text())
    assert len(config["periods"])==15
    cache = ROOT/".market_cache/local_daily"
    cache.mkdir(parents=True, exist_ok=True)
    output = args.output/datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    output.mkdir(parents=True)
    (output/"configuration.json").write_text(json.dumps(config, indent=2))
    records, ready, sources = [], [], {}
    for period in config["periods"]:
        market = config["markets"][period["market"]]
        assets = [market["index"], *market["stocks"]]
        assert len(assets)==6 and len(set(assets))==6
        try:
            schedule = calendars.get_calendar(market["calendar"]).schedule(start_date=period["start"], end_date=pd.Timestamp(period["end"])-pd.Timedelta(days=1))
            if schedule.empty:
                raise ValueError("No scheduled sessions")
            for symbol in assets:
                key = (period["market"], symbol)
                if key not in sources:
                    periods = [p for p in config["periods"] if p["market"]==period["market"]]
                    sources[key] = daily(symbol, min(p["start"] for p in periods), max(p["end"] for p in periods), cache)
            benchmark = sources[(period["market"], market["index"])][0].loc[period["start"]:pd.Timestamp(period["end"])-pd.Timedelta(days=1)]
            volatility = float(np.log(benchmark.close).diff().std()*np.sqrt(252))
            drawdown = float((1-benchmark.close/benchmark.close.cummax()).max())
            change = float(benchmark.close.iloc[-1]/benchmark.open.iloc[0]-1)
            stable = len(benchmark)>=30 and volatility<=config["stable_limits"]["annual_volatility"] and drawdown<=config["stable_limits"]["max_drawdown"] and abs(change)<=config["stable_limits"]["absolute_return"]
            if period["kind"]=="stable_candidate" and not stable:
                raise ValueError(f"Stable candidate failed thresholds: vol={volatility}, drawdown={drawdown}, return={change}")
        except Exception as error:
            records.extend(dict(period=period["id"], symbol=s, status="FAILED", reason=str(error)) for s in assets)
            continue
        for symbol in assets:
            record = dict(period=period["id"], market=period["market"], symbol=symbol,
                asset_kind="index" if symbol==market["index"] else "stock", kind=period["kind"],
                start=period["start"], end_exclusive=period["end"], seed=args.seed,
                benchmark_annual_volatility=volatility, benchmark_drawdown=drawdown, benchmark_return=change)
            records.append(record)
            try:
                anchors, source = sources[(period["market"], symbol)]
                frame, rejected = build_frame(anchors, schedule, real_minutes(args.minutes, symbol), symbol, period["market"], args.seed)
                destination = output/period["id"]/symbol
                destination.mkdir(parents=True)
                frame.to_csv(destination/"source.csv", index_label="timestamp")
                anchors.loc[period["start"]:pd.Timestamp(period["end"])-pd.Timedelta(days=1)].to_csv(destination/"daily_anchors.csv", index_label="date")
                tables = {name: features(frame, spec[0]) for name, spec in TRACKS.items()}
                record.update(status="PREPARED", simulated_fraction=float(frame.is_simulated.mean()),
                    source_rows=len(frame), adjustments=ADJUSTMENT, daily_provider="Yahoo Finance via yfinance",
                    daily_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), rejected_real_sessions=rejected,
                    simulation="daily_constrained_random_bridge_v1; not historical intraday evidence")
                ready.append((record, destination, tables))
            except Exception as error:
                record.update(status="FAILED", reason=str(error))
    if ready:
        scales = calibrate([t for _, _, t in ready])
        (output/"calibration.json").write_text(json.dumps(scales, indent=2))
        for record, destination, tables in ready:
            try:
                binary, metrics = song(tables, scales)
                (destination/"song.mid").write_bytes(binary)
                metrics.to_csv(destination/"metrics.csv", index=False)
                record.update(status="GENERATED", calibration_pairs=len(ready), duration_seconds=120, instruments=7)
            except Exception as error:
                record.update(status="FAILED", reason=str(error))
            (destination/"metadata.json").write_text(json.dumps(record, indent=2))
    (output/"manifest.json").write_text(json.dumps(records, indent=2))
    pd.DataFrame(records).to_csv(output/"manifest.csv", index=False)
    successful = [r for r in records if r["status"]=="GENERATED"]
    with zipfile.ZipFile(output/"songs.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for record in successful:
            p = output/record["period"]/record["symbol"]/"song.mid"
            archive.write(p, p.relative_to(output))
        archive.write(output/"manifest.json", "manifest.json")
    print(f"Generated {len(successful)}/90 songs in {output}")
    if len(successful)!=90:
        raise SystemExit("Incomplete collection. Inspect manifest; no prior outputs were overwritten.")


if __name__ == "__main__":
    main()
