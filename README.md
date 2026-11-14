# Market Band

Choose one of ten market events, then build a tune on the seven-instrument stage.

The original stock tray contains SPY, AAPL, TSLA, GLD and TLT using the committed
Q1 2020 OHLCV data. Their charts and playback are independent of event selection.
A separate yellow crash card plays the selected event's original arrangement:
its drum part on Kick/Snare/Hi-hat, bass on Bass, lead/pad on the two synths,
and guitar on Guitar. It has no price chart because these legacy files contain
MIDI rather than raw prices. Stock card tooltips include the data period.

The event catalog comes from `legacy/data/market_events_v3/manifest.csv` and each
crash arrangement from its `song.mid`. Use **Events** to return to the menu;
changing sessions stops and clears the current tune. Event links support browser Back.

Instrument samples load on first assignment, restricted to the playable range.
The stage and stock tray appear before charts finish loading; Play waits only
for assigned instruments, with a loading indicator during sample decoding.

```
raw OHLCV CSV ──► IR (level, activity, intensity per beat) ──► .mid ──► Tone.js instrument
   backend/data/raw     backend market_band/ir.py          algorithm.py    frontend audio/band.ts
```

| IR channel | From stock data | Music |
|---|---|---|
| `level` | min-max of log adj close over the window | pitch (snapped to C major pentatonic) |
| `activity` | percentile of daily range (high − low) / close | notes per beat: 1, 2 or 4 |
| `intensity` | percentile of volume | velocity + filter brightness |

1 trading day = 1 beat. 62 days at 120 bpm ≈ 31 s, looped.

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
