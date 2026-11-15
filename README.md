# Market Band

Drag a dataset (a stock over Q1 2020) onto an instrument and the band plays it.

```
raw OHLCV CSV ──► IR (64 beats, 16 bars) ──► .mid per instrument ──► Tone.js voice ──► mix
   backend/data/raw   market_band/ir.py        algorithm.py + one module per role   audio/band.ts, mix.ts
```

| IR channel | From stock data | Music |
|---|---|---|
| `level` (beat) | min-max of log adj close | melody register (smoothed) |
| `swing` (beat) | log close minus its 5-beat mean, ranked | melodic jumps; bass root / fifth / octave |
| `activity` (beat) | sqrt of daily range / close, 1.0 at 9% | note lengths, strum and strike patterns, drum density, ornaments |
| `intensity` (beat) | volume / median volume, 1.0 at 3x | velocity + filter brightness |
| `mood` (bar) | bar log return, ±6% | the bar's chord: IV, I, V, ii, vi, iii (bright → dark) |

Each stock picks its own chords, so instruments carrying stocks that move together agree and diverging ones clash.

| Instrument | Role | Plays |
|---|---|---|
| Kick, snare, hi-hat | `drum` | beat grid; activity sets hits per beat |
| Synth | `lead` | melody from the chord's notes, varied lengths, ornaments |
| Bass | `bass` | chord root, fifth and octave; steps into chord changes; max 3 repeats |
| Pad | `pad` | root, octave, fifth, root, third; struck 1, 2 or 4 times a bar |
| Guitar | `guitar` | strummed open voicing, down or down-up; rolls and hammer-ons |

16 bars of 4 beats at 120 bpm = 32 s, looped. Q1 2020 (62 trading days) is stretched onto the 64 beats.

## Run

```bash
# backend (http://127.0.0.1:8000, OpenAPI docs at /docs)
cd backend
uv run market-band-fetch   # one-off: refresh data/raw/*.csv from yfinance (already committed)
uv run market-band-serve

# frontend (http://localhost:5173)
cd frontend
npm install
npm run dev
```

## Checks

```bash
cd backend && uv run pytest && uv run ruff check . && uv run mypy src tests
cd frontend && npm run lint && npm run build
```
