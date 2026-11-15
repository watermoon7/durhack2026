"""Complete all 90 pairs offline; invented observations are explicitly synthetic."""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, json, zipfile
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
COLS = ["open", "high", "low", "close", "volume"]
HOURS = {"US": [("09:30", "16:00")], "UK": [("08:00", "16:30")],
         "JP": [("09:00", "11:30"), ("12:30", "15:00")],
         "CN": [("09:30", "11:30"), ("13:00", "15:00")],
         "IN": [("09:15", "15:30")]}


def rng_for(seed, *keys):
    digest = hashlib.sha256("|".join(map(str, (seed, *keys))).encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "big"))


def schedule(period, market):
    try:
        import pandas_market_calendars as calendars
        table = calendars.get_calendar(market["calendar"]).schedule(
            start_date=period["start"], end_date=pd.Timestamp(period["end"])-pd.Timedelta(days=1))
        if table.empty:
            raise ValueError("Empty calendar")
        sessions = []
        for day, row in table.iterrows():
            spans = [(row.market_open, row.market_close)]
            if pd.notna(row.get("break_start", pd.NaT)):
                spans = [(row.market_open, row.break_start), (row.break_end, row.market_close)]
            stamps = [pd.date_range(a, b, freq="min", inclusive="left") for a,b in spans]
            sessions.append((pd.Timestamp(day).tz_localize(None).normalize(), stamps[0].append(stamps[1:])))
        return sessions, "exchange_calendar_scheduled_sessions"
    except Exception as error:
        sessions = []
        for day in pd.bdate_range(period["start"], pd.Timestamp(period["end"])-pd.Timedelta(days=1)):
            stamps = [pd.date_range(f"{day.date()} {a}", f"{day.date()} {b}", tz=market["timezone"], freq="min", inclusive="left").tz_convert("UTC") for a,b in HOURS[period["market"]]]
            sessions.append((day, stamps[0].append(stamps[1:])))
        return sessions, f"SYNTHETIC_WEEKDAY_CALENDAR; holidays/halts not modeled; {type(error).__name__}"


def valid_rows(frame):
    numeric = frame[COLS].apply(pd.to_numeric, errors="coerce")
    valid = np.isfinite(numeric.to_numpy()).all(axis=1) & (numeric[COLS[:4]] > 0).all(axis=1) & (numeric.volume >= 0)
    valid &= numeric.high >= numeric[["open", "close", "low"]].max(axis=1)
    valid &= numeric.low <= numeric[["open", "close", "high"]].min(axis=1)
    return valid


def load_existing(paths, start, end, warnings):
    pieces = []
    for path in paths:
        try:
            data = pd.read_csv(path)
            if not {"timestamp", "is_simulated", "provenance", *COLS}.issubset(data.columns):
                raise ValueError("Missing row-level provenance/schema")
            data.index = pd.DatetimeIndex(pd.to_datetime(data.pop("timestamp"), utc=True))
            flags = data.is_simulated.astype(str).str.lower()
            if not flags.isin(["true", "false", "1", "0"]).all():
                raise ValueError("Unknown simulation flags")
            data["is_simulated"] = flags.isin(["true", "1"])
            data = data.loc[(data.index>=pd.Timestamp(start, tz="UTC")-pd.Timedelta(days=1)) & (data.index<pd.Timestamp(end, tz="UTC")+pd.Timedelta(days=1))]
            data = data.loc[valid_rows(data)].copy()
            data[COLS] = data[COLS].astype(float)
            pieces.append(data[COLS+["is_simulated", "provenance"]])
        except (OSError, ValueError, KeyError) as error:
            warnings.append(f"Ignored {path}: {error}")
    if not pieces:
        return None
    merged = pd.concat(pieces).sort_values("is_simulated", ascending=False, kind="stable")
    return merged.loc[~merged.index.duplicated(keep="last")].sort_index()


def load_anchors(paths, warnings):
    pieces = []
    for path in paths:
        if not path.exists():
            continue
        try:
            data = pd.read_csv(path, index_col=0, parse_dates=True)
            data.index = pd.DatetimeIndex(data.index).tz_localize(None).normalize()
            if "anchor_is_simulated" in data:
                data = data.loc[data.anchor_is_simulated.astype(str).str.lower().isin(["false", "0"])]
            data = data.loc[valid_rows(data), COLS].astype(float)
            pieces.append(data)
        except (OSError, ValueError, KeyError) as error:
            warnings.append(f"Ignored anchor file {path}: {error}")
    if not pieces:
        return pd.DataFrame(columns=COLS)
    data = pd.concat(pieces)
    return data.loc[~data.index.duplicated(keep="last")].sort_index()


