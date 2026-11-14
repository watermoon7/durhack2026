# Legacy: market-event MIDI algorithm

An alternative algorithm, kept for later. It is not wired into the app: the frontend plays MIDI from the backend in `backend/` (`market_band`).

- `Stock_Data_to_Metrics.py`: daily OHLCV CSV -> music event CSV (see `STOCK_MUSIC.md`)
- `Market_Events_to_MIDI.py`: SPY one-minute data -> ten market-event songs in `data/market_events/`
- `Market_Events_Five_Tracks.py`: five-track arrangements (drums, bass, synth lead, pad, guitar) in `data/market_events_v3/`

Scripts resolve `data/` relative to this folder. Install with `pip install -r requirements-stock-music.txt`.

A frontend player for the `data/market_events_v3` songs exists in commit `4869758` (`frontend/src/songs.ts`), reverted in `90b31e4`.
