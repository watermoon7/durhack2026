"""Static configuration for the Market Band backend.

Holds tunable parameters only. Secrets and per-machine settings belong in environment
variables, not here.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

BACKEND_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = BACKEND_ROOT / "data" / "raw"


@dataclass(frozen=True)
class DatasetConfig:
    """A fetchable raw dataset: one ticker, fetched over the demo period or a scenario window."""

    id: str
    ticker: str
    name: str
    has_volume: bool = True  # False for indices and FX pairs: Yahoo reports their volume as 0


@dataclass(frozen=True)
class ScenarioConfig:
    """A historical market event: a date window and the band of datasets fetched for it."""

    id: str
    name: str
    start: str  # inclusive, YYYY-MM-DD
    end: str  # exclusive (yfinance convention)
    datasets: tuple[DatasetConfig, ...]


Role = Literal["drum", "lead", "bass", "pad", "guitar"]  # selects the instrument's renderer


@dataclass(frozen=True)
class InstrumentConfig:
    """A band member: its pitch range, its part in the band and (drums) its rhythm grid."""

    id: str
    name: str
    root_midi: int  # lowest note; must share pitch class with SCALE_ROOT_PITCH_CLASS
    octaves: int
    role: Role
    subdivisions: tuple[int, ...] = ()  # drums: notes per beat, chosen by activity (low -> high)
    offset_beats: float = 0.0  # drums: delay within each beat (0.5 puts the snare between kicks)


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

# --- Scenarios --------------------------------------------------------------
# The events in legacy/data/market_events/manifest.csv, each cut to ~3 months (<= 1 trading
# day per beat of the 64-beat song) so the shock isn't averaged away. Each band is a shared core
# (stocks, bonds, gold) plus an event-specific FX pair and 1-2 assets at the centre of it.
SCENARIO_DATA_DIR = RAW_DATA_DIR / "scenarios"  # files land at <dir>/<scenario>/<dataset>.csv
MAX_START_GAP_DAYS = 7  # first row later than this after the window start: asset didn't exist yet

_SPY = DatasetConfig(id="spy", ticker="SPY", name="S&P 500 ETF")
_TLT = DatasetConfig(id="tlt", ticker="TLT", name="20Y Treasury ETF")
_GLD = DatasetConfig(id="gld", ticker="GLD", name="Gold ETF")
_CORE: tuple[DatasetConfig, ...] = (_SPY, _TLT, _GLD)


def _fx(id_: str, ticker: str, name: str) -> DatasetConfig:
    """Build an FX or index dataset, which Yahoo serves without volume."""
    return DatasetConfig(id=id_, ticker=ticker, name=name, has_volume=False)


SCENARIOS: tuple[ScenarioConfig, ...] = (
    ScenarioConfig(
        id="2010_flash_crash",
        name="2010 Flash Crash",
        start="2010-04-01",
        end="2010-07-01",
        datasets=(
            *_CORE,
            _fx("eurusd", "EURUSD=X", "Euro / US Dollar"),
            DatasetConfig(id="pg", ticker="PG", name="Procter & Gamble"),
            DatasetConfig(id="acn", ticker="ACN", name="Accenture"),
        ),
    ),
    ScenarioConfig(
        id="2011_debt_ceiling_euro_crisis",
        name="2011 Debt Ceiling & Euro Crisis",
        start="2011-07-01",
        end="2011-10-01",
        datasets=(
            *_CORE,
            _fx("usdchf", "CHF=X", "US Dollar / Swiss Franc"),
            DatasetConfig(id="bac", ticker="BAC", name="Bank of America"),
        ),
    ),
    ScenarioConfig(
        id="2013_taper_tantrum",
        name="2013 Taper Tantrum",
        start="2013-05-01",
        end="2013-08-01",
        datasets=(
            *_CORE,
            _fx("usdinr", "INR=X", "US Dollar / Indian Rupee"),
            DatasetConfig(id="eem", ticker="EEM", name="Emerging Markets ETF"),
        ),
    ),
    ScenarioConfig(
        id="2015_china_devaluation",
        name="2015 China Devaluation",
        start="2015-07-15",
        end="2015-10-15",
        datasets=(
            *_CORE,
            _fx("usdcny", "CNY=X", "US Dollar / Chinese Yuan"),
            DatasetConfig(id="fxi", ticker="FXI", name="China Large-Cap ETF"),
            DatasetConfig(id="baba", ticker="BABA", name="Alibaba"),
        ),
    ),
    ScenarioConfig(
        id="2016_oil_growth_scare",
        name="2016 Oil & Growth Scare",
        start="2015-12-01",
        end="2016-03-01",
        datasets=(
            *_CORE,
            _fx("usdcad", "CAD=X", "US Dollar / Canadian Dollar"),
            DatasetConfig(id="uso", ticker="USO", name="US Oil Fund"),
            DatasetConfig(id="xom", ticker="XOM", name="ExxonMobil"),
        ),
    ),
    ScenarioConfig(
        id="2016_brexit_us_equities",
        name="2016 Brexit Vote",
        start="2016-06-01",
        end="2016-09-01",
        datasets=(
            *_CORE,
            _fx("gbpusd", "GBPUSD=X", "British Pound / US Dollar"),
            DatasetConfig(id="ewu", ticker="EWU", name="UK Equities ETF"),
        ),
    ),
    ScenarioConfig(
        id="2016_us_election",
        name="2016 US Election",
        start="2016-10-01",
        end="2017-01-01",
        datasets=(
            *_CORE,
            _fx("usdmxn", "MXN=X", "US Dollar / Mexican Peso"),
            DatasetConfig(id="xlf", ticker="XLF", name="US Financials ETF"),
        ),
    ),
    ScenarioConfig(
        id="2018_february_volatility",
        name="2018 Volmageddon",
        start="2018-01-01",
        end="2018-04-01",
        datasets=(
            *_CORE,
            _fx("usdtry", "TRY=X", "US Dollar / Turkish Lira"),
            _fx("vix", "^VIX", "VIX Volatility Index"),
            DatasetConfig(id="svxy", ticker="SVXY", name="Short VIX ETF"),
        ),
    ),
    ScenarioConfig(
        id="2018_q4_selloff",
        name="2018 Q4 Selloff",
        start="2018-10-01",
        end="2019-01-01",
        datasets=(
            *_CORE,
            _fx("usdjpy", "JPY=X", "US Dollar / Japanese Yen"),
            DatasetConfig(id="nvda", ticker="NVDA", name="Nvidia"),
            DatasetConfig(id="uso", ticker="USO", name="US Oil Fund"),
        ),
    ),
    ScenarioConfig(
        id="2020_covid_crash_rebound",
        name="2020 COVID Crash & Rebound",
        start="2020-01-15",
        end="2020-04-15",
        datasets=(
            *_CORE,
            _fx("audusd", "AUDUSD=X", "Australian Dollar / US Dollar"),
            DatasetConfig(id="ccl", ticker="CCL", name="Carnival"),
            DatasetConfig(id="zm", ticker="ZM", name="Zoom"),
            DatasetConfig(id="btc", ticker="BTC-USD", name="Bitcoin"),
        ),
    ),
)

MIN_BEATS = 2  # a series shorter than this cannot be normalised meaningfully

# --- Time grid and IR scales ------------------------------------------------
SONG_BARS = 16
BEATS_PER_BAR = 4
SONG_BEATS = SONG_BARS * BEATS_PER_BAR  # 64 beats = 32 s at 120 bpm
MAX_RESAMPLE_RATIO = 2.0  # more source rows than this x beats needs aggregation, not supported
SWING_WINDOW_BEATS = 5  # trailing mean that `swing` measures the price against
# Fixed scales shared by every stock, so a calm stock sounds calm next to a wild one.
ACTIVITY_RANGE_CAP = 0.09  # daily range (high - low) / close that maps to activity 1.0 (sqrt curve)
INTENSITY_VOLUME_CAP = 3.0  # volume / the stock's median volume that maps to intensity 1.0
MOOD_RETURN_BOUND = 0.06  # bar log return of +/- this maps to mood 1.0 / 0.0

# --- Music ------------------------------------------------------------------
TEMPO_BPM = 120
TICKS_PER_BEAT = 480
SCALE_ROOT_PITCH_CLASS = 0  # C
SCALE_INTERVALS: tuple[int, ...] = (0, 2, 4, 7, 9)  # major pentatonic: nothing clashes (yet)
MELODIC_SUBDIVISIONS: tuple[int, ...] = (1, 2, 4)  # notes per beat for pitched instruments
NOTE_LEGATO = 0.9  # fraction of a subdivision a note sounds for
VELOCITY_FLOOR = 0.3  # quietest note as a fraction of full velocity
MIDI_VELOCITY_MAX = 127

# Harmony: C major. Chords are chosen per bar from each stock's mood (see harmony.py).
MAJOR_SCALE: tuple[int, ...] = (0, 2, 4, 5, 7, 9, 11)
# Scale degrees of the chord roots, bright to dark (stacked fifths): IV, I, V, ii, vi, iii.
CHORD_LINE: tuple[int, ...] = (3, 0, 4, 1, 5, 2)

# Lead melody (see lead.py).
LEVEL_SMOOTH_BEATS = 5  # centred mean of level that sets the register (keeps the chart's shape)
# How far swing pushes the note away from the register (0.6 left TSLA at 19.5% jumps).
MELODY_SWING_WEIGHT = 0.8
# Note lengths within one beat, chosen by activity (calm -> busy).
LEAD_PATTERNS: tuple[tuple[float, ...], ...] = (
    (1.0,),
    (0.5, 0.5),
    (0.75, 0.25),
    (0.25, 0.25, 0.25, 0.25),
)
MAX_TIE_BEATS = 4  # a calm repeated note is held, up to this many beats

# Bass (see bass.py).
BASS_MAX_REPEATS = 3  # most consecutive bass notes allowed on one pitch

# Chord parts (see chords.py).
PAD_LOW_MIDI = 36  # the second synth's chord root sits in the octave from C2
GUITAR_LOW_MIDI = 40  # the guitar's chord root sits in the octave from E2 (lowest open string)
STRUM_GAP_BEATS = 0.04  # delay between strings in a strum (20 ms at 120 bpm)
UPSTROKE_VELOCITY_SCALE = 0.7  # upstrokes are lighter than downstrokes

# Ornaments on the lead and guitar (see ornaments.py): placed on busy beats, kind chosen by a
# generator seeded from the stock and instrument, so the same data always gives the same song.
ORNAMENT_TRIGGER = 0.75  # activity at or above which a beat may carry an ornament
ORNAMENT_MIN_GAP_BEATS = 4  # at least this many beats between ornaments


# --- Genres -----------------------------------------------------------------
@dataclass(frozen=True)
class GenreConfig:
    """A band style: the backend changes some parts' notes, the frontend picks the sounds."""

    id: str
    name: str


