"""Five-track market sonification. Run: python Market_Events_Five_Tracks.py
Requires the existing Market_Events_to_MIDI.py, numpy and pandas.
Offline descriptive mappings; no motifs, fabricated bars, or audio rendering.
"""
from pathlib import Path
import argparse, hashlib, json, struct, zipfile
import numpy as np
import pandas as pd
import Market_Events_to_MIDI as base

ROOT = Path(__file__).resolve().parent
BARS, BPM, TPB = 60, 120, 480
SHAPE_WEIGHT = 0.80
EMA_SPAN = 12
ROOT_HYSTERESIS = 1.0
SWING = 0.08
SCALE = (0, 2, 3, 5, 7, 8, 10)
# name: (onsets, zero-based channel, GM program, low pitch, high pitch)
TRACKS = {"bass": (60, 0, 33, 28, 48), "synth_lead": (240, 1, 81, 55, 84),
          "drums": (960, 9, None, 0, 0), "synth_pad": (60, 2, 89, 55, 79),
          "guitar": (480, 3, 24, 48, 72)}
FIELDS = ("gradient_per_hour", "volatility", "shock", "drawdown")


def features(frame, count, previous_high):
    edges = np.arange(count + 1) * len(frame) // count
    if len(frame) < count:
        raise ValueError("Insufficient genuine bars; no upsampling allowed")
    returns = np.log(frame.close).diff()
    returns.iloc[0] = np.log(frame.close.iloc[0] / frame.open.iloc[0])
    running_high = frame.high.cummax().clip(lower=previous_high)
    drawdown = (1 - frame.close / running_high).clip(lower=0)
    rows = []
    for i, (left, right) in enumerate(zip(edges[:-1], edges[1:])):
        chunk, r = frame.iloc[left:right], returns.iloc[left:right]
        travel = float(r.abs().sum())
        rows.append(dict(candle=i, source_start=str(chunk.index[0]), source_end=str(chunk.index[-1]),
            source_count=len(chunk), trading_hours=len(chunk)/60,
            open=chunk.open.iloc[0], high=chunk.high.max(), low=chunk.low.min(),
            close=chunk.close.iloc[-1], volume=chunk.volume.sum(),
            volatility=float(np.sqrt(np.mean(np.square(r)))),
            shock=float(r.abs().max()), drawdown=float(drawdown.iloc[left:right].max()),
            efficiency=min(1.0, abs(float(r.sum()))/travel) if travel else 0.0))
    result = pd.DataFrame(rows)
    result["ema"] = result.close.ewm(span=EMA_SPAN, adjust=False).mean()
    result["trend"] = np.log(result.ema/frame.open.iloc[0])
    result["ema_gradient"] = np.log(result.ema).diff().abs().fillna(0)
    result["gradient_per_hour"] = result.ema_gradient/result.trading_hours
    return result


def scales(prepared):
    # Shared calibration pooled across accepted events, separately by instrument.
    return {track: {field: max(1e-12, float(np.quantile(np.concatenate(
        [tables[track][field].to_numpy() for tables in prepared.values()]), .95)))
        for field in FIELDS} for track in TRACKS}


def blend(values, shared):
    local = max(1e-12, float(values.quantile(.95)))
    return (SHAPE_WEIGHT * np.clip(values/local, 0, 1) +
            (1-SHAPE_WEIGHT) * np.clip(values/shared, 0, 1))


def root_sequence(table, extent):
    allowed = [n for n in range(28, 49) if n % 12 in (0, 5, 7, 8)]
    roots = []
    for value in table.trend:
        target = 28 + (float(np.clip(value/extent, -1, 1))+1)*10
        candidate = min(allowed, key=lambda n: abs(n-target))
        if roots and abs(roots[-1]-target) <= abs(candidate-target)+ROOT_HYSTERESIS:
            candidate = roots[-1]
        roots.append(candidate)
    return roots


