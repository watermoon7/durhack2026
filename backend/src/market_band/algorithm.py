"""The music algorithm: IR series -> notes -> Standard MIDI File bytes.

Per beat, deliberately simple for the first demo:
- pitch:    ``level`` picks a degree of the instrument's slice of the shared scale
- rhythm:   ``activity`` picks how many notes subdivide the beat (per-instrument
            ``subdivisions``), starting ``offset_beats`` into the beat
- velocity: ``intensity`` scales note velocity above VELOCITY_FLOOR; the frontend also
            maps velocity to filter brightness, so the two are one combined control
"""

import io
from dataclasses import dataclass

import mido

from market_band.config import (
    MIDI_VELOCITY_MAX,
    NOTE_LEGATO,
    SCALE_INTERVALS,
    SCALE_ROOT_PITCH_CLASS,
    TEMPO_BPM,
    TICKS_PER_BEAT,
    VELOCITY_FLOOR,
    InstrumentConfig,
)
from market_band.ir import IRBeat, IRSeries

MIDI_NOTE_MAX = 127


@dataclass(frozen=True)
class Note:
    """A single note in beat time."""

    start_beat: float
    duration_beats: float
    midi: int
    velocity: int


def scale_notes(instrument: InstrumentConfig) -> tuple[int, ...]:
    """List the MIDI notes of the shared scale across the instrument's range, low to high."""
    if instrument.root_midi % 12 != SCALE_ROOT_PITCH_CLASS:
        raise ValueError(f"{instrument.id}: root_midi is not on the scale root")
    if instrument.octaves < 1:
        raise ValueError(f"{instrument.id}: octaves must be >= 1")
    top = instrument.root_midi + 12 * instrument.octaves
    if top > MIDI_NOTE_MAX:
        raise ValueError(f"{instrument.id}: range exceeds MIDI note {MIDI_NOTE_MAX}")
    notes = [
        instrument.root_midi + 12 * octave + interval
        for octave in range(instrument.octaves)
        for interval in SCALE_INTERVALS
    ]
    notes.append(top)
    return tuple(notes)


def intensity_to_velocity(intensity: float) -> int:
    """Map IR intensity in [0, 1] to a MIDI velocity, never quieter than VELOCITY_FLOOR."""
    if not 0.0 <= intensity <= 1.0:
        raise ValueError(f"intensity {intensity} outside [0, 1]")
    velocity = round(MIDI_VELOCITY_MAX * (VELOCITY_FLOOR + (1.0 - VELOCITY_FLOOR) * intensity))
    assert 1 <= velocity <= MIDI_VELOCITY_MAX, "velocity must be a sounding MIDI velocity"
    return velocity


def beat_to_notes(
    index: int, beat: IRBeat, scale: tuple[int, ...], instrument: InstrumentConfig
) -> list[Note]:
    """Render one IR beat as ``count`` equal-length notes on the same pitch.

    Notes fill the part of the beat after ``offset_beats``, so they never spill into the next.
    """
    assert index >= 0, "beat index must be non-negative"
    assert len(scale) > 0, "scale must contain notes"
    subdivisions = instrument.subdivisions
    if not subdivisions or min(subdivisions) < 1:
        raise ValueError(f"{instrument.id}: subdivisions must be positive and non-empty")
    if not 0.0 <= instrument.offset_beats < 1.0:
        raise ValueError(f"{instrument.id}: offset_beats must be in [0, 1)")
    midi = scale[round(beat.level * (len(scale) - 1))]
    slot = min(int(beat.activity * len(subdivisions)), len(subdivisions) - 1)
    count = subdivisions[slot]
    velocity = intensity_to_velocity(beat.intensity)
    step = (1.0 - instrument.offset_beats) / count
    return [
        Note(
            start_beat=index + instrument.offset_beats + n * step,
            duration_beats=step * NOTE_LEGATO,
            midi=midi,
            velocity=velocity,
        )
        for n in range(count)
    ]


def ir_to_notes(ir: IRSeries, instrument: InstrumentConfig) -> list[Note]:
    """Render a whole IR series for one instrument, one beat per IR row."""
    assert len(ir.beats) > 0, "IR series must contain beats"
    scale = scale_notes(instrument)
    notes: list[Note] = []
    for index, beat in enumerate(ir.beats):
        notes.extend(beat_to_notes(index, beat, scale, instrument))
    return notes


def notes_to_midi(notes: list[Note], track_name: str) -> bytes:
    """Encode monophonic notes as a single-track Standard MIDI File (type 0)."""
    if not notes:
        raise ValueError("cannot encode an empty note list")
    events: list[tuple[int, int, mido.Message]] = []  # (tick, order, message); off before on
    for note in notes:
        start = round(note.start_beat * TICKS_PER_BEAT)
        end = round((note.start_beat + note.duration_beats) * TICKS_PER_BEAT)
        if end <= start:
            raise ValueError(f"note at beat {note.start_beat} has no duration in ticks")
        events.append((start, 1, mido.Message("note_on", note=note.midi, velocity=note.velocity)))
        events.append((end, 0, mido.Message("note_off", note=note.midi, velocity=0)))
    events.sort(key=lambda event: (event[0], event[1]))

    track = mido.MidiTrack()
    track.append(mido.MetaMessage("track_name", name=track_name, time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(TEMPO_BPM), time=0))
    previous_tick = 0
    for tick, _order, message in events:
        track.append(message.copy(time=tick - previous_tick))
        previous_tick = tick
    track.append(mido.MetaMessage("end_of_track", time=0))

    midi_file = mido.MidiFile(type=0, ticks_per_beat=TICKS_PER_BEAT)
    midi_file.tracks.append(track)
    buffer = io.BytesIO()
    midi_file.save(file=buffer)
    return buffer.getvalue()


def render_midi(ir: IRSeries, instrument: InstrumentConfig) -> bytes:
    """Run the full algorithm: IR series + instrument -> .mid file bytes."""
    return notes_to_midi(ir_to_notes(ir, instrument), track_name=f"{ir.source}:{instrument.id}")
