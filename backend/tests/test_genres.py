import hashlib

import pytest
from fastapi.testclient import TestClient

from market_band.algorithm import render_midi, render_notes
from market_band.api import app, build_ir
from market_band.chords import power_voicing
from market_band.config import BEATS_PER_BAR, INSTRUMENTS, DatasetConfig, InstrumentConfig
from market_band.harmony import bar_chords, chord_for_mood

# Fingerprint of every Default part before genres existed (see the genres plan).
DEFAULT_FINGERPRINT = "19470c3bda251b638db778904a2784692af011f290afb72e6686172012a1b82e"
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


def test_render_midi_genre_default_matches_no_genre() -> None:
    ir = build_ir("spy")
    for instrument in INSTRUMENTS:
        assert render_midi(ir, instrument) == render_midi(ir, instrument, "default")


def test_power_voicing_values() -> None:
    assert power_voicing(chord_for_mood(0.0)) == (40, 47, 52)  # E5
    assert power_voicing(chord_for_mood(0.75)) == (48, 55, 60)  # C5


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
    assert response.json() == [{"id": "default", "name": "Default"}, {"id": "rock", "name": "Rock"}]


def test_api_unknown_genre_404() -> None:
    params = {"dataset_id": "spy", "instrument_id": "guitar", "genre": "polka"}
    assert TestClient(app).get("/api/midi", params=params).status_code == 404


def test_api_rock_guitar_differs_from_default() -> None:
    client = TestClient(app)

    def midi(instrument_id: str, genre: str) -> bytes:
        params = {"dataset_id": "spy", "instrument_id": instrument_id, "genre": genre}
        response = client.get("/api/midi", params=params)
        assert response.status_code == 200
        return bytes(response.content)

    assert midi("guitar", "rock") != midi("guitar", "default")
    assert midi("synth", "rock") == midi("synth", "default")
