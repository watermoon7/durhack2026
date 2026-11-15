"""Harmony: each stock's bar mood picks one of six C-major chords.

The chord sets the notes the parts may use in that bar. The chords sit on a line from bright
to dark (IV, I, V, ii, vi, iii: stacked fifths), so a rising bar plays a bright major chord
and a falling bar a dark minor one. Two stocks that move
together land on the same or neighbouring chords; stocks that diverge land far apart and clash.
"""

from dataclasses import dataclass

from market_band.config import CHORD_LINE, MAJOR_SCALE, SCALE_INTERVALS
from market_band.ir import IRSeries


@dataclass(frozen=True)
class Chord:
    """A diatonic triad: its scale degree, pitch classes (root, third, fifth) and quality."""

    degree: int
    pitch_classes: tuple[int, int, int]
    minor: bool


def triad(degree: int) -> Chord:
    """Build the C-major triad on a scale degree (0 = C ... 6 = B)."""
    if not 0 <= degree < len(MAJOR_SCALE):
        raise ValueError(f"scale degree {degree} outside the scale")
    steps = len(MAJOR_SCALE)
    root, third, fifth = (MAJOR_SCALE[(degree + k) % steps] for k in (0, 2, 4))
    minor = (third - root) % 12 == 3
    return Chord(degree, (root, third, fifth), minor)


def chord_for_mood(mood: float) -> Chord:
    """Pick the chord for a bar: mood 1 -> brightest (IV), mood 0 -> darkest (iii)."""
    if not 0.0 <= mood <= 1.0:
        raise ValueError(f"mood {mood} outside [0, 1]")
    slots = len(CHORD_LINE)
    return triad(CHORD_LINE[min(int((1.0 - mood) * slots), slots - 1)])


def bar_chords(ir: IRSeries) -> tuple[Chord, ...]:
    """One chord per bar of the IR."""
    assert len(ir.bars) > 0, "IR must have bars"
    return tuple(chord_for_mood(bar.mood) for bar in ir.bars)


def pool_notes(chord: Chord, low: int, high: int, strong: bool) -> tuple[int, ...]:
    """List the MIDI notes in [low, high] a melody may use, ascending.

    Strong beats get chord tones only; other beats add C major pentatonic.
    """
    if low > high:
        raise ValueError(f"empty range {low}..{high}")
    allowed = set(chord.pitch_classes)
    if not strong:
        allowed |= set(SCALE_INTERVALS)
    notes = tuple(n for n in range(low, high + 1) if n % 12 in allowed)
    if not notes:
        raise ValueError(f"no chord notes in range {low}..{high}")
    return notes


def nearest_note(pool: tuple[int, ...], target: float) -> int:
    """Return the pool note closest to ``target``; ties resolve downward."""
    if not pool:
        raise ValueError("pool is empty")
    return min(pool, key=lambda note: (abs(note - target), note))


def step_toward(pool: tuple[int, ...], current: int, target: int) -> int:
    """Move one pool step from ``current`` toward ``target``.

    At the target it moves to the upper neighbour (the lower one at the top of the pool), so
    walking notes never repeat.
    """
    assert pool, "pool must not be empty"
    below = [n for n in pool if n < current]
    above = [n for n in pool if n > current]
    if target > current and above:
        return above[0]
    if target < current and below:
        return below[-1]
    if above:
        return above[0]
    return below[-1] if below else current
