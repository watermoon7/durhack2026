"""Read all completed v4 runs without moving or overwriting source datasets."""
import csv
import json
import math
import struct
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
LEGACY = REPO / "legacy"
TRACKS = {
    "bass": ("Bass", 24, 2), "drums": ("Drum kit", 36, 1),
    "synth_lead": ("Lead synth", 55, 3), "synth_pad": ("Pad synth", 55, 2),
    "guitar": ("Guitar", 48, 2), "synth_counter": ("Counter synth", 60, 2),
    "guitar_counter": ("Counter guitar", 52, 2)}


def vlq(value):
    parts = [value & 127]
    while value >> 7:
        value >>= 7
        parts.insert(0, (value & 127) | 128)
    return bytes(parts)


def split_midi(payload):
    if payload[:4] != b"MThd" or len(payload) < 14:
        raise ValueError("Invalid MIDI header")
    length, fmt, count, ppq = struct.unpack(">IHHH", payload[4:14])
    if length != 6 or fmt != 1 or ppq != 480:
        raise ValueError("Expected v4 format-1 MIDI at 480 PPQ")
    offset, chunks = 14, []
    for _ in range(count):
        if payload[offset:offset+4] != b"MTrk":
            raise ValueError("Missing MIDI track")
        size = struct.unpack(">I", payload[offset+4:offset+8])[0]
        data = payload[offset+8:offset+8+size]
        if len(data) != size:
            raise ValueError("Truncated MIDI track")
        chunks.append(data)
        offset += 8+size
    if offset != len(payload) or not chunks or chunks[0][:7] != b"\x00\xff\x51\x03\x07\xa1\x20":
        raise ValueError("Expected complete 120-BPM v4 MIDI")
    return chunks


def track_data(chunks, instrument):
    label = instrument.encode("ascii")
    prefix = b"\x00\xff\x03"+vlq(len(label))+label
    matches = [chunk for chunk in chunks if chunk.startswith(prefix)]
    if len(matches) != 1:
        raise ValueError(f"Missing or duplicated instrument track: {instrument}")
    return matches[0]


def instrument_midi(path, instrument):
    chunks = split_midi(path.read_bytes())
    # A SINGLE note track: the browser never receives the other six assets/parts.
    data = chunks[0][:7]+track_data(chunks, instrument)
    return b"MThd"+struct.pack(">IHHH", 6, 0, 1, 480)+b"MTrk"+struct.pack(">I", len(data))+data


