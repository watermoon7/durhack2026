"""The two chord parts: the second synth (pad) and the strummed acoustic guitar.

Both play their stock's chord for each bar; activity sets how often it is struck and intensity
how hard.
"""

from market_band.config import (
    BEATS_PER_BAR,
    DEFAULT_GENRE,
    GUITAR_LOW_MIDI,
    NOTE_LEGATO,
    PAD_LOW_MIDI,
    STRUM_GAP_BEATS,
    UPSTROKE_VELOCITY_SCALE,
    InstrumentConfig,
)
from market_band.harmony import Chord, bar_chords
from market_band.ir import IRSeries
from market_band.notes import Note, intensity_to_velocity, trim_overlaps
from market_band.ornaments import guitar_ornament, ornament_beats, stable_rng

UPSTROKE_STRINGS = 4  # an upstroke catches only the top strings


def root_from(low: int, chord: Chord) -> int:
    """Return the chord root's lowest MIDI note at or above ``low``."""
    assert 0 <= low <= 127, "low must be a MIDI note"
    return low + (chord.pitch_classes[0] - low) % 12


def pad_voicing(chord: Chord) -> tuple[int, ...]:
    """Voice the chord as root, octave, fifth above that, root again, then the third on top."""
    r = root_from(PAD_LOW_MIDI, chord)
    third = 3 if chord.minor else 4
    return r, r + 12, r + 19, r + 24, r + 24 + third


def guitar_voicing(chord: Chord) -> tuple[int, ...]:
    """Voice the chord as a six-string open shape: root, fifth, root, third, fifth, root."""
    r = root_from(GUITAR_LOW_MIDI, chord)
    third = 3 if chord.minor else 4
    return r, r + 7, r + 12, r + 12 + third, r + 19, r + 24


def power_voicing(chord: Chord) -> tuple[int, int, int]:
    """Voice the chord as a rock power chord: root, fifth and octave from the low strings."""
    r = root_from(GUITAR_LOW_MIDI, chord)
    return r, r + 7, r + 12


def strikes_per_bar(mean_activity: float) -> int:
    """Count the strikes in a bar: calm bars hold one chord, busy bars strike every beat."""
    assert 0.0 <= mean_activity <= 1.0, "activity must be in [0, 1]"
    if mean_activity < 1 / 3:
        return 1
    return 2 if mean_activity < 2 / 3 else 4


def render_pad(ir: IRSeries, instrument: InstrumentConfig) -> list[Note]:
    """Render the second synth: the big voicing once, twice or four times a bar."""
    assert len(ir.beats) == len(ir.bars) * BEATS_PER_BAR, "bars and beats disagree"
    assert instrument.role == "pad", f"{instrument.id} is not a pad"
    notes: list[Note] = []
    for bar, chord in enumerate(bar_chords(ir)):
        beats = ir.beats[bar * BEATS_PER_BAR : (bar + 1) * BEATS_PER_BAR]
        strikes = strikes_per_bar(sum(b.activity for b in beats) / len(beats))
        length = BEATS_PER_BAR // strikes
        for strike in range(strikes):
            covered = beats[strike * length : (strike + 1) * length]
            velocity = intensity_to_velocity(sum(b.intensity for b in covered) / len(covered))
            start = float(bar * BEATS_PER_BAR + strike * length)
            notes.extend(
                Note(start, length * NOTE_LEGATO, pitch, velocity) for pitch in pad_voicing(chord)
            )
    return notes


def strum(start: float, ring: float, pitches: tuple[int, ...], velocity: int) -> list[Note]:
    """Strum ``pitches`` in the order given, STRUM_GAP_BEATS apart, each ringing ``ring``."""
    assert ring > STRUM_GAP_BEATS * len(pitches), "ring must outlast the strum"
    assert 1 <= velocity <= 127, "velocity must be a MIDI velocity"
    return [
        Note(start + i * STRUM_GAP_BEATS, ring * NOTE_LEGATO, pitch, velocity)
        for i, pitch in enumerate(pitches)
    ]


def render_guitar(
    ir: IRSeries, instrument: InstrumentConfig, genre: str = DEFAULT_GENRE
) -> list[Note]:
    """Render the guitar: calm beats strum on 1 and 3, busier ones every beat, busiest down-up.

    Rock plays power chords in place of the six-string open shapes.
    """
    assert len(ir.beats) == len(ir.bars) * BEATS_PER_BAR, "bars and beats disagree"
    assert instrument.role == "guitar", f"{instrument.id} is not a guitar"
    chords = bar_chords(ir)
    ornaments = set(ornament_beats(ir))
    rng = stable_rng(ir.source, instrument.id)
    notes: list[Note] = []
    for index, beat in enumerate(ir.beats):
        chord = chords[index // BEATS_PER_BAR]
        voicing = power_voicing(chord) if genre == "rock" else guitar_voicing(chord)
        velocity = intensity_to_velocity(beat.intensity)
        if index in ornaments:  # the stock's busiest beats get a roll or hammer-on instead
            notes.extend(guitar_ornament(rng, index, voicing, velocity))
            continue
        if beat.activity < 1 / 3:
            if index % 2 == 0:  # bar beats 1 and 3
                notes.extend(strum(float(index), 2.0, voicing, velocity))
            continue
        notes.extend(strum(float(index), 1.0, voicing, velocity))
        if beat.activity >= 2 / 3:
            up = tuple(reversed(voicing[-UPSTROKE_STRINGS:]))
            soft = max(1, round(velocity * UPSTROKE_VELOCITY_SCALE))
            notes.extend(strum(index + 0.5, 0.5, up, soft))
    end = float(len(ir.beats))  # strummed strings start late, so the last strum must stop here
    clipped = [
        Note(n.start_beat, min(n.duration_beats, end - n.start_beat), n.midi, n.velocity)
        for n in notes
    ]
    return trim_overlaps(clipped)
