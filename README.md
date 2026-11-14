# Market Band

Drag a dataset (a stock over Q1 2020) onto an instrument and the band plays it.

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