def bridge(n, first, last, sigma, rng):
    walk = np.r_[0., np.cumsum(rng.normal(0, sigma, n))]
    walk -= np.linspace(0, walk[-1], n+1)
    path = np.exp(np.linspace(np.log(first), np.log(last), n+1)+walk)
    path[0], path[-1] = first, last
    return path


def complete_pair(period, market, symbol, seed, sessions, observed=None, anchors=None):
    rng = rng_for(seed, period["id"], symbol)
    is_index = symbol == market["index"]
    previous = float(observed.open.iloc[0]) if observed is not None and len(observed) else 100.
    frames, daily = [], []
    for number, (day, stamps) in enumerate(sessions):
        n = len(stamps)
        stable = period["kind"].startswith("stable")
        phase = number/max(1, len(sessions)-1)
        stress = 0. if stable else float(np.exp(-((phase-.45)/.16)**2))
        common = rng_for(seed, period["id"], str(day.date()))
        anchored = anchors is not None and day in anchors.index
        if anchored:
            anchor = anchors.loc[day]
        else:
            sigma = .0015 if stable else .006+.025*stress
            change = common.normal(-.025*stress+.006*(phase>.65) if not stable else 0., sigma)+rng.normal(0, sigma*.35)
            close = previous*np.exp(change)
            spread = previous*(.003 if stable else .008+.025*stress)
            anchor = pd.Series(dict(open=previous, close=close,
                high=max(previous,close)+spread, low=max(.0001,min(previous,close)-spread),
                volume=0 if is_index else int(rng.integers(50000,500000))))
        known = None if observed is None else observed.reindex(stamps)
        mask = np.zeros(n, dtype=bool) if known is None else known[COLS].notna().all(axis=1).to_numpy()
        if anchored and known is not None:
            mask &= known.is_simulated.eq(False).to_numpy()
        sigma = max(1e-7, abs(np.log(anchor.high/anchor.low))/np.sqrt(n)*.35)
        prices = bridge(n, float(anchor.open), float(anchor.close), sigma, rng)
        prices = np.clip(prices, float(anchor.low), float(anchor.high))
        result = pd.DataFrame(dict(open=prices[:-1], high=np.maximum(prices[:-1],prices[1:]),
            low=np.minimum(prices[:-1],prices[1:]), close=prices[1:], volume=np.zeros(n)), index=stamps)
        result["is_simulated"] = True
        result["provenance"] = "DAILY_ANCHORED_SIMULATION" if anchored else "FULLY_SYNTHETIC_SCENARIO_NOT_HISTORICAL"
        if mask.any():
            result.loc[mask, COLS] = known.loc[mask, COLS].to_numpy(dtype=float)
            result.loc[mask, "is_simulated"] = known.loc[mask, "is_simulated"].astype(bool).to_numpy()
            result.loc[mask, "provenance"] = known.loc[mask, "provenance"].astype(str).to_numpy()
        missing = ~mask
        boundaries = np.diff(np.r_[False, missing, False].astype(int))
        for left,right in zip(np.where(boundaries==1)[0], np.where(boundaries==-1)[0]):
            first = result.close.iloc[left-1] if left else anchor.open
            last = result.open.iloc[right] if right<n else anchor.close
            path = bridge(right-left, float(first), float(last), sigma, rng)
            low, high = min(anchor.low,first,last), max(anchor.high,first,last)
            path = np.clip(path, low, high)
            result.iloc[left:right, :4] = np.column_stack([path[:-1], np.maximum(path[:-1],path[1:]), np.minimum(path[:-1],path[1:]), path[1:]])
        if missing.any():
            locations = np.where(missing)[0]
            # Put daily extremes on simulated wicks, never change a known observation.
            hi, lo = int(rng.choice(locations)), int(rng.choice(locations))
            result.iloc[hi, result.columns.get_loc("high")] = max(result.high.iloc[hi], anchor.high)
            result.iloc[lo, result.columns.get_loc("low")] = min(result.low.iloc[lo], anchor.low)
            remaining = max(0, int(round(anchor.volume-float(result.loc[mask,"volume"].sum()))))
            result.loc[missing,"volume"] = rng.multinomial(remaining, np.full(len(locations),1/len(locations)))
        if not valid_rows(result).all():
            raise ValueError("Completion produced invalid OHLCV")
        result["is_simulated"] = result.is_simulated.astype(bool)
        frames.append(result)
        daily.append(dict(date=str(day.date()), **anchor.to_dict(), anchor_is_simulated=not anchored))
        previous = float(result.close.iloc[-1])
    frame = pd.concat(frames)
    expected = sessions[0][1].append([stamps for _,stamps in sessions[1:]])
    if not frame.index.equals(expected) or frame.index.has_duplicates:
        raise ValueError("Incomplete minute grid")
    return frame, pd.DataFrame(daily)


