"""HTTP API for Market Band. OpenAPI docs are served at ``/docs``.

Endpoints:
- ``GET /api/datasets``              datasets available to drag onto the stage
- ``GET /api/instruments``           band members and their pitch ranges
- ``GET /api/datasets/{id}/ir``      the IR series (drives the chart + playhead)
- ``GET /api/genres``                genres the band can play in (first is the default)
- ``GET /api/midi?dataset_id&instrument_id&genre``  the rendered .mid file
- ``GET /api/scenarios``             historical events for the menu, each with its own band
- ``GET /api/scenarios/{id}/datasets``, ``.../datasets/{id}/ir``, ``.../midi``  as above, per event
"""

from datetime import date, timedelta
from functools import lru_cache

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from market_band.algorithm import render_midi
from market_band.config import (
    API_HOST,
    API_PORT,
    CORS_ORIGINS,
    DATASETS,
    DEFAULT_GENRE,
    GENRES,
    INSTRUMENTS,
    PERIOD_LABEL,
    RAW_DATA_DIR,
    SCENARIO_DATA_DIR,
    SCENARIOS,
    DatasetConfig,
    InstrumentConfig,
    ScenarioConfig,
)
from market_band.ir import IRSeries, load_raw_stock, stock_to_ir

MIDI_MEDIA_TYPE = "audio/midi"


class DatasetInfo(BaseModel):
    """A dataset as listed to the frontend."""

    id: str
    ticker: str
    name: str
    period: str


class InstrumentInfo(BaseModel):
    """An instrument as listed to the frontend."""

    id: str
    name: str
    root_midi: int
    octaves: int


app = FastAPI(title="Market Band API", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=list(CORS_ORIGINS), allow_methods=["GET"], allow_headers=["*"]
)


def find_dataset(dataset_id: str) -> DatasetConfig:
    """Look up a configured dataset or raise 404."""
    for dataset in DATASETS:
        if dataset.id == dataset_id:
            return dataset
    raise HTTPException(status_code=404, detail=f"unknown dataset '{dataset_id}'")


def find_instrument(instrument_id: str) -> InstrumentConfig:
    """Look up a configured instrument or raise 404."""
    for instrument in INSTRUMENTS:
        if instrument.id == instrument_id:
            return instrument
    raise HTTPException(status_code=404, detail=f"unknown instrument '{instrument_id}'")


@lru_cache(maxsize=len(DATASETS))
def build_ir(dataset_id: str) -> IRSeries:
    """Translate a dataset's cached raw CSV into IR (cached: inputs are static files)."""
    dataset = find_dataset(dataset_id)
    try:
        frame = load_raw_stock(RAW_DATA_DIR / f"{dataset.id}.csv")
    except FileNotFoundError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    return stock_to_ir(dataset.ticker, frame)


@app.get("/api/datasets")
def list_datasets() -> list[DatasetInfo]:
    """List the datasets that can be assigned to instruments."""
    return [
        DatasetInfo(id=d.id, ticker=d.ticker, name=d.name, period=PERIOD_LABEL) for d in DATASETS
    ]


@app.get("/api/instruments")
def list_instruments() -> list[InstrumentInfo]:
    """List the band's instruments."""
    return [
        InstrumentInfo(id=i.id, name=i.name, root_midi=i.root_midi, octaves=i.octaves)
        for i in INSTRUMENTS
    ]


class GenreInfo(BaseModel):
    """A genre as listed to the frontend."""

    id: str
    name: str


@app.get("/api/genres")
def list_genres() -> list[GenreInfo]:
    """List the genres the band can play in; the first is the default."""
    return [GenreInfo(id=g.id, name=g.name) for g in GENRES]


@app.get("/api/datasets/{dataset_id}/ir")
def get_ir(dataset_id: str) -> IRSeries:
    """Return the IR series for a dataset."""
    return build_ir(dataset_id)


