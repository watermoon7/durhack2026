"""Historical catalogue: accept completed assets even before the run manifest exists."""
import csv
import json
import math
import struct
from pathlib import Path


def legacy_root():
    candidates = [Path.cwd(), *Path.cwd().parents, *Path(__file__).resolve().parents]
    for root in candidates:
        if (root/"legacy/local_market_periods.json").is_file():
            return root/"legacy"
    return Path(__file__).resolve().parents[3]/"legacy"


LEGACY = legacy_root()
TRACKS = {"bass": ("Bass",24,2), "drums": ("Drum kit",36,1),
    "synth_lead": ("Lead synth",55,3), "synth_pad": ("Pad synth",55,2),
    "guitar": ("Guitar",48,2), "synth_counter": ("Counter synth",60,2),
    "guitar_counter": ("Counter guitar",52,2)}


def vlq(value):
    parts = [value & 127]
    while value >> 7:
        value >>= 7
        parts.insert(0,(value & 127)|128)
    return bytes(parts)


def split_midi(payload):
    if len(payload)<14 or payload[:4]!=b"MThd":
        raise ValueError("Invalid MIDI header")
    size,fmt,count,ppq = struct.unpack(">IHHH",payload[4:14])
    if (size,fmt,ppq)!=(6,1,480):
        raise ValueError("Expected v4 format-1 MIDI at 480 PPQ")
    offset,chunks = 14,[]
    for _ in range(count):
        if payload[offset:offset+4]!=b"MTrk" or len(payload)<offset+8:
            raise ValueError("Missing MIDI track")
        size = struct.unpack(">I",payload[offset+4:offset+8])[0]
        chunk = payload[offset+8:offset+8+size]
        if len(chunk)!=size:
            raise ValueError("Truncated MIDI track")
        chunks.append(chunk)
        offset += size+8
    if offset!=len(payload) or not chunks or chunks[0][:7]!=b"\x00\xff\x51\x03\x07\xa1\x20":
        raise ValueError("Expected complete 120-BPM v4 MIDI")
    return chunks


def track_name(data):
    """Read MIDI events: channel setup may precede the track-name meta event."""
    offset,running = 0,None
    def number(position):
        value = 0
        for _ in range(4):
            if position>=len(data):
                raise ValueError("Truncated MIDI variable-length number")
            byte = data[position]
            position += 1
            value = (value<<7)|(byte&127)
            if byte<128:
                return value,position
        raise ValueError("Invalid MIDI variable-length number")
    while offset<len(data):
        _,offset = number(offset)
        if offset>=len(data):
            raise ValueError("Truncated MIDI event")
        status = data[offset]
        if status>=128:
            offset += 1
            if status<240:
                running = status
        elif running is not None:
            status = running
        else:
            raise ValueError("Invalid MIDI running status")
        if status==255:
            if offset>=len(data):
                raise ValueError("Truncated MIDI meta event")
            kind = data[offset]
            size,offset = number(offset+1)
            end = offset+size
            if end>len(data):
                raise ValueError("Truncated MIDI meta payload")
            if kind==3:
                return data[offset:end]
            if kind==47:
                return None
            offset = end
        elif status in (240,247):
            size,offset = number(offset)
            offset += size
            running = None
        elif 128<=status<240:
            offset += 1 if status&240 in (192,208) else 2
        else:
            raise ValueError("Unsupported MIDI status")
        if offset>len(data):
            raise ValueError("Truncated MIDI channel event")
    return None


def track_data(chunks,instrument):
    label = instrument.encode("ascii")
    matches = [c for c in chunks if track_name(c)==label]
    if len(matches)!=1:
        raise ValueError(f"Missing or duplicated instrument track: {instrument}")
    return matches[0]


def instrument_midi(path,instrument):
    chunks = split_midi(path.read_bytes())
    data = chunks[0][:7]+track_data(chunks,instrument)
    return b"MThd"+struct.pack(">IHHH",6,0,1,480)+b"MTrk"+struct.pack(">I",len(data))+data


