# Historical frontend integration

Restart the backend after pulling: cd backend && uv run market-band-serve. Keep the Vite dev server running. The existing drag/drop UI now uses /api/history rather than the Q1-2020 demo API. Choose any of the 15 configured periods, then assign its local assets independently to seven instrument slots. Changing periods stops and clears the old mix and invalidates pending requests.

The catalogue merges successful pairs across ALL legacy/data/*v4* run manifests; latest valid pair wins. No files are moved/overwritten. Only complete seven-track assets with simulation provenance are playable. Different runs may use different calibration sets. Browser timbres use native Web Audio synthesis/plucked envelopes and GM-driven percussion; original sample files remain untouched.

Missing periods show available/6 and manifest errors, never demo replacements. To create missing pairs run python legacy/Local_Markets_Seven_Tracks.py after installing its requirements; then click Refresh generated data. All 90 pairs are needed for completion. This integration does NOT generate missing production data itself. /api/history/catalogue exposes diagnostics. Backend and generator must share the same checkout/filesystem.

Per-instrument playback extracts a single MIDI track plus tempo from the selected asset; charts use 240 observations matching the 240-beat loop. Simulation fractions stay visible. Fixture tests passed for merging 90 pairs/15 periods, corruption rejection, older-success retention, single-track tempo and chart alignment. Live HTTP, frontend build/browser audio and production data generation were not run here.
