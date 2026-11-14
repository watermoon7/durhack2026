"""Static configuration for the Market Band backend.

Holds tunable parameters only. Secrets and per-machine settings belong in environment
variables, not here.
"""

from dataclasses import dataclass
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = BACKEND_ROOT / "data" / "raw"


@dataclass(frozen=True)
class DatasetConfig:
    """A fetchable raw dataset: one ticker over the shared demo period."""

    id: str
    ticker: str
    name: str


@dataclass(frozen=True)
class InstrumentConfig:
    """A band member: the pitch range its notes are drawn from."""

    id: str
    name: str
    root_midi: int  # lowest note; must share pitch class with SCALE_ROOT_PITCH_CLASS
    octaves: int


# --- Data -------------------------------------------------------------------
PERIOD_START = "2020-01-01"  # inclusive
PERIOD_END = "2020-04-01"  # exclusive (yfinance convention)
PERIOD_LABEL = "Q1 2020"

DATASETS: tuple[DatasetConfig, ...] = (
    DatasetConfig(id="spy", ticker="SPY", name="S&P 500 ETF"),
    DatasetConfig(id="aapl", ticker="AAPL", name="Apple"),
    DatasetConfig(id="tsla", ticker="TSLA", name="Tesla"),
    DatasetConfig(id="gld", ticker="GLD", name="Gold ETF"),
    DatasetConfig(id="tlt", ticker="TLT", name="20Y Treasury ETF"),
)

MIN_BEATS = 2  # a series shorter than this cannot be normalised meaningfully

# --- Music ------------------------------------------------------------------
TEMPO_BPM = 120
TICKS_PER_BEAT = 480
SCALE_ROOT_PITCH_CLASS = 0  # C
SCALE_INTERVALS: tuple[int, ...] = (0, 2, 4, 7, 9)  # major pentatonic: nothing clashes (yet)
SUBDIVISIONS: tuple[int, ...] = (1, 2, 4)  # notes per beat, chosen by IR activity
NOTE_LEGATO = 0.9  # fraction of a subdivision a note sounds for
VELOCITY_FLOOR = 0.3  # quietest note as a fraction of full velocity
MIDI_VELOCITY_MAX = 127

INSTRUMENTS: tuple[InstrumentConfig, ...] = (
    InstrumentConfig(id="bass", name="Bass", root_midi=36, octaves=2),
    InstrumentConfig(id="keys", name="Keys", root_midi=48, octaves=2),
    InstrumentConfig(id="lead", name="Lead", root_midi=60, octaves=2),
    InstrumentConfig(id="bells", name="Bells", root_midi=72, octaves=2),
)

# --- API --------------------------------------------------------------------
API_HOST = "127.0.0.1"
API_PORT = 8000
CORS_ORIGINS: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
