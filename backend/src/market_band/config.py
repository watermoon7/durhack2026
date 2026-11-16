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


_CROSS_ASSET_SCENARIOS: tuple[ScenarioConfig, ...] = (
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

# Local-market scenarios, from legacy/local_market_periods.json (main branch): each band is one
# market's headline index plus five large local stocks, over that file's exact windows. 10 are
# crashes and 5 are calm 2017 controls to compare them against. Real daily OHLCV only: the minute
# data that file's generator simulates is not used. Short windows are stretched onto the 16 bars.
_US_BASKET: tuple[DatasetConfig, ...] = (
    _fx("sp500", "^GSPC", "S&P 500 Index"),
    DatasetConfig(id="aapl", ticker="AAPL", name="Apple"),
    DatasetConfig(id="jpm", ticker="JPM", name="JPMorgan Chase"),
    DatasetConfig(id="xom", ticker="XOM", name="ExxonMobil"),
    DatasetConfig(id="jnj", ticker="JNJ", name="Johnson & Johnson"),
    DatasetConfig(id="wmt", ticker="WMT", name="Walmart"),
)
_JP_BASKET: tuple[DatasetConfig, ...] = (
    _fx("nikkei", "^N225", "Nikkei 225 Index"),
    DatasetConfig(id="toyota", ticker="7203.T", name="Toyota"),
    DatasetConfig(id="sony", ticker="6758.T", name="Sony"),
    DatasetConfig(id="mufg", ticker="8306.T", name="Mitsubishi UFJ"),
    DatasetConfig(id="takeda", ticker="4502.T", name="Takeda"),
    DatasetConfig(id="nintendo", ticker="7974.T", name="Nintendo"),
)
_CN_BASKET: tuple[DatasetConfig, ...] = (
    _fx("sse", "000001.SS", "SSE Composite Index"),
    DatasetConfig(id="moutai", ticker="600519.SS", name="Kweichow Moutai"),
    DatasetConfig(id="cmb", ticker="600036.SS", name="China Merchants Bank"),
    DatasetConfig(id="sinopec", ticker="600028.SS", name="Sinopec"),
    DatasetConfig(id="yangtze", ticker="600900.SS", name="China Yangtze Power"),
    DatasetConfig(id="pingan", ticker="601318.SS", name="Ping An Insurance"),
)
_UK_BASKET: tuple[DatasetConfig, ...] = (
    _fx("ftse", "^FTSE", "FTSE 100 Index"),
    DatasetConfig(id="hsbc", ticker="HSBA.L", name="HSBC"),
    DatasetConfig(id="bp", ticker="BP.L", name="BP"),
    DatasetConfig(id="gsk", ticker="GSK.L", name="GSK"),
    DatasetConfig(id="vod", ticker="VOD.L", name="Vodafone"),
    DatasetConfig(id="unilever", ticker="ULVR.L", name="Unilever"),
)
_IN_BASKET: tuple[DatasetConfig, ...] = (
    _fx("nifty", "^NSEI", "Nifty 50 Index"),
    DatasetConfig(id="reliance", ticker="RELIANCE.NS", name="Reliance Industries"),
    DatasetConfig(id="tcs", ticker="TCS.NS", name="Tata Consultancy Services"),
    DatasetConfig(id="hdfc", ticker="HDFCBANK.NS", name="HDFC Bank"),
    DatasetConfig(id="infy", ticker="INFY.NS", name="Infosys"),
    DatasetConfig(id="itc", ticker="ITC.NS", name="ITC"),
)


def _local(
    id_: str, name: str, start: str, end: str, basket: tuple[DatasetConfig, ...]
) -> ScenarioConfig:
    """Build a local-market scenario: one market's basket over a ``[start, end)`` window."""
    assert start < end, f"empty window {start}..{end}"
    assert len(basket) > 0, "basket must not be empty"
    return ScenarioConfig(id=id_, name=name, start=start, end=end, datasets=basket)


_LOCAL_MARKET_SCENARIOS: tuple[ScenarioConfig, ...] = (
    _local("dotcom_2000", "2000 Dot-com Crash · US", "2000-03-01", "2000-07-01", _US_BASKET),
    _local(
        "financial_crisis_2008",
        "2008 Financial Crisis · US",
        "2008-09-01",
        "2009-01-01",
        _US_BASKET,
    ),
    _local("flash_crash_2010", "2010 Flash Crash · US", "2010-05-03", "2010-05-18", _US_BASKET),
    _local(
        "earthquake_2011", "2011 Tōhoku Earthquake · Japan", "2011-03-01", "2011-05-01", _JP_BASKET
    ),
    _local(
        "china_crash_2015", "2015 China Stock Crash · China", "2015-06-01", "2015-09-01", _CN_BASKET
    ),
    _local(
        "china_circuit_breakers_2016",
        "2016 Circuit Breakers · China",
        "2016-01-01",
        "2016-03-01",
        _CN_BASKET,
    ),
    _local("brexit_2016", "2016 Brexit Vote · UK", "2016-06-01", "2016-08-01", _UK_BASKET),
    _local("q4_selloff_2018", "2018 Q4 Selloff · US", "2018-09-01", "2019-01-01", _US_BASKET),
    _local("covid_2020", "2020 COVID Crash · India", "2020-02-01", "2020-05-01", _IN_BASKET),
    _local(
        "japan_august_2024", "2024 Yen Carry Unwind · Japan", "2024-07-01", "2024-09-01", _JP_BASKET
    ),
    _local("stable_us_2017", "2017 Calm · US", "2017-01-01", "2017-04-01", _US_BASKET),
    _local("stable_jp_2017", "2017 Calm · Japan", "2017-06-01", "2017-09-01", _JP_BASKET),
    _local("stable_cn_2017", "2017 Calm · China", "2017-01-01", "2017-04-01", _CN_BASKET),
    _local("stable_uk_2017", "2017 Calm · UK", "2017-03-01", "2017-06-01", _UK_BASKET),
    _local("stable_in_2017", "2017 Calm · India", "2017-04-01", "2017-07-01", _IN_BASKET),
)

SCENARIOS: tuple[ScenarioConfig, ...] = (*_CROSS_ASSET_SCENARIOS, *_LOCAL_MARKET_SCENARIOS)

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
SCALE_INTERVALS: tuple[int, ...] = (0, 3, 5, 7, 10)  # minor pentatonic: nothing clashes (yet)
MELODIC_SUBDIVISIONS: tuple[int, ...] = (1, 2, 4)  # notes per beat for pitched instruments
NOTE_LEGATO = 0.9  # fraction of a subdivision a note sounds for
VELOCITY_FLOOR = 0.3  # quietest note as a fraction of full velocity
MIDI_VELOCITY_MAX = 127

# Harmony: C natural minor. Chords are chosen per bar from each stock's mood (see harmony.py).
KEY_SCALE: tuple[int, ...] = (0, 2, 3, 5, 7, 8, 10)
# Scale degrees of the chord roots, bright to dark (stacked fifths): VI, III, VII, iv, i, v
# (Ab, Eb, Bb, Fm, Cm, Gm). The diminished ii (D F Ab) is left out.
CHORD_LINE: tuple[int, ...] = (5, 2, 6, 3, 0, 4)

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


DEFAULT_GENRE = "rock"
# Rock: guitar plays power chords (chords.py); drums add accents (algorithm.py).
# Rock is the only genre for now; the plain band's code paths stay for when it returns.
GENRES: tuple[GenreConfig, ...] = (GenreConfig(id=DEFAULT_GENRE, name="Rock"),)
# Rock drum accents, as General MIDI drum notes. Toms sit between the kick (24-36) and snare
# (48-60) tuning ranges and the crash above the snare's, so no ordinary hit is mistaken for one.
DRUM_ACCENT_NOTES: dict[str, int] = {
    "crash": 49,
    "tom_hh": 47,
    "tom_h": 45,
    "tom_m": 43,
    "tom_l": 41,
}
# Which drum piece carries which accent in Rock: a tom fill on the snare, a crash on the hi-hat.
ROCK_DRUM_ACCENTS: dict[str, Literal["fill", "crash"]] = {"snare": "fill", "hihat": "crash"}

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
    # 4 octaves: the Bb voicing tops out at D5 (74), above a 3-octave range.
    InstrumentConfig(id="pad", name="Pad", root_midi=36, octaves=4, role="pad"),
    InstrumentConfig(id="guitar", name="Guitar", root_midi=36, octaves=4, role="guitar"),
)

# --- API --------------------------------------------------------------------
API_HOST = "127.0.0.1"
API_PORT = 8000
CORS_ORIGINS: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