def catalogue(legacy=LEGACY):
    config = json.loads((legacy/"local_market_periods.json").read_text())
    files = []
    for root in (legacy/"data").glob("*v4*"):
        if root.is_dir():
            files.extend(root.rglob("manifest.json"))
            files.extend(p for p in root.rglob("manifest.csv") if not p.with_suffix(".json").exists())
            files.extend(root.rglob("metadata.json"))
    chosen,issues = {},[]
    pending = 0
    for path in sorted(set(files),key=lambda p:(p.stat().st_mtime_ns,str(p))):
        try:
            if path.suffix==".json":
                rows = json.loads(path.read_text())
                if path.name=="metadata.json" and isinstance(rows,dict):
                    rows = [rows]
            else:
                with path.open(newline="") as handle:
                    rows = list(csv.DictReader(handle))
            if not isinstance(rows,list):
                raise ValueError("Expected records")
            for row in rows:
                if not isinstance(row,dict):
                    continue
                period,symbol = row.get("period") or row.get("event"),row.get("symbol") or row.get("ticker")
                if not isinstance(period,str) or not isinstance(symbol,str):
                    continue
                if row.get("status") not in ("GENERATED","ok"):
                    if path.name=="metadata.json" and row.get("status")=="DATASET_READY":
                        pending += 1
                    elif path.name!="metadata.json":
                        issues.append(f"{period}/{symbol}: {row.get('reason',row.get('status'))}")
                    continue
                folder = path.parent if path.name=="metadata.json" else path.parent/period/symbol
                folder = folder.resolve()
                if not folder.is_relative_to(path.parent.resolve()):
                    raise ValueError("Unsafe manifest path")
                try:
                    if not (folder/"metrics.csv").is_file():
                        raise ValueError("Metrics not ready")
                    chunks = split_midi((folder/"song.mid").read_bytes())
                    for name in TRACKS:
                        track_data(chunks,name)
                    fraction = float(row["simulated_fraction"])
                    if not math.isfinite(fraction) or not 0<=fraction<=1:
                        raise ValueError("Invalid simulation provenance")
                except (OSError,ValueError,KeyError,struct.error) as error:
                    issues.append(f"{period}/{symbol}: {error}")
                    continue
                chosen[(period,symbol)] = dict(id=f"{period}::{symbol}",ticker=symbol,name=symbol,
                    period_id=period,period=period.replace("_"," "),simulated_fraction=fraction,
                    run=folder.parent.parent.name,calibration_pairs=row.get("calibration_pairs"),_folder=folder)
        except (OSError,ValueError,TypeError) as error:
            issues.append(f"{path.parent.name}/{path.name}: {error}")
    definitions = {p["id"]:p for p in config["periods"]}
    for period,_ in chosen:
        definitions.setdefault(period,dict(id=period,kind="unknown",market="",start="",end=""))
    periods = []
    for key,p in definitions.items():
        count = sum(period==key for period,_ in chosen)
        periods.append(dict(id=key,name=key.replace("_"," ").title(),
            kind="stable" if p["kind"]=="stable_candidate" else p["kind"],
            market=p["market"],start=p["start"],end=p["end"],available=count,expected=6,complete=count==6))
    message = f"{pending} per-asset records have candles but are awaiting MIDI. Click Refresh generated data as MIDI finishes. No demo fallback."
    return dict(periods=periods,datasets=list(chosen.values()),diagnostics=dict(
        scanned_manifests=len(files),issues=list(dict.fromkeys(issues)),message=message))


def public_catalogue():
    result = catalogue()
    result["datasets"] = [{k:v for k,v in row.items() if not k.startswith("_")} for row in result["datasets"]]
    return result


def chart(folder,symbol):
    with (folder/"metrics.csv").open(newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r["track"]=="synth_lead"]
    rows.sort(key=lambda r:int(r["onset"]))
    if len(rows)!=240:
        raise ValueError("Expected 240 lead observations")
    levels = [math.log(float(r["close"])) for r in rows]
    low,high = min(levels),max(levels)
    beats = [dict(date=r["source_end"],level=(v-low)/(high-low) if high>low else .5,
        activity=min(1.,max(0.,float(r["volatility"])/.01)),
        intensity=min(1.,max(0.,float(r["relative_volume"])/5))) for r,v in zip(rows,levels)]
    if not all(math.isfinite(v) for b in beats for k,v in b.items() if k!="date"):
        raise ValueError("Nonfinite chart values")
    return dict(source=symbol,beats=beats)


def make_router():
    from fastapi import APIRouter,HTTPException,Response
    router = APIRouter(prefix="/api/history",tags=["Historical collection"])
    def find(identifier):
        for row in catalogue()["datasets"]:
            if row["id"]==identifier:
                return row
        raise HTTPException(404,"Dataset not playable yet; check generation diagnostics")
    @router.get("/catalogue")
    def get_catalogue():
        try:
            return public_catalogue()
        except (OSError,ValueError) as error:
            raise HTTPException(503,str(error)) from error
    @router.get("/instruments")
    def instruments():
        return [dict(id=k,name=v[0],root_midi=v[1],octaves=v[2]) for k,v in TRACKS.items()]
    @router.get("/datasets/{dataset_id}/ir")
    def get_chart(dataset_id:str):
        row = find(dataset_id)
        try:
            return chart(row["_folder"],row["ticker"])
        except (OSError,ValueError,KeyError) as error:
            raise HTTPException(503,str(error)) from error
    @router.get("/midi")
    def get_midi(dataset_id:str,instrument_id:str):
        if instrument_id not in TRACKS:
            raise HTTPException(404,"Unknown historical instrument")
        row = find(dataset_id)
        try:
            payload = instrument_midi(row["_folder"]/"song.mid",instrument_id)
        except (OSError,ValueError,struct.error) as error:
            raise HTTPException(503,str(error)) from error
        return Response(content=payload,media_type="audio/midi")
    return router