def chord(root, tension, include_seventh=False):
    degree = SCALE.index(root % 12)
    steps = [0, 2, 4]
    if include_seventh or tension >= .30:
        steps.append(6)
    if tension >= .65:
        steps.append(8)
    return tuple(SCALE[(degree+step) % 7] for step in steps)


def voicing(classes, previous):
    # Unique upper-register notes; select nearby voices, not a preset progression.
    used = []
    for pc in classes:
        candidates = [n for n in range(55, 80) if n % 12 == pc and n not in used]
        note = min(candidates, key=lambda n: min(abs(n-p) for p in previous) if previous else abs(n-67))
        used.append(note)
    return sorted(used)


def make_song(tables, calibration):
    tables = {name: table.copy() for name, table in tables.items()}
    for name, table in tables.items():
        for field in FIELDS:
            table[field+"_strength"] = blend(table[field], calibration[name][field])
    extent = max(1e-12, max(float(t.trend.abs().max()) for t in tables.values()))
    roots = root_sequence(tables["bass"], extent)
    tensions = tables["synth_pad"].drawdown_strength.to_numpy()
    end = BARS*4*TPB
    tempo = int(round(60_000_000/BPM))
    seconds_per_tick = tempo/1_000_000/TPB
    tracks = [base.midi_track([(0, 0, b"\xff\x51\x03"+tempo.to_bytes(3, "big")),
        (0, 0, b"\xff\x58\x04\x04\x02\x18\x08")], end)]
    rows = []
    for name, (count, channel, program, low, high) in TRACKS.items():
        label = name.encode("ascii")
        messages = [(0, 0, b"\xff\x03"+base.variable_length(len(label))+label)]
        if program is not None:
            messages.append((0, 0, bytes([0xC0|channel, program])))
        per_bar, slot = count//BARS, end/count
        previous_pitch, previous_chord = None, []
        for i, row in tables[name].iterrows():
            bar, position = i//per_bar, i%per_bar
            root, tension = int(roots[bar]), float(tensions[bar])
            harmony = chord(root, tension, include_seventh=True)
            stress = float(row.volatility_strength)
            shift = SWING*stress if name in ("drums", "synth_lead", "guitar") and position%2 else 0
            start = int(round((i+shift)*slot))
            accent, shock_boost, gain = 1.0, 0.0, 0.4 if name == "synth_lead" else 1.0
            gate = .85-.50*stress
            if name == "bass":
                pitches, gate = [root], .85
            elif name == "drums":
                if position in (0, 8):
                    pitches, accent = [36], 1.0
                elif position in (4, 12):
                    pitches, accent = [38], .95
                else:
                    pitches, accent = [42], .68 if position%2==0 else .45
                gate = .30
                shock_boost = 12*float(np.clip((row.shock_strength-.85)/.15, 0, 1))
            elif name == "synth_pad":
                pitches = voicing(chord(root, tension), previous_chord)
                previous_chord = pitches
                gate, gain = .95, .65
            else:
                target = low+(float(np.clip(row.trend/extent, -1, 1))+1)*.5*(high-low)
                candidates = [n for n in range(low, high+1) if n%12 in SCALE and
                    (name != "synth_lead" or position%2 or n%12 in harmony)]
                if previous_pitch is not None:
                    nearby = [n for n in candidates if abs(n-previous_pitch)<=5]
                    candidates = nearby or candidates
                pitch = min(candidates, key=lambda n: abs(n-target)+
                    (.6*abs(n-previous_pitch) if previous_pitch is not None else 0))
                pitches = [pitch]
                previous_pitch = pitch
                if name == "guitar":
                    gate, gain = .25+.60*float(row.efficiency), .75
            stop = min(end, start+max(1, int(slot*gate)))
            velocity_base = 35+80*float(row.gradient_per_hour_strength)
            velocity = int(np.clip(round((velocity_base+shock_boost)*accent*gain), 1, 127))
            for pitch in pitches:
                messages += [(start, 2, bytes([0x90|channel, pitch, velocity])),
                             (stop, 1, bytes([0x80|channel, pitch, 0]))]
                rows.append(dict(track=name, onset=i, bar=bar+1, pitch_midi=pitch,
                    velocity=velocity, velocity_base=velocity_base, accent=accent,
                    shock_boost=shock_boost, track_gain=gain, harmony_root_midi=root,
                    chord_pitch_classes=";".join(map(str, harmony)), tension=tension,
                    gate_fraction=gate, start_seconds=start*seconds_per_tick,
                    duration_seconds=(stop-start)*seconds_per_tick,
                    rhythm_offset_fraction=shift, **row.to_dict()))
        tracks.append(base.midi_track(messages, end))
    events = pd.DataFrame(rows)
    for name, (count, *_) in TRACKS.items():
        assert events.loc[events.track==name, "onset"].nunique()==count
    assert ((events.start_seconds+events.duration_seconds)<=120).all()
    return b"MThd"+struct.pack(">IHHH", 6, 1, len(tracks), TPB)+b"".join(tracks), events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", help="Optional local SPY one-minute OHLCV file")
    parser.add_argument("--output", default=str(ROOT/"data/market_events_v3"))
    args = parser.parse_args()
    source = base.get_source(args.source)
    data = base.read_source(source)
    with source.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    prepared, records = {}, {}
    for name, start, end in base.EVENTS:
        record = dict(event=name, requested_start=start, requested_end_exclusive=end,
            sha256=digest, source=base.PROVENANCE if not args.source else str(source),
            symbol="SPY", arrangement="five_tracks_v3", shape_weight=SHAPE_WEIGHT)
        records[name] = record
        destination = output/name
        destination.mkdir(exist_ok=True)
        for filename in ("song.mid", "metrics.csv", "source.csv"):
            (destination/filename).unlink(missing_ok=True)
        try:
            frame = data.loc[(data.index>=start)&(data.index<end)]
            gaps = base.validate(frame, start, end)
            history = data.loc[data.index<start]
            prior_dates = history.index.normalize().unique()[-60:]
            history = history.loc[history.index.normalize().isin(prior_dates)]
            previous_high = max(float(frame.open.iloc[0]), float(history.high.max())) if len(history) else float(frame.open.iloc[0])
            prepared[name] = {track: features(frame, spec[0], previous_high) for track, spec in TRACKS.items()}
            record.update(status="prepared", source_rows=len(frame), tolerated_intraday_gaps=gaps,
                actual_start=str(frame.index[0]), actual_end=str(frame.index[-1]),
                prior_sessions=len(prior_dates), previous_high=previous_high)
        except ValueError as error:
            record.update(status="FAILED", reason=str(error))
    if not prepared:
        pd.DataFrame(records.values()).to_csv(output/"manifest.csv", index=False)
        raise SystemExit("No events passed validation; inspect manifest.csv")
    calibration = scales(prepared)
    (output/"calibration.json").write_text(json.dumps(calibration, indent=2))
    successful = []
    for name, tables in prepared.items():
        record, destination = records[name], output/name
        binary, events = make_song(tables, calibration)
        frame = data.loc[(data.index>=record["requested_start"])&(data.index<record["requested_end_exclusive"])]
        frame.to_csv(destination/"source.csv", index_label="timestamp")
        events.to_csv(destination/"metrics.csv", index=False)
        (destination/"song.mid").write_bytes(binary)
        record.update(status="ok", duration_seconds=120, note_count=len(events), onset_count=1800)
        successful.append(destination/"song.mid")
        print(f"OK {name}: {len(events)} notes, five named instrument tracks")
    pd.DataFrame(records.values()).to_csv(output/"manifest.csv", index=False)
    with zipfile.ZipFile(output/"market_event_midis_v3.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in successful:
            archive.write(path, path.relative_to(output))
    print(f"Successful events: {len(successful)}/{len(base.EVENTS)}")
    print(f"MIDI ZIP: {output/'market_event_midis_v3.zip'}")
    if len(successful)!=len(base.EVENTS):
        raise SystemExit("Partial collection only; inspect manifest.csv")


if __name__ == "__main__":
    main()
