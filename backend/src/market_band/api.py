"""HTTP API for Market Band. OpenAPI docs are served at ``/docs``.

Endpoints:
- ``GET /api/datasets``              datasets available to drag onto the stage
- ``GET /api/instruments``           band members and their pitch ranges
- ``GET /api/datasets/{id}/ir``      the IR series (drives the chart + playhead)
- ``GET /api/genres``                genres the band can play in (first is the default)
- ``GET /api/midi?dataset_id&instrument_id&genre``  the rendered .mid file
"""

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
    DatasetConfig,
    InstrumentConfig,
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


def main() -> None:
    """Serve the API with uvicorn."""
    uvicorn.run("market_band.api:app", host=API_HOST, port=API_PORT, reload=False)
