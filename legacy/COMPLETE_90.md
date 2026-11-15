# Complete 90 pairs with an offline random fallback

Run from repo root:
```
python legacy/Complete_Local_Markets.py
```
Unlike the original strict generator, this runner does NOT require network access, daily anchors, or validated stable candidates to complete. It reuses valid local minute observations (real rows beat synthetic rows), cached genuine daily anchors where available, and generates explicitly unanchored random scenarios for everything still missing. Known observed rows are never changed. Invalid inputs are logged and bypassed. With real daily anchors, existing synthetic rows are regenerated rather than overriding better historical anchors. --data-only omits MIDI; normal use creates all 90 datasets AND 90 seven-instrument MIDI arrangements with shared calibration.

New runs go under legacy/data/local_markets_v4/complete_<timestamp>/ and are automatically discovered by the historical frontend. Old data is not overwritten. Progress prints per pair; wait for COMPLETE: 90/90. Disk/dependency/code errors are still errors, not falsely reported as success.

Every source row has is_simulated/provenance. metadata.json records unanchored_days, calendar_basis, warnings and historical_control_validated=false. Fully synthetic crash/stable behaviour is an artistic scenario, NOT evidence of what that named asset actually did. Prices start at an arbitrary level where there is no real anchor. Synthetic index volume is zero. If exchange calendars cannot load, a labelled weekday-hours template is used; holidays, suspensions and unscheduled halts are not reconstructed. Stable labels describe intended control scenarios, not a new historical certification.

Optional generated data-only ZIP: extract offline_seed_2026 into legacy/data/local_markets_v4/, then run this runner to preserve any better local observations and create metrics/MIDI. The ZIP alone has no playable MIDI. The supplied ZIP contains 90 wholly synthetic CSV datasets, 1,942,830 candles, using weekday session templates. Source CSV counts and ZIP integrity were verified; no genuine local observations were available in the assistant environment. The runner was component-tested for determinism, genuine-row preservation, gap completion and daily-anchor endpoints/extremes/volume. Full Codespace MIDI generation remains to be run.

Both terminals closed? After pulling this commit:
Terminal 1: cd /workspaces/durhack2026; python legacy/Complete_Local_Markets.py; cd backend; uv run market-band-serve
Terminal 2: cd /workspaces/durhack2026/frontend; npm run dev -- --host 0.0.0.0
If legacy Python dependencies are missing, install legacy/requirements-local-markets.txt first. Leave both servers running and reload the forwarded frontend page. Use Refresh generated data after a later completion run.
