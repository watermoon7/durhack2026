"""Read the committed legacy event arrangements for the interactive stage."""

import csv
from functools import lru_cache

import mido
from fastapi import APIRouter, HTTPException, Response

from market_band.algorithm import Note, notes_to_midi
from market_band.config import BACKEND_ROOT, INSTRUMENTS
from market_band.ir import IRBeat, IRSeries

EVENT_DIR = BACKEND_ROOT.parent / "legacy" / "data" / "market_events_v3"
PARTS = {
    "bass": "Bass",
    "synth_lead": "Lead",
    "drums": "Drums",
    "synth_pad": "Pad",
    "guitar": "Guitar",
}
router = APIRouter(prefix="/api/events")


@lru_cache(maxsize=1)
def catalog() -> list[dict[str, str]]:
    """Load the event catalog from the legacy manifest."""
    with (EVENT_DIR / "manifest.csv").open(newline="") as file:
        return [
            dict(
                id=row["event"],
                name=row["event"][5:].replace("_", " ").title(),
                start=row["actual_start"][:10],
                end=row["actual_end"][:10],
                symbol=row["symbol"],
            )
            for row in csv.DictReader(file)
            if row["status"] == "ok"
        ]


def event_info(event_id: str) -> dict[str, str]:
    """Resolve only manifest-listed events, preventing arbitrary file access."""
    for event in catalog():
        if event["id"] == event_id:
            return event
    raise HTTPException(404, "Unknown event")


@lru_cache(maxsize=50)
def part_notes(event_id: str, part_id: str) -> tuple[Note, ...]:
    """Decode a legacy part into beat-based notes, retaining chords and timing."""
    event_info(event_id)
    if part_id not in PARTS:
        raise HTTPException(404, "Unknown event part")
    midi = mido.MidiFile(EVENT_DIR / event_id / "song.mid")
    track = next(t for t in midi.tracks if t.name == part_id)
    active: dict[tuple[int, int], tuple[int, int]] = {}
    notes = []
    tick = 0
    for message in track:
        tick += message.time
        if message.type == "note_on" and message.velocity > 0:
            active[(message.channel, message.note)] = (tick, message.velocity)
        elif message.type in ("note_on", "note_off"):
            start = active.pop((message.channel, message.note), None)
            if start is not None:
                notes.append(
                    Note(
                        start[0] / midi.ticks_per_beat,
                        (tick - start[0]) / midi.ticks_per_beat,
                        message.note,
                        start[1],
                    )
                )
    return tuple(sorted(notes, key=lambda note: note.start_beat))


@router.get("")
def list_events() -> list[dict[str, str]]:
    """List the ten available market events."""
    return catalog()


@router.get("/{event_id}/datasets")
def list_parts(event_id: str) -> list[dict[str, str]]:
    """Expose the event's original musical parts as draggable sources."""
    event = event_info(event_id)
    return [
        dict(
            id=key,
            ticker=name.upper(),
            name=f"{event['name']} · {name}",
            period=f"{event['start']} to {event['end']}",
        )
        for key, name in PARTS.items()
    ]


@router.get("/{event_id}/datasets/{part_id}/ir")
def part_ir(event_id: str, part_id: str) -> IRSeries:
    """Summarise note contours per beat; these are musical rather than price charts."""
    notes = part_notes(event_id, part_id)
    buckets: dict[int, list[Note]] = {}
    for note in notes:
        buckets.setdefault(int(note.start_beat), []).append(note)
    low, high = min(n.midi for n in notes), max(n.midi for n in notes)
    count = max(1, max(len(bucket) for bucket in buckets.values()))
    beats = []
    level = 0.5
    for index in range(240):
        bucket = buckets.get(index, [])
        if bucket:
            level = (sum(n.midi for n in bucket) / len(bucket) - low) / (high - low or 1)
        beats.append(
            IRBeat(
                date=f"Beat {index + 1}",
                level=level,
                activity=len(bucket) / count,
                intensity=max((n.velocity / 127 for n in bucket), default=0),
            )
        )
    return IRSeries(source=PARTS[part_id], beats=beats)


@router.get("/{event_id}/midi")
def part_midi(event_id: str, dataset_id: str, instrument_id: str) -> Response:
    """Render a chosen legacy part for any stage instrument."""
    instrument = next((i for i in INSTRUMENTS if i.id == instrument_id), None)
    if instrument is None:
        raise HTTPException(404, "Unknown instrument")
    notes = part_notes(event_id, dataset_id)
    drum_pitch = {"kick": 36, "snare": 38, "hihat": 42}
    if dataset_id == "drums" and instrument_id in drum_pitch:
        notes = tuple(n for n in notes if n.midi == drum_pitch[instrument_id])
    rendered = []
    for note in notes:
        pitch = note.midi
        if instrument_id in drum_pitch:
            pitch = instrument.root_midi
        else:
            while pitch < instrument.root_midi:
                pitch += 12
            while pitch > instrument.root_midi + instrument.octaves * 12:
                pitch -= 12
        rendered.append(Note(note.start_beat, note.duration_beats, pitch, note.velocity))
    return Response(notes_to_midi(rendered, f"{event_id}:{dataset_id}"), media_type="audio/midi")
