import io
import random
import zlib
from collections import defaultdict
from itertools import groupby, pairwise

import mido
import pytest
from helpers import ir_with_activity, make_frame

from market_band.algorithm import render_midi, render_notes
from market_band.api import build_ir
from market_band.chords import guitar_voicing, pad_voicing, render_guitar
from market_band.config import (
    BASS_MAX_REPEATS,
    DATASETS,
    DEFAULT_GENRE,
    DRUM_ACCENT_NOTES,
    GENRES,
    INSTRUMENTS,
    KEY_SCALE,
    SCALE_INTERVALS,
    SONG_BEATS,
    STRUM_GAP_BEATS,
    TICKS_PER_BEAT,
    DatasetConfig,
    InstrumentConfig,
)
from market_band.harmony import Chord, bar_chords, chord_for_mood, pool_notes
from market_band.ir import stock_to_ir
from market_band.notes import Note, trim_overlaps
from market_band.ornaments import (
    guitar_ornament,
    lead_ornament,
    ornament_beats,
    stable_rng,
)


def instrument(instrument_id: str) -> InstrumentConfig:
    return next(i for i in INSTRUMENTS if i.id == instrument_id)


def in_key_and_range(notes: list[Note], part: InstrumentConfig, genre: str = DEFAULT_GENRE) -> bool:
    """Every note is in C minor and in range; Rock drum accents (GM drum notes) are exempt."""
    top = part.root_midi + 12 * part.octaves
    accents = genre == "rock" and part.role == "drum"
    exempt = set(DRUM_ACCENT_NOTES.values()) if accents else set()
    return all(
        n.midi in exempt or (n.midi % 12 in KEY_SCALE and part.root_midi <= n.midi <= top)
        for n in notes
    )


LEAD = instrument("synth")
BASS = instrument("bass")
PAD = instrument("pad")
GUITAR = instrument("guitar")

# --- Time grid and IR ---------------------------------------------------------------------


@pytest.mark.parametrize("dataset", DATASETS, ids=lambda d: d.id)
def test_demo_ir_is_64_beats_16_bars(dataset: DatasetConfig) -> None:
    ir = build_ir(dataset.id)
    assert len(ir.beats) == 64 and len(ir.bars) == 16
    assert all(
        0.0 <= v <= 1.0 for b in ir.beats for v in (b.level, b.swing, b.activity, b.intensity)
    )


def test_mood_follows_bar_return() -> None:
    ir = stock_to_ir("T", make_frame([100, 100, 100, 100, 100, 90, 80, 70], [1] * 8), beats=8)
    assert [b.mood for b in ir.bars] == [0.5, 0.0]


def test_activity_and_intensity_use_fixed_scales() -> None:
    ir = stock_to_ir("T", make_frame([100, 100, 100, 100], [10, 10, 10, 40]), beats=4)
    assert ir.beats[0].activity == pytest.approx((0.02 / 0.09) ** 0.5)  # make_frame range is 2%
    assert [b.intensity for b in ir.beats] == pytest.approx([1 / 3, 1 / 3, 1 / 3, 1.0])


def test_flat_stock_is_neutral_not_nan() -> None:
    ir = stock_to_ir("T", make_frame([50.0] * 10, [0.0] * 10))
    assert len(ir.beats) == 64
    assert all(b.level == b.swing == b.intensity == 0.5 for b in ir.beats)
    assert all(b.mood == 0.5 for b in ir.bars)


def test_too_long_dataset_is_rejected() -> None:
    with pytest.raises(ValueError, match="rows"):
        stock_to_ir("T", make_frame([100.0] * 9, [1.0] * 9), beats=4)


def test_beats_must_fill_whole_bars() -> None:
    with pytest.raises(ValueError, match="bar"):
        stock_to_ir("T", make_frame([100.0] * 6, [1.0] * 6), beats=6)


@pytest.mark.parametrize("instrument", INSTRUMENTS, ids=lambda i: i.id)
def test_midi_is_exactly_song_length(instrument: InstrumentConfig) -> None:
    payload = render_midi(build_ir("spy"), instrument)
    track = mido.MidiFile(file=io.BytesIO(payload)).tracks[0]
    assert sum(m.time for m in track) == SONG_BEATS * TICKS_PER_BEAT


# --- Harmony and lead ---------------------------------------------------------------------


def test_mood_picks_chords_on_the_bright_to_dark_line() -> None:
    assert chord_for_mood(1.0) == Chord(5, (8, 0, 3), False)  # VI (Ab)
    assert chord_for_mood(0.51) == Chord(6, (10, 2, 5), False)  # VII (Bb)
    assert chord_for_mood(0.5) == Chord(3, (5, 8, 0), True)  # iv (Fm)
    assert chord_for_mood(0.0) == Chord(4, (7, 10, 2), True)  # v (Gm)


