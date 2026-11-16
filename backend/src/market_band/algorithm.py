"""The music algorithm: IR series -> notes -> Standard MIDI File bytes.

``render_notes`` dispatches on the instrument's role: ``lead`` (lead.py), ``bass`` (bass.py),
``pad`` and ``guitar`` (chords.py), and ``drum`` (here). The drum grid, per beat:
- tuning:   ``level`` picks a degree of the instrument's slice of the shared scale
- rhythm:   ``activity`` picks how many notes subdivide the beat (per-instrument
            ``subdivisions``), starting ``offset_beats`` into the beat
- velocity: ``intensity`` scales note velocity above VELOCITY_FLOOR; the frontend also
            maps velocity to filter brightness, so the two are one combined control
"""

import io

import mido

from market_band.bass import render_bass
from market_band.chords import render_guitar, render_pad
from market_band.config import (
    BEATS_PER_BAR,
    DEFAULT_GENRE,
    DRUM_ACCENT_NOTES,
    GENRES,
    NOTE_LEGATO,
    ORNAMENT_TRIGGER,
    ROCK_DRUM_ACCENTS,
    SCALE_INTERVALS,
    SCALE_ROOT_PITCH_CLASS,
    SONG_BEATS,
    TEMPO_BPM,
    TICKS_PER_BEAT,
    InstrumentConfig,
)
from market_band.ir import IRBeat, IRSeries
from market_band.lead import render_lead
from market_band.notes import Note, intensity_to_velocity

MIDI_NOTE_MAX = 127


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


def notes_to_midi(notes: list[Note], track_name: str, beats: int = SONG_BEATS) -> bytes:
    """Encode notes as a single-track Standard MIDI File (type 0) exactly ``beats`` long.

    The end-of-track marker sits at ``beats``, so every part loops on the same bar line
    wherever its last note ends.
    """
    if not notes:
        raise ValueError("cannot encode an empty note list")
    if beats < 1:
        raise ValueError(f"beats must be positive, got {beats}")
    last_end = max(note.start_beat + note.duration_beats for note in notes)
    if last_end > beats + 1e-9:
        raise ValueError(f"a note ends at beat {last_end:g}, after the song's {beats} beats")
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
    end_tick = beats * TICKS_PER_BEAT
    track.append(mido.MetaMessage("end_of_track", time=end_tick - previous_tick))

    midi_file = mido.MidiFile(type=0, ticks_per_beat=TICKS_PER_BEAT)
    midi_file.tracks.append(track)
    buffer = io.BytesIO()
    midi_file.save(file=buffer)
    return buffer.getvalue()


def tom_fill(ir: IRSeries, notes: list[Note]) -> list[Note]:
    """Replace the snare on every busy fourth beat of a bar with a four-tom fill, high to low."""
    toms = [DRUM_ACCENT_NOTES[name] for name in ("tom_hh", "tom_h", "tom_m", "tom_l")]
    busy = {
        i
        for i, beat in enumerate(ir.beats)
        if i % BEATS_PER_BAR == BEATS_PER_BAR - 1 and beat.activity >= ORNAMENT_TRIGGER
    }
    kept = [n for n in notes if int(n.start_beat) not in busy]
    step = 1.0 / len(toms)
    for index in sorted(busy):
        velocity = intensity_to_velocity(ir.beats[index].intensity)
        kept.extend(
            Note(index + k * step, step * NOTE_LEGATO, tom, velocity) for k, tom in enumerate(toms)
        )
    return sorted(kept, key=lambda n: n.start_beat)


def crashes(ir: IRSeries, notes: list[Note]) -> list[Note]:
    """Add a crash on beat 1 of every bar that follows a busy bar (bar 1 follows the last)."""
    bars = len(ir.bars)
    assert bars * BEATS_PER_BAR == len(ir.beats), "bars and beats disagree"
    added = list(notes)
    for bar in range(bars):
        previous = (bar - 1) % bars
        window = ir.beats[previous * BEATS_PER_BAR : (previous + 1) * BEATS_PER_BAR]
        if sum(b.activity for b in window) / len(window) >= ORNAMENT_TRIGGER:
            start = bar * BEATS_PER_BAR
            velocity = intensity_to_velocity(ir.beats[start].intensity)
            added.append(Note(float(start), NOTE_LEGATO, DRUM_ACCENT_NOTES["crash"], velocity))
    return sorted(added, key=lambda n: (n.start_beat, n.midi))


def drum_accents(ir: IRSeries, instrument: InstrumentConfig, notes: list[Note]) -> list[Note]:
    """Apply the instrument's Rock accent (tom fill or crash), if it has one."""
    if instrument.role != "drum":
        raise ValueError(f"{instrument.id} is not a drum")
    accent = ROCK_DRUM_ACCENTS.get(instrument.id)
    if accent == "fill":
        return tom_fill(ir, notes)
    if accent == "crash":
        return crashes(ir, notes)
    return notes


def render_notes(
    ir: IRSeries, instrument: InstrumentConfig, genre: str = DEFAULT_GENRE
) -> list[Note]:
    """Render one instrument's part with the renderer for its role, in the given genre."""
    assert len(ir.beats) > 0, "IR series must contain beats"
    if genre not in {g.id for g in GENRES}:
        raise ValueError(f"unknown genre '{genre}'")
    if instrument.role == "lead":
        return render_lead(ir, instrument)
    if instrument.role == "bass":
        return render_bass(ir, instrument)
    if instrument.role == "pad":
        return render_pad(ir, instrument)
    if instrument.role == "guitar":
        return render_guitar(ir, instrument, genre)
    if instrument.role == "drum":
        notes = ir_to_notes(ir, instrument)
        return drum_accents(ir, instrument, notes) if genre == "rock" else notes
    raise ValueError(f"{instrument.id}: unknown role '{instrument.role}'")


def render_midi(
    ir: IRSeries, instrument: InstrumentConfig, genre: str = DEFAULT_GENRE
) -> bytes:
    """Run the full algorithm: IR series + instrument + genre -> .mid file bytes."""
    notes = render_notes(ir, instrument, genre)
    return notes_to_midi(notes, track_name=f"{ir.source}:{instrument.id}", beats=len(ir.beats))
