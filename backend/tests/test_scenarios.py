import io

import mido
from fastapi.testclient import TestClient

from market_band.api import app
from market_band.config import INSTRUMENTS, SCENARIOS

COVID = "2020_covid_crash_rebound"


def test_lists_every_configured_scenario_in_order() -> None:
    client = TestClient(app)
    response = client.get("/api/scenarios")
    assert response.status_code == 200
    body = response.json()
    assert [s["id"] for s in body] == [s.id for s in SCENARIOS]
    covid = next(s for s in body if s["id"] == COVID)
    assert covid["name"] == "2020 COVID Crash & Rebound"
    assert covid["period"] == "Jan-Apr 2020"
    assert covid["tickers"] == ["SPY", "TLT", "GLD", "AUDUSD", "CCL", "ZM", "BTC"]


def test_period_excludes_end_date_and_names_both_years_when_spanning() -> None:
    client = TestClient(app)
    body = {s["id"]: s for s in client.get("/api/scenarios").json()}
    assert body["2018_q4_selloff"]["period"] == "Oct-Dec 2018"  # end 2019-01-01 is exclusive
    assert body["2016_oil_growth_scare"]["period"] == "Dec 2015-Feb 2016"
    assert body["flash_crash_2010"]["period"] == "May 2010"  # one month: named once


def test_scenario_datasets_match_its_band() -> None:
    client = TestClient(app)
    response = client.get(f"/api/scenarios/{COVID}/datasets")
    assert response.status_code == 200
    body = response.json()
    assert [d["id"] for d in body] == ["spy", "tlt", "gld", "audusd", "ccl", "zm", "btc"]
    assert {d["period"] for d in body} == {"Jan-Apr 2020"}


def test_scenario_ir_fills_the_song_grid() -> None:
    client = TestClient(app)
    response = client.get(f"/api/scenarios/{COVID}/datasets/btc/ir")
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "BTC-USD"
    assert len(body["beats"]) == 64
    assert body["beats"][0]["date"].startswith("2020-01")


def test_every_scenario_dataset_renders_midi() -> None:
    client = TestClient(app)
    instrument = INSTRUMENTS[3].id
    for scenario in SCENARIOS:
        for dataset in scenario.datasets:
            response = client.get(
                f"/api/scenarios/{scenario.id}/midi",
                params={"dataset_id": dataset.id, "instrument_id": instrument},
            )
            assert response.status_code == 200, (scenario.id, dataset.id, response.text)
            assert response.headers["content-type"] == "audio/midi"
            assert len(mido.MidiFile(file=io.BytesIO(response.content)).tracks) > 0


def test_scenario_unknown_ids_404() -> None:
    client = TestClient(app)
    assert client.get("/api/scenarios/nope/datasets").status_code == 404
    assert client.get(f"/api/scenarios/{COVID}/datasets/aapl/ir").status_code == 404
    midi = f"/api/scenarios/{COVID}/midi"
    assert client.get(midi, params={"dataset_id": "spy", "instrument_id": "x"}).status_code == 404
    bad_genre = {"dataset_id": "spy", "instrument_id": "synth", "genre": "jazz"}
    assert client.get(midi, params=bad_genre).status_code == 404