def catalogue(legacy=LEGACY):
    config = json.loads((legacy/"local_market_periods.json").read_text())
    chosen, issues = {}, []
    roots = sorted(p for p in (legacy/"data").glob("*v4*") if p.is_dir())
    manifests = []
    for root in roots:
        manifests.extend(root.rglob("manifest.json"))
        manifests.extend(p for p in root.rglob("manifest.csv") if not p.with_suffix(".json").exists())
    for manifest in sorted(manifests, key=lambda p: (p.stat().st_mtime_ns, str(p))):
        try:
            if manifest.suffix == ".json":
                rows = json.loads(manifest.read_text())
            else:
                with manifest.open(newline="") as handle:
                    rows = list(csv.DictReader(handle))
            if not isinstance(rows, list):
                raise ValueError("Manifest must be a list of records")
            for row in rows:
                period = row.get("period") or row.get("event")
                symbol = row.get("symbol") or row.get("ticker")
                if not period or not symbol:
                    continue
                if not isinstance(period, str) or not isinstance(symbol, str):
                    continue
                if row.get("status") not in ("GENERATED", "ok"):
                    issues.append(f"{period}/{symbol}: {row.get('reason', row.get('status'))}")
                    continue
                folder = (manifest.parent/period/symbol).resolve()
                if not folder.is_relative_to(manifest.parent.resolve()):
                    raise ValueError("Unsafe manifest path")
                if not (folder/"metrics.csv").is_file():
                    issues.append(f"Missing metrics for {period}/{symbol}")
                    continue
                try:
                    chunks = split_midi((folder/"song.mid").read_bytes())
                    for instrument in TRACKS:
                        track_data(chunks, instrument)
                    fraction = float(row["simulated_fraction"])
                    if not math.isfinite(fraction) or not 0 <= fraction <= 1:
                        raise ValueError("Invalid simulation provenance")
                except (OSError, ValueError, KeyError, struct.error) as error:
                    issues.append(f"{period}/{symbol}: {error}")
                    continue
                # Newest SUCCESSFUL pair wins; failed later attempts never hide good data.
                chosen[(period, symbol)] = dict(id=f"{period}::{symbol}", ticker=symbol,
                    name=symbol, period_id=period, period=period.replace("_", " "),
                    simulated_fraction=fraction, run=manifest.parent.name,
                    calibration_pairs=row.get("calibration_pairs"), _folder=folder)
        except (OSError, ValueError, TypeError) as error:
            issues.append(f"{manifest.name} in {manifest.parent.name}: {error}")
    definitions = {p["id"]: p for p in config["periods"]}
    for period, _ in chosen:
        definitions.setdefault(period, dict(id=period, kind="unknown", market="", start="", end=""))
    periods = []
    for identifier, definition in definitions.items():
        assets = [v for (p, _), v in chosen.items() if p == identifier]
        periods.append(dict(id=identifier, name=identifier.replace("_", " ").title(),
            kind="stable" if definition["kind"]=="stable_candidate" else definition["kind"],
            market=definition["market"], start=definition["start"], end=definition["end"],
            available=len(assets), expected=6, complete=len(assets)==6))
    return dict(periods=periods, datasets=list(chosen.values()), diagnostics=dict(
        scanned_manifests=len(manifests), issues=issues,
        message="Missing pairs must be generated in Codespaces; no Q1-2020 sample fallback."))


def public_catalogue():
    result = catalogue()
    result["datasets"] = [{k:v for k,v in row.items() if not k.startswith("_")} for row in result["datasets"]]
    return result


def chart(folder, symbol):
    with (folder/"metrics.csv").open(newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r["track"]=="synth_lead"]
    rows.sort(key=lambda r: int(r["onset"]))
    if len(rows) != 240:
        raise ValueError("Expected 240 lead observations for the 240-beat chart")
    levels = [math.log(float(r["close"])) for r in rows]
    low, high = min(levels), max(levels)
    beats = [dict(date=r["source_end"], level=(v-low)/(high-low) if high>low else .5,
        activity=min(1., max(0., float(r["volatility"])/.01)),
        intensity=min(1., max(0., float(r["relative_volume"])/5))) for r,v in zip(rows, levels)]
    if not all(math.isfinite(v) for beat in beats for k,v in beat.items() if k != "date"):
        raise ValueError("Nonfinite chart values")
    return dict(source=symbol, beats=beats)


def make_router():
    from fastapi import APIRouter, HTTPException, Response
    router = APIRouter(prefix="/api/history", tags=["Historical collection"])

    def find(identifier):
        for row in catalogue()["datasets"]:
            if row["id"] == identifier:
                return row
        raise HTTPException(status_code=404, detail="Historical dataset unavailable; inspect catalogue diagnostics")

    @router.get("/catalogue")
    def get_catalogue():
        return public_catalogue()

    @router.get("/instruments")
    def instruments():
        return [dict(id=k, name=v[0], root_midi=v[1], octaves=v[2]) for k,v in TRACKS.items()]

    @router.get("/datasets/{dataset_id}/ir")
    def get_chart(dataset_id: str):
        row = find(dataset_id)
        try:
            return chart(row["_folder"], row["ticker"])
        except (OSError, ValueError, KeyError) as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @router.get("/midi")
    def get_midi(dataset_id: str, instrument_id: str):
        if instrument_id not in TRACKS:
            raise HTTPException(status_code=404, detail="Unknown historical instrument")
        row = find(dataset_id)
        try:
            payload = instrument_midi(row["_folder"]/"song.mid", instrument_id)
        except (OSError, ValueError, struct.error) as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        return Response(content=payload, media_type="audio/midi")

    return router
