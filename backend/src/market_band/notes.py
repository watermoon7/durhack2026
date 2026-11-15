"""Notes in beat time, shared by every part renderer."""

from dataclasses import dataclass

from market_band.config import MIDI_VELOCITY_MAX, VELOCITY_FLOOR


@dataclass(frozen=True)
class Note:
    """A single note in beat time."""

    start_beat: float
    duration_beats: float
    midi: int
    velocity: int


def intensity_to_velocity(intensity: float) -> int:
    """Map IR intensity in [0, 1] to a MIDI velocity, never quieter than VELOCITY_FLOOR."""
    if not 0.0 <= intensity <= 1.0:
        raise ValueError(f"intensity {intensity} outside [0, 1]")
    velocity = round(MIDI_VELOCITY_MAX * (VELOCITY_FLOOR + (1.0 - VELOCITY_FLOOR) * intensity))
    assert 1 <= velocity <= MIDI_VELOCITY_MAX, "velocity must be a sounding MIDI velocity"
    return velocity


def trim_overlaps(notes: list[Note]) -> list[Note]:
    """Shorten any note still sounding when the same pitch starts again, so it ends there.

    Without this, the earlier note's note-off would cut the later note short in MIDI.
    Returns the notes sorted by start.
    """
    assert all(n.duration_beats > 0 for n in notes), "notes must have positive duration"
    ordered = sorted(notes, key=lambda n: (n.start_beat, n.midi))
    next_start: dict[int, float] = {}
    trimmed: list[Note] = []
    for note in reversed(ordered):
        following = next_start.get(note.midi)
        end = note.start_beat + note.duration_beats
        if following is not None and end > following:
            if following <= note.start_beat:
                raise ValueError(f"two notes on pitch {note.midi} start at beat {note.start_beat}")
            note = Note(note.start_beat, following - note.start_beat, note.midi, note.velocity)
        next_start[note.midi] = note.start_beat
        trimmed.append(note)
    trimmed.reverse()
    return trimmed
