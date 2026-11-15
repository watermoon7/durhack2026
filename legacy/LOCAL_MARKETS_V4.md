# Local-market seven-track legacy collection

Run (Python 3.11+):
```
git pull --ff-only
pip install -r legacy/requirements-local-markets.txt
python legacy/Local_Markets_Seven_Tracks.py
```
Targets 90 separate 120-second songs: 10 crash/shock windows + 5 stable controls, each with five local stocks and one actual index. Market assignments and inclusive-start/exclusive-end dates are in local_market_periods.json. Global shocks have a local perspective, not a claimed single-country origin. Baskets are illustrative survivors, not reconstructed historical constituents.

This commit is code/configuration, NOT 90 downloaded datasets or production songs. Offline tests passed: daily OHLCV constraints, determinism, lunch breaks, real/partial session handling, seven MIDI instruments, onset counts and 120-second limits. Live downloads/90-pair coverage remain unverified. Yahoo via yfinance needs no paid key; availability, rate limits and usage/redistribution terms still apply.

Optional minute CSVs: legacy/data/local_minute_inputs/<symbol>.csv; columns timestamp,open,high,low,close,volume, with UTC Z or explicit-offset timestamps. Matching JSON must contain symbol, interval="1min", source, adjustments="yahoo_auto_adjust_split_and_dividend". Do not relabel unadjusted data. Complete scheduled real sessions must agree approximately with adjusted daily OHLCV; otherwise the WHOLE session is simulated. Missing real daily anchors fail rather than inventing history.

Simulation: reproducible daily-constrained random bridge, exact daily OHLC and rounded integer volume; partly shared assumed market/day shocks. This is a possible counterfactual path, NOT recovered historical trades, measured intraday correlations or flash-crash timing. Calendars respect scheduled holidays/lunch/half-days but NOT unscheduled halts or security suspensions, including circuit-breaker days. Every source row carries is_simulated/provenance; metrics carry simulated_fraction. Zero index volume stays zero; the counter-guitar uses volatility instead.

Stable controls remain candidates until the actual index has >=30 observations, annualized daily volatility <=18%, max close drawdown <=7%, and absolute return <=12%. Failed candidates are reported, not silently relabelled. Instrument onsets: bass 60, drums 960, quiet lead 240, pad 60 chords, guitar 480, acceleration synth 240, relative-volume/counter-melody guitar 480. Shared calibration across accepted pairs preserves calm/crash differences; all notes stay in a common scale with restrained gains and voice-leading.

Fresh timestamped runs under legacy/data/local_markets_v4 contain per-pair source.csv, daily_anchors.csv, metrics.csv, song.mid, metadata.json; top-level manifests, configuration, calibration and songs.zip. Old songs/website remain unchanged. Only 90/90 means complete; partial runs exit nonzero. Outputs/raw data are NOT auto-published or committed; check redistribution terms first. No frontend changes. US uses ^GSPC, not SPY relabelled as an index.
