"""The bass: works around the root of its stock's chord for each bar.

Beat 1 of every bar plays the root. Swing moves the other beats between root, fifth and octave;
activity decides one note or two eighths per beat, and calm beats on the same pitch are held.
When the next bar's chord differs, beat 4 steps into its root. No pitch may sound more than
BASS_MAX_REPEATS times in a row.
"""

from market_band.config import (
    BASS_MAX_REPEATS,
    BEATS_PER_BAR,
    MAJOR_SCALE,
    MAX_TIE_BEATS,
    NOTE_LEGATO,
    InstrumentConfig,
)
from market_band.harmony import Chord, bar_chords
from market_band.ir import IRBeat, IRSeries
from market_band.notes import Note, intensity_to_velocity

BUSY_ACTIVITY = 0.5  # at or above: two eighth notes per beat
CALM_ACTIVITY = 0.25  # below: a repeated pitch is held instead of re-struck


def chord_cycle(chord: Chord, instrument: InstrumentConfig) -> tuple[int, int, int]:
    """Root, fifth and octave of the chord, with the root in the instrument's lowest octave."""
    root = instrument.root_midi + (chord.pitch_classes[0] - instrument.root_midi) % 12
    if root + 12 > instrument.root_midi + 12 * instrument.octaves:
        raise ValueError(f"{instrument.id}: range too small for a root and its octave")
    return root, root + 7, root + 12


def next_up(cycle: tuple[int, int, int], pitch: int) -> int:
    """Return the next chord note up the cycle root -> fifth -> octave -> root."""
    assert len(cycle) == 3, "cycle is root, fifth, octave"
    if pitch in cycle:
        return cycle[(cycle.index(pitch) + 1) % len(cycle)]
    return cycle[0] if cycle[0] != pitch else cycle[1]


def approach_note(next_root: int, instrument: InstrumentConfig) -> int:
    """Return the scale note one step below the next root (above it at the bottom of range)."""
    low = instrument.root_midi
    below = next(n for n in range(next_root - 1, next_root - 3, -1) if n % 12 in MAJOR_SCALE)
    if below >= low:
        return below
    return next(n for n in range(next_root + 1, next_root + 3) if n % 12 in MAJOR_SCALE)


def swing_pitch(cycle: tuple[int, int, int], beat: IRBeat, beat_in_bar: int) -> int:
    """Root on beat 1; elsewhere swing picks root, fifth or octave."""
    if beat_in_bar == 0:
        return cycle[0]
    return cycle[min(int(beat.swing * 3), 2)]


def beat_line(
    ir: IRSeries, chords: tuple[Chord, ...], instrument: InstrumentConfig, index: int
) -> list[tuple[float, int]]:
    """List the (length in beats, pitch) notes one beat plays, before ties and the repeat cap."""
    bar, beat_in_bar = divmod(index, BEATS_PER_BAR)
    cycle = chord_cycle(chords[bar], instrument)
    beat = ir.beats[index]
    pitch = swing_pitch(cycle, beat, beat_in_bar)
    next_chord = chords[(bar + 1) % len(chords)]
    if beat_in_bar == BEATS_PER_BAR - 1 and next_chord != chords[bar]:
        step = approach_note(chord_cycle(next_chord, instrument)[0], instrument)
        return [(0.5, pitch), (0.5, step)] if beat.activity >= BUSY_ACTIVITY else [(1.0, step)]
    if beat.activity >= BUSY_ACTIVITY:
        return [(0.5, pitch), (0.5, next_up(cycle, pitch))]
    return [(1.0, pitch)]


def render_bass(ir: IRSeries, instrument: InstrumentConfig) -> list[Note]:
    """Render the bass part for every beat of the IR."""
    assert len(ir.beats) == len(ir.bars) * BEATS_PER_BAR, "bars and beats disagree"
    assert BASS_MAX_REPEATS >= 1, "repeat cap must allow at least one note"
    chords = bar_chords(ir)
    held: list[list[float]] = []  # [start, nominal length, midi, velocity]
    run = 0
    for index, beat in enumerate(ir.beats):
        velocity = intensity_to_velocity(beat.intensity)
        cycle = chord_cycle(chords[index // BEATS_PER_BAR], instrument)
        start = float(index)
        for length, wanted in beat_line(ir, chords, instrument, index):
            last = held[-1] if held else None
            if (
                last is not None
                and length == 1.0
                and beat.activity < CALM_ACTIVITY
                and last[2] == wanted
                and last[1] < MAX_TIE_BEATS
                and abs(last[0] + last[1] - start) < 1e-9
            ):
                last[1] += 1.0
                start += length
                continue
            pitch = wanted
            run = run + 1 if last is not None and last[2] == pitch else 1
            if run > BASS_MAX_REPEATS:
                pitch, run = next_up(cycle, pitch), 1
            held.append([start, length, pitch, velocity])
            start += length
    return [
        Note(start_beat=s, duration_beats=length * NOTE_LEGATO, midi=int(m), velocity=int(v))
        for s, length, m, v in held
    ]
