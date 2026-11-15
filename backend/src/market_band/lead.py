"""The lead melody.

The smoothed price sets the register (so a crash still descends), swing adds the jumps, the
bar's chord decides which notes are allowed, and activity sets note lengths.
"""

import numpy as np

from market_band.config import (
    BEATS_PER_BAR,
    LEAD_PATTERNS,
    LEVEL_SMOOTH_BEATS,
    MAX_TIE_BEATS,
    MELODY_SWING_WEIGHT,
    NOTE_LEGATO,
    InstrumentConfig,
)
from market_band.harmony import bar_chords, nearest_note, pool_notes, step_toward
from market_band.ir import IRSeries
from market_band.notes import Note, intensity_to_velocity
from market_band.ornaments import lead_ornament, ornament_beats, stable_rng

STRONG_BEATS = (0, 2)  # beats 1 and 3 of a bar use chord tones only


def instrument_range(instrument: InstrumentConfig) -> tuple[int, int]:
    """Lowest and highest MIDI note the instrument may play."""
    if instrument.octaves < 1:
        raise ValueError(f"{instrument.id}: octaves must be >= 1")
    return instrument.root_midi, instrument.root_midi + 12 * instrument.octaves


def beat_pools(
    ir: IRSeries, instrument: InstrumentConfig, strong_only: bool
) -> list[tuple[int, ...]]:
    """List the note pool for every beat: chord tones on strong beats, plus pentatonic elsewhere."""
    low, high = instrument_range(instrument)
    chords = bar_chords(ir)
    assert len(chords) * BEATS_PER_BAR == len(ir.beats), "bars and beats disagree"
    return [
        pool_notes(
            chords[i // BEATS_PER_BAR],
            low,
            high,
            strong=strong_only or (i % BEATS_PER_BAR) in STRONG_BEATS,
        )
        for i in range(len(ir.beats))
    ]


def lead_pitches(ir: IRSeries, instrument: InstrumentConfig) -> list[int]:
    """Pick the main pitch of every beat."""
    low, high = instrument_range(instrument)
    level = np.array([b.level for b in ir.beats])
    swing = np.array([b.swing for b in ir.beats])
    window = np.ones(LEVEL_SMOOTH_BEATS)
    smooth = np.convolve(level, window, "same") / np.convolve(np.ones_like(level), window, "same")
    position = np.clip(smooth + (swing - 0.5) * MELODY_SWING_WEIGHT, 0.0, 1.0)
    targets = low + position * (high - low)
    pools = beat_pools(ir, instrument, strong_only=False)
    return [nearest_note(pool, float(t)) for pool, t in zip(pools, targets, strict=True)]


def pattern_for(activity: float) -> tuple[float, ...]:
    """Pick the note lengths within a beat for a given activity."""
    assert 0.0 <= activity <= 1.0, "activity must be in [0, 1]"
    return LEAD_PATTERNS[min(int(activity * len(LEAD_PATTERNS)), len(LEAD_PATTERNS) - 1)]


def render_lead(ir: IRSeries, instrument: InstrumentConfig) -> list[Note]:
    """Render the lead part, one pattern per beat.

    Calm repeated notes are held instead, and the stock's busiest beats become an ornament.
    """
    pitches = lead_pitches(ir, instrument)
    pools = beat_pools(ir, instrument, strong_only=False)
    ornaments = set(ornament_beats(ir))
    rng = stable_rng(ir.source, instrument.id)
    held: list[list[float]] = []  # [start, nominal length, midi, velocity, legato]
    for index, beat in enumerate(ir.beats):
        pitch = pitches[index]
        velocity = intensity_to_velocity(beat.intensity)
        next_pitch = pitches[(index + 1) % len(pitches)]
        if index in ornaments:  # ornament notes already carry their sounding length
            decoration = lead_ornament(rng, index, pitch, next_pitch, pools[index], velocity)
            held.extend(
                [n.start_beat, n.duration_beats, n.midi, n.velocity, 1.0] for n in decoration
            )
            continue
        pattern = pattern_for(beat.activity)
        last = held[-1] if held else None
        tie = (
            last is not None
            and pattern == (1.0,)
            and last[2] == pitch
            and last[1] < MAX_TIE_BEATS
            and abs(last[0] + last[1] - index) < 1e-9
        )
        if tie and last is not None:
            last[1] += 1.0
            continue
        current, start = pitch, float(index)
        for fraction in pattern:
            held.append([start, fraction, current, velocity, NOTE_LEGATO])
            start += fraction
            current = step_toward(pools[index], current, next_pitch)
    return [
        Note(start_beat=s, duration_beats=length * legato, midi=int(m), velocity=int(v))
        for s, length, m, v, legato in held
    ]