def test_pool_is_chord_on_strong_beats_and_adds_pentatonic_on_weak() -> None:
    one = chord_for_mood(0.25)  # i (Cm)
    assert pool_notes(one, 60, 72, strong=True) == (60, 63, 67, 72)
    assert pool_notes(one, 60, 72, strong=False) == (60, 63, 65, 67, 70, 72)


@pytest.mark.parametrize("dataset", DATASETS, ids=lambda d: d.id)
def test_lead_moves_like_a_melody(dataset: DatasetConfig) -> None:
    notes = render_notes(build_ir(dataset.id), LEAD)
    moves = [abs(b.midi - a.midi) for a, b in pairwise(notes)]
    repeats = sum(m == 0 for m in moves) / len(moves)
    jumps = sum(m >= 4 for m in moves) / len(moves)  # 4+ semitones = two pool steps
    assert repeats <= 0.30, f"{repeats:.0%} repeated notes"
    assert 0.20 <= jumps <= 0.50, f"{jumps:.0%} jumps"
    assert len({round(n.duration_beats, 3) for n in notes}) >= 3


@pytest.mark.parametrize("dataset", DATASETS, ids=lambda d: d.id)
def test_lead_stays_in_key_range_and_song(dataset: DatasetConfig) -> None:
    notes = render_notes(build_ir(dataset.id), LEAD)
    assert in_key_and_range(notes, LEAD)
    assert max(n.start_beat + n.duration_beats for n in notes) <= SONG_BEATS


@pytest.mark.parametrize("part", INSTRUMENTS, ids=lambda i: i.id)
def test_render_is_deterministic(part: InstrumentConfig) -> None:
    ir = build_ir("spy")
    assert render_midi(ir, part) == render_midi(ir, part)


# --- Bass ---------------------------------------------------------------------------------


@pytest.mark.parametrize("dataset", DATASETS, ids=lambda d: d.id)
def test_bass_never_repeats_a_pitch_more_than_three_times(dataset: DatasetConfig) -> None:
    notes = render_notes(build_ir(dataset.id), BASS)
    run = longest = 1
    for a, b in pairwise(notes):
        run = run + 1 if a.midi == b.midi else 1
        longest = max(longest, run)
    assert longest <= BASS_MAX_REPEATS


@pytest.mark.parametrize("dataset", DATASETS, ids=lambda d: d.id)
def test_bass_opens_each_bar_on_its_chord(dataset: DatasetConfig) -> None:
    ir = build_ir(dataset.id)
    notes = render_notes(ir, BASS)
    for bar, chord in enumerate(bar_chords(ir)):
        at_bar = max((n for n in notes if n.start_beat <= bar * 4), key=lambda n: n.start_beat)
        assert at_bar.midi % 12 in chord.pitch_classes  # a tied note may carry over the bar line


@pytest.mark.parametrize("dataset", DATASETS, ids=lambda d: d.id)
def test_bass_stays_in_key_and_range(dataset: DatasetConfig) -> None:
    notes = render_notes(build_ir(dataset.id), BASS)
    assert in_key_and_range(notes, BASS)
    assert max(n.start_beat + n.duration_beats for n in notes) <= SONG_BEATS


# --- Second synth (pad) and guitar --------------------------------------------------------


def test_pad_voicing_is_root_octave_fifth_root_third() -> None:
    assert pad_voicing(chord_for_mood(0.75)) == (39, 51, 58, 63, 67)  # Eb major: Eb2 Eb3 Bb3 Eb4 G4
    assert pad_voicing(chord_for_mood(0.25)) == (36, 48, 55, 60, 63)  # C minor: C2 C3 G3 C4 Eb4


@pytest.mark.parametrize("dataset", DATASETS, ids=lambda d: d.id)
def test_every_pad_chord_uses_the_voicing(dataset: DatasetConfig) -> None:
    notes = sorted(render_notes(build_ir(dataset.id), PAD), key=lambda n: n.start_beat)
    shapes = {(0, 12, 19, 24, 27), (0, 12, 19, 24, 28)}
    for _start, group in groupby(notes, key=lambda n: n.start_beat):
        pitches = sorted(n.midi for n in group)
        assert tuple(p - pitches[0] for p in pitches) in shapes


def test_guitar_voicing_matches_open_chords() -> None:
    assert guitar_voicing(chord_for_mood(0.0)) == (43, 50, 55, 58, 62, 67)  # G minor
    assert guitar_voicing(chord_for_mood(0.25)) == (48, 55, 60, 63, 67, 72)  # C minor


