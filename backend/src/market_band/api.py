"""Market Band demo endpoints plus the generated historical collection."""
from functools import lru_cache
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from market_band.algorithm import render_midi
from market_band.config import API_HOST, API_PORT, CORS_ORIGINS, DATASETS, INSTRUMENTS, PERIOD_LABEL, RAW_DATA_DIR
from market_band.ir import IRSeries, load_raw_stock, stock_to_ir
from market_band.history import make_router

MIDI_MEDIA_TYPE = "audio/midi"
class DatasetInfo(BaseModel):
    id: str
    ticker: str
    name: str
    period: str
class InstrumentInfo(BaseModel):
    id: str
    name: str
    root_midi: int
    octaves: int
app = FastAPI(title="Market Band API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=list(CORS_ORIGINS), allow_methods=["GET"], allow_headers=["*"])
app.include_router(make_router())

def find_dataset(dataset_id):
    for item in DATASETS:
        if item.id == dataset_id:
            return item
    raise HTTPException(404, f"unknown dataset '{dataset_id}'")

def find_instrument(instrument_id):
    for item in INSTRUMENTS:
        if item.id == instrument_id:
            return item
    raise HTTPException(404, f"unknown instrument '{instrument_id}'")

@lru_cache(maxsize=len(DATASETS))
def build_ir(dataset_id: str) -> IRSeries:
    dataset = find_dataset(dataset_id)
    try:
        frame = load_raw_stock(RAW_DATA_DIR/f"{dataset.id}.csv")
    except FileNotFoundError as error:
        raise HTTPException(503, str(error)) from error
    except ValueError as error:
        raise HTTPException(500, str(error)) from error
    return stock_to_ir(dataset.ticker, frame)

@app.get("/api/datasets")
def list_datasets() -> list[DatasetInfo]:
    return [DatasetInfo(id=d.id, ticker=d.ticker, name=d.name, period=PERIOD_LABEL) for d in DATASETS]

@app.get("/api/instruments")
def list_instruments() -> list[InstrumentInfo]:
    return [InstrumentInfo(id=i.id, name=i.name, root_midi=i.root_midi, octaves=i.octaves) for i in INSTRUMENTS]

@app.get("/api/datasets/{dataset_id}/ir")
def get_ir(dataset_id: str) -> IRSeries:
    return build_ir(dataset_id)

@app.get("/api/midi", response_class=Response)
def get_midi(dataset_id: str = Query(min_length=1), instrument_id: str = Query(min_length=1)) -> Response:
    payload = render_midi(build_ir(dataset_id), find_instrument(instrument_id))
    return Response(content=payload, media_type=MIDI_MEDIA_TYPE,
        headers={"Content-Disposition": f'inline; filename="{dataset_id}_{instrument_id}.mid"'})

def main() -> None:
    uvicorn.run("market_band.api:app", host=API_HOST, port=API_PORT, reload=False)
