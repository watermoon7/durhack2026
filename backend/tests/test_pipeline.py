import io

import mido
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from market_band.algorithm import (
    beat_to_notes,
    intensity_to_velocity,
    ir_to_notes,
    notes_to_midi,
    scale_notes,
)
from market_band.api import app
from market_band.config import (
    INSTRUMENTS,
    MELODIC_SUBDIVISIONS,
    MIDI_VELOCITY_MAX,
    TICKS_PER_BEAT,
    InstrumentConfig,
)
from market_band.ir import IRBeat, percentile_rank, stock_to_ir

KEYS = InstrumentConfig(
    id="keys", name="Keys", root_midi=48, octaves=2, subdivisions=MELODIC_SUBDIVISIONS
)
KICK = next(i for i in INSTRUMENTS if i.id == "kick")
SNARE = next(i for i in INSTRUMENTS if i.id == "snare")
WILD = IRBeat(date="d", level=1, activity=1, intensity=1)


def make_frame(closes: list[float], volumes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": [f"2020-01-{i + 1:02d}" for i in range(len(closes))],
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "adj_close": closes,
            "volume": volumes,
        }
    )


def test_ir_channels_are_normalised_and_level_follows_price() -> None:
    ir = stock_to_ir("TEST", make_frame([100, 120, 80, 100], [10, 40, 20, 30]))
    levels = [b.level for b in ir.beats]
    assert levels[2] == 0.0 and levels[1] == 1.0
    assert [b.intensity for b in ir.beats] == pytest.approx([0, 1, 1 / 3, 2 / 3])


def test_percentile_rank_flat_series_is_neutral() -> None:
    assert percentile_rank(pd.Series([5.0, 5.0, 5.0])).tolist() == [0.5, 0.5, 0.5]


def test_stock_to_ir_rejects_non_positive_prices() -> None:
    with pytest.raises(ValueError, match="positive"):
        stock_to_ir("BAD", make_frame([100, 0], [1, 2]))


def test_scale_spans_two_octaves_of_pentatonic() -> None:
    assert scale_notes(KEYS) == (48, 50, 52, 55, 57, 60, 62, 64, 67, 69, 72)


def test_beat_extremes_map_to_range_ends_and_subdivisions() -> None:
    scale = scale_notes(KEYS)
    calm_low = beat_to_notes(0, IRBeat(date="d", level=0, activity=0, intensity=0), scale, KEYS)
    wild_high = beat_to_notes(3, WILD, scale, KEYS)
    assert [n.midi for n in calm_low] == [48]
    assert len(wild_high) == MELODIC_SUBDIVISIONS[-1]
    assert {n.midi for n in wild_high} == {72}
    assert wild_high[0].start_beat == 3.0
    assert wild_high[0].velocity == MIDI_VELOCITY_MAX


def test_kick_never_exceeds_two_hits() -> None:
    assert len(beat_to_notes(0, WILD, scale_notes(KICK), KICK)) == 2


def test_snare_offset_shifts_start() -> None:
    notes = beat_to_notes(3, WILD, scale_notes(SNARE), SNARE)
    assert notes[0].start_beat == 3.5


def test_offset_notes_fit_in_beat() -> None:
    for instrument in INSTRUMENTS:
        for note in beat_to_notes(3, WILD, scale_notes(instrument), instrument):
            assert note.start_beat + note.duration_beats <= 4.0


def test_bad_offset_raises() -> None:
    bad = InstrumentConfig(
        id="x", name="X", root_midi=48, octaves=1, subdivisions=(1,), offset_beats=1.0
    )
    with pytest.raises(ValueError, match="offset"):
        beat_to_notes(0, WILD, scale_notes(bad), bad)


def test_intensity_out_of_range_raises() -> None:
    with pytest.raises(ValueError):
        intensity_to_velocity(1.5)


def test_midi_round_trip_preserves_notes() -> None:
    ir = stock_to_ir("TEST", make_frame([100, 120, 80, 100], [10, 40, 20, 30]))
    notes = ir_to_notes(ir, KEYS)
    parsed = mido.MidiFile(file=io.BytesIO(notes_to_midi(notes, "test")))
    assert parsed.ticks_per_beat == TICKS_PER_BEAT
    note_ons = [m for m in parsed.tracks[0] if m.type == "note_on"]
    assert [m.note for m in note_ons] == [n.midi for n in notes]


def test_api_serves_midi_for_every_instrument() -> None:
    client = TestClient(app)
    datasets = client.get("/api/datasets").json()
    assert len(datasets) > 0
    for instrument in INSTRUMENTS:
        response = client.get(
            "/api/midi", params={"dataset_id": datasets[0]["id"], "instrument_id": instrument.id}
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/midi"
        assert response.content[:4] == b"MThd"


def test_api_unknown_ids_404() -> None:
    client = TestClient(app)
    assert client.get("/api/datasets/nope/ir").status_code == 404
    response = client.get("/api/midi", params={"dataset_id": "spy", "instrument_id": "nope"})
    assert response.status_code == 404