@app.get(
    "/api/midi",
    response_class=Response,
    responses={200: {"content": {MIDI_MEDIA_TYPE: {}}, "description": "A type-0 .mid file"}},
)
def get_midi(
    dataset_id: str = Query(min_length=1),
    instrument_id: str = Query(min_length=1),
    genre: str = Query(default=DEFAULT_GENRE, min_length=1),
) -> Response:
    """Render a dataset as a .mid file for the given instrument and genre."""
    instrument = find_instrument(instrument_id)
    if genre not in {g.id for g in GENRES}:
        raise HTTPException(status_code=404, detail=f"unknown genre '{genre}'")
    payload = render_midi(build_ir(dataset_id), instrument, genre)
    filename = f"{dataset_id}_{instrument_id}.mid"
    return Response(
        content=payload,
        media_type=MIDI_MEDIA_TYPE,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


# --- Scenarios --------------------------------------------------------------
# Each scenario serves its own band from data/raw/scenarios/<scenario>/<dataset>.csv through the
# same IR and renderers as the default datasets.


class ScenarioInfo(BaseModel):
    """A historical event as listed on the menu."""

    id: str
    name: str
    period: str  # e.g. "Jan-Apr 2020"
    tickers: list[str]  # display tickers of the scenario's band, in tray order


def find_scenario(scenario_id: str) -> ScenarioConfig:
    """Look up a configured scenario or raise 404."""
    for scenario in SCENARIOS:
        if scenario.id == scenario_id:
            return scenario
    raise HTTPException(status_code=404, detail=f"unknown scenario '{scenario_id}'")


def find_scenario_dataset(scenario: ScenarioConfig, dataset_id: str) -> DatasetConfig:
    """Look up a dataset in a scenario's band or raise 404."""
    for dataset in scenario.datasets:
        if dataset.id == dataset_id:
            return dataset
    raise HTTPException(
        status_code=404, detail=f"scenario '{scenario.id}' has no dataset '{dataset_id}'"
    )


def period_label(start: str, end_exclusive: str) -> str:
    """Name a date window by month, e.g. "Jan-Apr 2020" or "Dec 2015-Feb 2016"."""
    first = date.fromisoformat(start)
    last = date.fromisoformat(end_exclusive) - timedelta(days=1)
    if last < first:
        raise ValueError(f"empty window {start}..{end_exclusive}")
    if (first.year, first.month) == (last.year, last.month):
        return f"{first:%b %Y}"
    if first.year == last.year:
        return f"{first:%b}-{last:%b %Y}"
    return f"{first:%b %Y}-{last:%b %Y}"


def display_ticker(dataset: DatasetConfig) -> str:
    """Short tray label: the dataset id, since Yahoo tickers carry suffixes ("EURUSD=X")."""
    if dataset.id == "":
        raise ValueError("dataset id is empty")
    return dataset.id.upper()


@lru_cache(maxsize=sum(len(s.datasets) for s in SCENARIOS))
def build_scenario_ir(scenario_id: str, dataset_id: str) -> IRSeries:
    """Translate one scenario dataset's raw CSV into IR (cached: inputs are static files)."""
    scenario = find_scenario(scenario_id)
    dataset = find_scenario_dataset(scenario, dataset_id)
    try:
        frame = load_raw_stock(SCENARIO_DATA_DIR / scenario.id / f"{dataset.id}.csv")
    except FileNotFoundError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    return stock_to_ir(dataset.ticker, frame)


@app.get("/api/scenarios")
def list_scenarios() -> list[ScenarioInfo]:
    """List the historical events, in menu order."""
    return [
        ScenarioInfo(
            id=s.id,
            name=s.name,
            period=period_label(s.start, s.end),
            tickers=[display_ticker(d) for d in s.datasets],
        )
        for s in SCENARIOS
    ]


@app.get("/api/scenarios/{scenario_id}/datasets")
def list_scenario_datasets(scenario_id: str) -> list[DatasetInfo]:
    """List a scenario's band: the datasets that can be assigned to instruments."""
    scenario = find_scenario(scenario_id)
    period = period_label(scenario.start, scenario.end)
    return [
        DatasetInfo(id=d.id, ticker=display_ticker(d), name=d.name, period=period)
        for d in scenario.datasets
    ]


@app.get("/api/scenarios/{scenario_id}/datasets/{dataset_id}/ir")
def get_scenario_ir(scenario_id: str, dataset_id: str) -> IRSeries:
    """Return the IR series for one dataset of a scenario."""
    return build_scenario_ir(scenario_id, dataset_id)


@app.get(
    "/api/scenarios/{scenario_id}/midi",
    response_class=Response,
    responses={200: {"content": {MIDI_MEDIA_TYPE: {}}, "description": "A type-0 .mid file"}},
)
def get_scenario_midi(
    scenario_id: str,
    dataset_id: str = Query(min_length=1),
    instrument_id: str = Query(min_length=1),
    genre: str = Query(default=DEFAULT_GENRE, min_length=1),
) -> Response:
    """Render one dataset of a scenario as a .mid file for the given instrument and genre."""
    instrument = find_instrument(instrument_id)
    if genre not in {g.id for g in GENRES}:
        raise HTTPException(status_code=404, detail=f"unknown genre '{genre}'")
    payload = render_midi(build_scenario_ir(scenario_id, dataset_id), instrument, genre)
    filename = f"{scenario_id}_{dataset_id}_{instrument_id}.mid"
    return Response(
        content=payload,
        media_type=MIDI_MEDIA_TYPE,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


def main() -> None:
    """Serve the API with uvicorn."""
    uvicorn.run("market_band.api:app", host=API_HOST, port=API_PORT, reload=False)