DEFAULT_GENRE = "default"
# Rock: guitar plays power chords (chords.py); drums add accents (algorithm.py).
GENRES: tuple[GenreConfig, ...] = (
    GenreConfig(id=DEFAULT_GENRE, name="Default"),
    GenreConfig(id="rock", name="Rock"),
)

# Drums use a 1-octave range: level becomes a subtle tuning shift rather than a melody.
INSTRUMENTS: tuple[InstrumentConfig, ...] = (
    InstrumentConfig(
        id="kick", name="Kick", root_midi=24, octaves=1, role="drum", subdivisions=(1, 2)
    ),
    InstrumentConfig(
        id="snare",
        name="Snare",
        root_midi=48,
        octaves=1,
        role="drum",
        subdivisions=(1, 2),
        offset_beats=0.5,
    ),
    InstrumentConfig(
        id="hihat", name="Hi-hat", root_midi=72, octaves=1, role="drum", subdivisions=(2, 4)
    ),
    InstrumentConfig(id="synth", name="Synth", root_midi=60, octaves=2, role="lead"),
    InstrumentConfig(
        id="bass",
        name="Bass",
        root_midi=36,
        octaves=2,
        role="bass",
        subdivisions=MELODIC_SUBDIVISIONS,
    ),
    InstrumentConfig(id="pad", name="Pad", root_midi=36, octaves=3, role="pad"),
    InstrumentConfig(id="guitar", name="Guitar", root_midi=36, octaves=4, role="guitar"),
)

# --- API --------------------------------------------------------------------
API_HOST = "127.0.0.1"
API_PORT = 8000
CORS_ORIGINS: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
