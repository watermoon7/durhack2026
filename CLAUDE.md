# DurHack 2026: Market Band

## Concept

Turn data into music. Each data series (a stock, a crypto coin, an FX pair, an index) becomes a member of a band and plays an instrument. The user drags members onto a stage to build an ensemble, then hears how the data played together over time sounds.

- **Notes, rhythm and sound** come from the data. First demo uses three metrics only: price level sets the pitch, daily range sets the rhythm, volume sets velocity + brightness (one combined control). Band-level mappings (correlation → harmony, drawdown → key) come in M3.
- **How the instruments sound together is the insight.** Assets that move together play in harmony; assets that diverge clash. In a crisis, correlations go to 1, and you hear the band lock into unison.
- **Scenarios** replay historical events with a preset band and timed captions (e.g. 2008 crisis, COVID crash, Swiss franc unpeg).

Markets are the core. Other noisy data (weather, solar wind) is a stretch goal only.

## What makes it new

Turning data into sound has existed for decades (MarketBuzz, TwoTone, NASA Chandra, Crawford's climate string quartet). What we haven't found elsewhere:
1. A band of financial assets that the user picks and arranges.
2. Harmony between instruments that encodes how the assets move together.

Lead the pitch with this, not with "data as sound".

## Target challenges

- **Marshall Wace: New Worlds** (primary). A new way to experience data. Judged on creativity, technical complexity and presentation.
- **SGX FX: Trading Market Storm** (secondary, "Early warning" track). A background risk sound that grows more clashing as market stress rises, so traders can monitor without watching every screen. Use SGX's FX data. Cite MarketBuzz: sound improved monitoring when the eyes were busy.
- **DurHack theme:** "Explore art, music and tech!"

## Approach

Pipeline: **raw data → IR → .mid file → instrument.**

- **Backend** (`backend/`, Python, uv, FastAPI on localhost): translates raw data to IR and runs the music algorithm, serving `.mid` files. OpenAPI docs at `/docs`.
- **Frontend** (`frontend/`, Vite + React + TypeScript strict, Tone.js): drag a dataset onto an instrument; it fetches that `.mid`, plays it on the instrument's synth, and shows a playhead over the price shape.
- **Raw data**: daily OHLCV fetched once from yfinance into `backend/data/raw/*.csv` (`uv run market-band-fetch`). Nothing is fetched from the internet during the demo.
- **IR** (source-agnostic, so non-market sources like tweets only need a new adapter): one row per beat, three channels in [0, 1]:
  - `level` → pitch: min-max of log adj close over the window
  - `activity` → rhythm: percentile of (high − low) / close
  - `intensity` → velocity + filter brightness: percentile of volume
- **Algorithm** (deliberately simple): `level` picks a degree of the instrument's 2-octave slice of a shared scale (C major pentatonic for now: no clashes, so harmony isn't audible yet); `activity` picks 1, 2 or 4 notes per beat; `intensity` sets velocity, which the frontend also maps to filter cutoff.
- **Timing**: 120 bpm, 1 trading day = 1 beat. Demo datasets are Q1 2020 (62 trading days ≈ 31 s), looped on a shared transport.
- **Config**: tunables live in `backend/src/market_band/config.py` and `frontend/src/config.ts`; instrument ranges are defined in the backend, sounds in the frontend.
- Later: musical ↔ raw slider (turn off scale snapping) and scenario captions.

### Open decisions

- **MIDI clip format.** Considered: every `.mid` is 4 bars of 4/4 at 120 bpm (16 beats). Deferred because it conflicts with 1 day = 1 beat for a 62-day quarter. Options: 1 day = 1 sixteenth note (64 slots, rhythm then becomes note/rest/hold), resample ~4 days per beat, or shorten datasets to 16 days.

## Milestones

- **M0: Lock decisions.** Stack, mapping principles, data sources, headline scenario.
- **M1: First sound.** One dataset → one instrument, in key. Go/no-go check: does it sound good?
- **M2: The band.** Several instruments, drag-and-drop stage, shared clock, mute/solo.
- **M3: Meaningful mapping.** Correlation → harmony, volatility → rhythm, drawdown → key. Synced charts.
- **M4: Scenarios.** Preset bands plus event captions. Polish 2008 before adding more.
- **M5: Challenge layer.** SGX risk sound on FX data. Extra data domains only if time allows.
- **M6: Pitch.** Demo script around the "correlations go to 1" moment, recorded fallback, headphones, Devpost write-up.
