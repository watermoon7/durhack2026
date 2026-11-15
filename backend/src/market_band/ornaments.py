"""Ornaments: short decorations on the lead and guitar, placed on the stock's busiest beats.

Where an ornament goes comes from the data (activity at or above ORNAMENT_TRIGGER, spaced at
least ORNAMENT_MIN_GAP_BEATS apart). Which kind plays is chosen by a generator seeded from the
stock and instrument with CRC32 (not Python's per-process ``hash()``), so the same data always
gives the same song.
"""

import random
import zlib

from market_band.config import (
    NOTE_LEGATO,
    ORNAMENT_MIN_GAP_BEATS,
    ORNAMENT_TRIGGER,
    SCALE_INTERVALS,
)
from market_band.harmony import step_toward
from market_band.ir import IRSeries
from market_band.notes import Note

LEAD_KINDS = ("grace", "mordent", "trill", "run")
GUITAR_KINDS = ("roll", "hammer")


def stable_rng(source: str, instrument_id: str) -> random.Random:
    """Return a generator seeded from the stock and instrument, identical in every process."""
    if not source or not instrument_id:
        raise ValueError("source and instrument_id are required")
    return random.Random(zlib.crc32(f"{source}:{instrument_id}".encode()))


def ornament_beats(ir: IRSeries) -> tuple[int, ...]:
    """List the beats that carry an ornament: busy beats, at least the minimum gap apart."""
    assert ORNAMENT_MIN_GAP_BEATS >= 1, "ornaments need a positive gap"
    assert 0.0 < ORNAMENT_TRIGGER <= 1.0, "trigger must be in (0, 1]"
    chosen: list[int] = []
    for index, beat in enumerate(ir.beats):
        spaced = not chosen or index - chosen[-1] >= ORNAMENT_MIN_GAP_BEATS
        if beat.activity >= ORNAMENT_TRIGGER and spaced:
            chosen.append(index)
    return tuple(chosen)


def neighbour(pool: tuple[int, ...], pitch: int, upward: bool) -> int:
    """Return the pool note next to ``pitch`` in one direction, or the other way at the edge."""
    above = [n for n in pool if n > pitch]
    below = [n for n in pool if n < pitch]
    if upward:
        return above[0] if above else below[-1]
    return below[-1] if below else above[0]


def sequence(beat: int, steps: list[tuple[float, int]], velocity: int) -> list[Note]:
    """Lay (length in beats, pitch) steps end to end from the start of ``beat``."""
    assert abs(sum(length for length, _ in steps) - 1.0) < 1e-9, "an ornament fills one beat"
    notes: list[Note] = []
    start = float(beat)
    for length, pitch in steps:
        notes.append(Note(start, length * NOTE_LEGATO, pitch, velocity))
        start += length
    return notes


def lead_ornament(
    rng: random.Random, beat: int, pitch: int, next_pitch: int, pool: tuple[int, ...], velocity: int
) -> list[Note]:
    """Decorate one lead beat with a grace note, mordent, trill or run, all from ``pool``."""
    if pitch not in pool:
        raise ValueError(f"pitch {pitch} is not in the pool")
    if len(pool) < 2:
        raise ValueError("an ornament needs at least two pool notes")
    kind = rng.choice(LEAD_KINDS)
    upper = neighbour(pool, pitch, upward=True)
    if kind == "grace":
        steps = [(0.125, neighbour(pool, pitch, upward=False)), (0.875, pitch)]
    elif kind == "mordent":
        steps = [(0.125, pitch), (0.125, upper), (0.75, pitch)]
    elif kind == "trill":
        steps = [(0.125, pitch if i % 2 == 0 else upper) for i in range(8)]
    else:
        steps, current = [], pitch
        for _ in range(4):
            steps.append((0.25, current))
            current = step_toward(pool, current, next_pitch)
    return sequence(beat, steps, velocity)


def guitar_ornament(
    rng: random.Random, beat: int, voicing: tuple[int, ...], velocity: int
) -> list[Note]:
    """Decorate one guitar beat with a rolled chord or a hammer-on into the top note."""
    if len(voicing) < 2:
        raise ValueError("a guitar voicing needs at least two notes")
    assert 1 <= velocity <= 127, "velocity must be a MIDI velocity"
    start, end = float(beat), float(beat + 1)
    if rng.choice(GUITAR_KINDS) == "roll":
        gap = 1.0 / len(voicing)
        return [
            Note(start + i * gap, end - (start + i * gap), pitch, velocity)
            for i, pitch in enumerate(voicing)
        ]
    top = voicing[-1]
    allowed = {p % 12 for p in voicing} | set(SCALE_INTERVALS)  # the bar's note pool
    from_note = next(n for n in range(top - 1, top - 12, -1) if n % 12 in allowed)
    body = [Note(start, NOTE_LEGATO, pitch, velocity) for pitch in voicing[:-1]]
    hammer = [
        Note(start, 0.125, from_note, velocity),
        Note(start + 0.125, (1.0 - 0.125) * NOTE_LEGATO, top, velocity),
    ]
    return body + hammer
