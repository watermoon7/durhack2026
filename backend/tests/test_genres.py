import hashlib

import pytest
from fastapi.testclient import TestClient
from helpers import ir_with_activity

from market_band.algorithm import render_midi, render_notes
from market_band.api import app, build_ir
from market_band.chords import power_voicing
from market_band.config import (
    BEATS_PER_BAR,
    DRUM_ACCENT_NOTES,
    INSTRUMENTS,
    DatasetConfig,
    InstrumentConfig,
)
from market_band.harmony import bar_chords, chord_for_mood

# Fingerprint of every part in the default genre (Rock), re-pinned when Default was removed.
DEFAULT_FINGERPRINT = "3aff321ac02a51726cce59476a66c688a4ce143f61b59ba8c8c7cc8e9de7fbb6"
PINNED_DATASETS = ("spy", "aapl", "tsla", "gld", "tlt")
PINNED_INSTRUMENTS = ("kick", "snare", "hihat", "synth", "bass", "pad", "guitar")
GUITAR = next(i for i in INSTRUMENTS if i.id == "guitar")
DEMO = [DatasetConfig(id=d, ticker=d.upper(), name=d) for d in PINNED_DATASETS]


def by_id(instrument_id: str) -> InstrumentConfig:
    return next(i for i in INSTRUMENTS if i.id == instrument_id)


def test_default_midi_is_byte_identical() -> None:
    digest = hashlib.sha256()
    for dataset in PINNED_DATASETS:
        for instrument_id in PINNED_INSTRUMENTS:
            digest.update(render_midi(build_ir(dataset), by_id(instrument_id)))
    assert digest.hexdigest() == DEFAULT_FINGERPRINT


def test_render_midi_without_genre_plays_rock() -> None:
    ir = build_ir("spy")
    for instrument in INSTRUMENTS:
        assert render_midi(ir, instrument) == render_midi(ir, instrument, "rock")


def test_power_voicing_values() -> None:
    assert power_voicing(chord_for_mood(0.0)) == (43, 50, 55)  # G5
    assert power_voicing(chord_for_mood(0.25)) == (48, 55, 60)  # C5


@pytest.mark.parametrize("dataset", DEMO, ids=lambda d: d.id)
def test_rock_guitar_plays_power_chords(dataset: DatasetConfig) -> None:
    ir = build_ir(dataset.id)
    chords = bar_chords(ir)
    for note in render_notes(ir, GUITAR, "rock"):
        voicing = power_voicing(chords[int(note.start_beat // BEATS_PER_BAR)])
        if note.midi not in voicing:  # only a hammer-on's short source note may differ
            assert note.duration_beats <= 0.125, f"{note} is outside the power chord"


def test_unknown_genre_raises() -> None:
    with pytest.raises(ValueError, match="genre"):
        render_notes(build_ir("spy"), GUITAR, "polka")


def test_api_lists_genres() -> None:
    response = TestClient(app).get("/api/genres")
    assert response.status_code == 200
    assert response.json() == [{"id": "rock", "name": "Rock"}]


def test_api_unknown_genre_404() -> None:
    params = {"dataset_id": "spy", "instrument_id": "guitar", "genre": "polka"}
    assert TestClient(app).get("/api/midi", params=params).status_code == 404


# --- Rock drum accents --------------------------------------------------------------------

ACCENTS = set(DRUM_ACCENT_NOTES.values())
TOMS = [DRUM_ACCENT_NOTES[k] for k in ("tom_hh", "tom_h", "tom_m", "tom_l")]
CRASH = DRUM_ACCENT_NOTES["crash"]


def test_accent_notes_are_outside_every_drum_tuning_range() -> None:
    for part in (i for i in INSTRUMENTS if i.role == "drum"):
        tuning = set(range(part.root_midi, part.root_midi + 12 * part.octaves + 1))
        assert not set(TOMS) & tuning, f"a tom note collides with {part.id}'s tuning"
    assert CRASH not in range(by_id("hihat").root_midi, by_id("hihat").root_midi + 13)


def test_rock_snare_fills_on_busy_fourth_beats() -> None:
    notes = render_notes(ir_with_activity([0.1, 0.1, 0.1, 0.9] * 2), by_id("snare"), "rock")
    for beat in (3, 7):
        in_beat = sorted(
            (n for n in notes if beat <= n.start_beat < beat + 1), key=lambda n: n.start_beat
        )
        assert [n.start_beat for n in in_beat] == [beat, beat + 0.25, beat + 0.5, beat + 0.75]
        assert [n.midi for n in in_beat] == TOMS


def test_rock_crash_follows_busy_bars() -> None:
    notes = render_notes(ir_with_activity([0.9] * 4 + [0.1] * 4), by_id("hihat"), "rock")
    crashes = [n.start_beat for n in notes if n.midi == CRASH]
    # Bar 1 follows a busy bar. Bar 0 follows bar 1 (the loop), which is calm.
    assert crashes == [4.0]


@pytest.mark.parametrize("dataset", DEMO, ids=lambda d: d.id)
def test_rock_drums_accents_only_on_their_pieces(dataset: DatasetConfig) -> None:
    ir = build_ir(dataset.id)
    assert not {n.midi for n in render_notes(ir, by_id("kick"), "rock")} & ACCENTS
    assert {n.midi for n in render_notes(ir, by_id("snare"), "rock")} & ACCENTS <= set(TOMS)
    assert {n.midi for n in render_notes(ir, by_id("hihat"), "rock")} & ACCENTS <= {CRASH}