def test_strum_staggers_low_to_high() -> None:
    notes = render_guitar(ir_with_activity([0.1] * 8), GUITAR)
    first = sorted(notes, key=lambda n: n.start_beat)[:3]  # one Rock power-chord strum
    assert [n.midi for n in first] == sorted(n.midi for n in first)
    assert first[1].start_beat - first[0].start_beat == pytest.approx(STRUM_GAP_BEATS)


@pytest.mark.parametrize("genre", [g.id for g in GENRES])
@pytest.mark.parametrize("dataset", DATASETS, ids=lambda d: d.id)
@pytest.mark.parametrize("part", INSTRUMENTS, ids=lambda i: i.id)
def test_no_same_pitch_overlap_in_any_part(
    dataset: DatasetConfig, part: InstrumentConfig, genre: str
) -> None:
    by_pitch: dict[int, list[Note]] = defaultdict(list)
    for note in render_notes(build_ir(dataset.id), part, genre):
        by_pitch[note.midi].append(note)
    for notes in by_pitch.values():
        ordered = sorted(notes, key=lambda n: n.start_beat)
        for a, b in pairwise(ordered):
            assert a.start_beat + a.duration_beats <= b.start_beat + 1e-9


@pytest.mark.parametrize("genre", [g.id for g in GENRES])
@pytest.mark.parametrize("dataset", DATASETS, ids=lambda d: d.id)
@pytest.mark.parametrize("part", INSTRUMENTS, ids=lambda i: i.id)
def test_every_part_stays_in_key_and_range(
    dataset: DatasetConfig, part: InstrumentConfig, genre: str
) -> None:
    assert in_key_and_range(render_notes(build_ir(dataset.id), part, genre), part, genre)


def test_trim_overlaps_shortens_the_earlier_note() -> None:
    assert trim_overlaps([Note(0, 4, 60, 90), Note(2, 1, 60, 90)])[0].duration_beats == 2


# --- Ornaments ----------------------------------------------------------------------------


def test_ornaments_land_on_busy_beats_with_a_gap() -> None:
    assert ornament_beats(ir_with_activity([0.8] * 8)) == (0, 4)
    assert ornament_beats(ir_with_activity([0.7] * 8)) == ()


@pytest.mark.parametrize("seed", range(50))
def test_lead_ornament_stays_in_its_beat_and_pool(seed: int) -> None:
    pool = pool_notes(chord_for_mood(0.75), 60, 84, strong=False)
    notes = lead_ornament(random.Random(seed), 5, 63, 67, pool, 90)
    assert notes
    assert all(n.start_beat >= 5 and n.start_beat + n.duration_beats <= 6 for n in notes)
    assert all(n.midi in pool for n in notes)


@pytest.mark.parametrize("seed", range(50))
def test_guitar_ornament_stays_in_its_beat_and_chord(seed: int) -> None:
    voicing = guitar_voicing(chord_for_mood(0.75))
    allowed = {p % 12 for p in voicing} | set(SCALE_INTERVALS)  # the bar's note pool
    notes = guitar_ornament(random.Random(seed), 5, voicing, 90)
    assert notes
    assert all(n.start_beat >= 5 and n.start_beat + n.duration_beats <= 6 for n in notes)
    assert all(n.midi in voicing or n.midi % 12 in allowed for n in notes)
    assert voicing[-1] in {n.midi for n in notes}  # every ornament reaches the top note


def test_stable_rng_is_seeded_from_crc32_not_hash() -> None:
    assert stable_rng("SPY", "synth").random() == random.Random(zlib.crc32(b"SPY:synth")).random()


@pytest.mark.parametrize("part", INSTRUMENTS, ids=lambda i: i.id)
def test_flat_stock_renders_for_every_instrument(part: InstrumentConfig) -> None:
    flat_ir = stock_to_ir("T", make_frame([50.0] * 10, [0.0] * 10))
    assert render_midi(flat_ir, part)[:4] == b"MThd"


@pytest.mark.parametrize("dataset", DATASETS, ids=lambda d: d.id)
def test_busy_stocks_get_ornaments(dataset: DatasetConfig) -> None:
    ir = build_ir(dataset.id)
    if not ornament_beats(ir):
        pytest.skip(f"{dataset.id} has no beat busy enough for an ornament")
    plain = [n for n in render_notes(ir, LEAD) if n.duration_beats < 0.2]  # 1/8-beat notes
    assert plain, "ornament beats must add short notes to the lead"