def main():
    import Local_Markets_Seven_Tracks as music
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--data-only", action="store_true")
    args = parser.parse_args()
    config = json.loads((ROOT/"local_market_periods.json").read_text())
    pairs = [(p,s) for p in config["periods"] for s in [config["markets"][p["market"]]["index"], *config["markets"][p["market"]]["stocks"]]]
    assert len(pairs)==90 and len({(p["id"],s) for p,s in pairs})==90
    old_roots = [p for p in (ROOT/"data").glob("*v4*") if p.is_dir()]
    output = ROOT/"data/local_markets_v4"/datetime.now(timezone.utc).strftime("complete_%Y%m%dT%H%M%S_%fZ")
    output.mkdir(parents=True)
    records, ready = [], []
    for period in config["periods"]:
        market = config["markets"][period["market"]]
        sessions, calendar_basis = schedule(period, market)
        for symbol in [market["index"], *market["stocks"]]:
            warnings = []
            paths = sorted([p for root in old_roots for p in root.glob(f"**/{period['id']}/{symbol}/source.csv")], key=lambda p:p.stat().st_mtime_ns)
            observed = load_existing(paths, period["start"], period["end"], warnings)
            try:
                supplied = music.real_minutes(ROOT/"data/local_minute_inputs", symbol)
                if supplied is not None:
                    supplied = supplied.loc[(supplied.index>=pd.Timestamp(period["start"],tz="UTC")-pd.Timedelta(days=1)) & (supplied.index<pd.Timestamp(period["end"],tz="UTC")+pd.Timedelta(days=1))]
                    observed = supplied if observed is None else pd.concat([observed, supplied]).loc[lambda d:~d.index.duplicated(keep="last")].sort_index()
            except (OSError, ValueError, KeyError) as error:
                warnings.append(f"Optional minute input ignored: {error}")
            periods = [p for p in config["periods"] if p["market"]==period["market"]]
            key = hashlib.sha256(f"{symbol}|{min(p['start'] for p in periods)}|{max(p['end'] for p in periods)}|{music.ADJUSTMENT}".encode()).hexdigest()[:20]
            anchor_paths = [ROOT/".market_cache/local_daily"/f"{key}.csv", *[p.with_name("daily_anchors.csv") for p in paths]]
            anchors = load_anchors(anchor_paths, warnings)
            frame, daily = complete_pair(period, market, symbol, args.seed, sessions, observed, anchors)
            destination = output/period["id"]/symbol
            destination.mkdir(parents=True)
            frame.to_csv(destination/"source.csv", index_label="timestamp")
            daily.to_csv(destination/"daily_anchors.csv", index=False)
            record = dict(period=period["id"], symbol=symbol, market=period["market"], kind=period["kind"],
                start=period["start"], end_exclusive=period["end"], status="DATASET_READY", seed=args.seed,
                source_rows=len(frame), simulated_fraction=float(frame.is_simulated.mean()),
                unanchored_days=int(daily.anchor_is_simulated.sum()), calendar_basis=calendar_basis,
                historical_control_validated=False, warnings=warnings,
                disclosure="Unanchored prices/volume and crash/control behaviour are invented scenarios, not market history")
            records.append(record)
            (destination/"metadata.json").write_text(json.dumps(record,indent=2))
            if not args.data_only:
                ready.append((record,destination,{name:music.features(frame,spec[0]) for name,spec in music.TRACKS.items()}))
            print(f"DATA {len(records)}/90 {period['id']}/{symbol}: {len(frame)} minute candles", flush=True)
    if ready:
        scales = music.calibrate([tables for _,_,tables in ready])
        (output/"calibration.json").write_text(json.dumps(scales,indent=2))
        for record,destination,tables in ready:
            binary,metrics = music.song(tables,scales)
            (destination/"song.mid").write_bytes(binary)
            metrics.to_csv(destination/"metrics.csv",index=False)
            record.update(status="GENERATED",calibration_pairs=90,duration_seconds=120,instruments=7)
            (destination/"metadata.json").write_text(json.dumps(record,indent=2))
            print(f"MIDI {record['period']}/{record['symbol']}",flush=True)
    (output/"configuration.json").write_text(json.dumps(config,indent=2))
    (output/"manifest.json").write_text(json.dumps(records,indent=2))
    pd.DataFrame(records).to_csv(output/"manifest.csv",index=False)
    with zipfile.ZipFile(output/"songs.zip","w",zipfile.ZIP_DEFLATED) as archive:
        for _,destination,_ in ready:
            archive.write(destination/"song.mid",(destination/"song.mid").relative_to(output))
        archive.write(output/"manifest.json","manifest.json")
    assert len(records)==90
    print(f"COMPLETE: 90/90 one-minute datasets; {len(ready)}/90 MIDI arrangements. {output}")


if __name__ == "__main__":
    main()
