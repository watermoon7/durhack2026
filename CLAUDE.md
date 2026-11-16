# DurHack 2026: Market Band

## Concept

Turn data into music. Each data series (a stock, a crypto coin, an FX pair, an index) becomes a member of a band and plays an instrument. The user drags members onto a stage to build an ensemble, then hears how the data played together over time sounds.

- **Notes, chords, rhythm and sound** come from the data: each stock picks its own chord every bar from its return, its price shape sets the melody, its daily range sets the rhythm, and its volume sets velocity + brightness. Only the key (C major), the pool of six chords, the tempo and the 16-bar length are fixed.
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
- **IR** (source-agnostic, so non-market sources like tweets only need a new adapter): every dataset is resampled onto the song grid (64 beats). All channels are in [0, 1]. Pitch channels are scaled per stock; rhythm, loudness and mood use fixed scales shared by every stock, so a calm stock sounds calm next to a wild one.
  - per beat `level` → melody register: min-max of log adj close
  - per beat `swing` → melodic jumps: log close minus its trailing 5-beat mean, ranked
  - per beat `activity` → rhythm: sqrt of (high − low) / close, 1.0 at a 9% daily range
  - per beat `intensity` → velocity + filter brightness: volume / the stock's median, 1.0 at 3x
  - per bar `mood` → chord: bar log return, 0 at −6%, 1 at +6%
- **Algorithm** (one renderer per instrument `role`, all in C major): `mood` picks each bar's chord from the line IV, I, V, ii, vi, iii (bright → dark), per stock, so stocks moving together agree and diverging stocks clash. `lead` (synth): smoothed `level` + `swing` choose notes from the chord (chord tones on beats 1 and 3), `activity` picks note lengths, calm repeats are held. `bass`: chord root on beat 1, fifth/octave by `swing`, steps into the next chord, never more than 3 repeats. `pad` (second synth): root, octave, fifth, root, third, struck 1/2/4 times a bar. `guitar`: strummed open-position voicing, down or down-up by `activity`. `drum`: unchanged beat grid. Busiest beats get seeded ornaments (grace, mordent, trill, run on the lead; roll or hammer-on on the guitar).
- **Mix** (frontend): each instrument has a high-pass, 3-band EQ and reverb send (`GENRE_MIX`), into a master compressor and limiter.
- **Genres** (dropdown, top-left): `GENRES` in backend config, `GENRE_SOUNDS` and `GENRE_MIX` in frontend config; `/api/midi` takes `genre`. **Rock** is the only genre for now (Default was removed from `GENRES`, `GENRE_SOUNDS` and `GENRE_MIX`; `DEFAULT_SOUNDS`/`DEFAULT_MIX` remain as Rock's base, and the plain guitar/drum code paths are kept for when it returns). **Rock**: guitar plays power chords on `distortion_guitar`, bass is `electric_bass_pick`, the pad piece plays `rock_organ`, drums are the LinnDrum (LM-2) kit with a crash on beat 1 after a busy bar (hi-hat piece) and a four-tom fill on busy fourth beats (snare piece). Accent notes are GM drum numbers outside every drum tuning range. Stage art is the same for every genre. Changing genre while playing swaps sounds once loaded and re-renders every part. Adding a genre: one entry in each of those three places.
- **Timing**: 120 bpm, 16 bars of 4 beats = 64 beats = 32 s, looped on a shared transport. Each `.mid` ends exactly at beat 64. Q1 2020 (62 trading days) is stretched to fit; datasets over 2× the beat count are refused.
- **Config**: tunables live in `backend/src/market_band/config.py` and `frontend/src/config.ts`; instrument ranges are defined in the backend, sounds in the frontend.
- **Legacy algorithm** (`legacy/`): a teammate's market-event → multi-track MIDI scripts and their data. Kept for later; not wired into the app. See `legacy/README.md`.
- Later: musical ↔ raw slider (turn off scale snapping) and scenario captions.

## Milestones

- **M0: Lock decisions.** Stack, mapping principles, data sources, headline scenario.
- **M1: First sound.** One dataset → one instrument, in key. Go/no-go check: does it sound good?
- **M2: The band.** Several instruments, drag-and-drop stage, shared clock, mute/solo.
- **M3: Meaningful mapping.** Correlation → harmony, volatility → rhythm, drawdown → key. Synced charts.
- **M4: Scenarios.** Preset bands plus event captions. Polish 2008 before adding more.
- **M5: Challenge layer.** SGX risk sound on FX data. Extra data domains only if time allows.
- **M6: Pitch.** Demo script around the "correlations go to 1" moment, recorded fallback, headphones, Devpost write-up.
