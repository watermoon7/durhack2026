# Stage Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the demo UI with a near-textless SVG stage (drum kit of 3 drop targets, synth, bass) fed by draggable stock boxes, backed by per-instrument rhythm in the backend.

**Architecture:** Backend `InstrumentConfig` gains `subdivisions` and `offset_beats`; the algorithm reads them instead of the global `SUBDIVISIONS`. Frontend renders one SVG stage; each piece is a drop target; `band.ts` builds a voice per instrument (pitched synth or drum synth) and reports note events for pulse animation.

**Tech Stack:** Python 3.13 / FastAPI / mido / pytest; Vite + React 19 + TS strict + Tone.js 15 + zod.

**Spec:** `docs/superpowers/specs/2026-11-14-stage-frontend-design.md`

## Global Constraints

- Only on-screen text: tickers.
- Palette: room `#dcefff`, tray `#cbe5fb`, yellow `#ffd23f`, ring `#ffb800`, ink `#1d2b3a`, line `#5aa9e6`.
- Instruments in real colours (red shells, brass cymbals, black synth with wood cheeks, sunburst bass).
- No overlapping instruments; layout from mockup v2 (viewBox 1200×760).
- Tunables in `backend/src/market_band/config.py` / `frontend/src/config.ts`. TS strict, oxlint, ruff, mypy clean.

## Review Focus

- Dropping a stock on a piece that already has one: replaces it (no double scheduling).
- Clearing every piece while playing: transport stops looping, no stale events fire.
- Backend down at load: an error toast instead of a blank stage.
- Drag of a non-stock item (e.g. a file) onto a piece: ignored.
- Snare offset notes stay inside the loop (last note ends ≤ len(beats)).

---

### Task 1: Per-instrument rhythm in backend

**Files:** Modify `backend/src/market_band/config.py`, `backend/src/market_band/algorithm.py`, `backend/tests/test_pipeline.py`

**Interfaces:**
- Produces: `InstrumentConfig(id, name, root_midi, octaves, subdivisions: tuple[int, ...], offset_beats: float = 0.0)`; `beat_to_notes(index, beat, scale, instrument)`; `INSTRUMENTS` ids `kick, snare, hihat, synth, bass`.

- [ ] Tests: `test_kick_never_exceeds_two_hits` (activity=1 → 2 notes); `test_snare_offset_shifts_start` (index 3 → first start 3.5); `test_offset_notes_fit_in_beat` (all notes end ≤ index+1); update KEYS fixture to pass `subdivisions=(1,2,4)`.
- [ ] Run → fail. Implement. Instruments: kick 24/1 oct (1,2); snare 48/1 (1,2) offset 0.5; hihat 72/1 (2,4); synth 60/2 (1,2,4); bass 36/2 (1,2,4). Step = (1 − offset) / count.
- [ ] `uv run pytest && uv run ruff check && uv run mypy src` → pass. Commit.

### Task 2: Audio engine voices + note events

**Files:** Modify `frontend/src/config.ts`, `frontend/src/audio/band.ts`

**Interfaces:**
- Produces: `createBand(ids, onNote: (instrumentId: string, velocity: number) => void): Band`; `Band.loopBeats(): number`.
- Voice kinds in `SOUND_PRESETS`: `{kind:'pitched', ...}`, `{kind:'kick'|'snare'|'hihat', volumeDb}`.

- [ ] Implement voices (MembraneSynth / NoiseSynth / MetalSynth; pitched keeps filter); `Tone.getDraw().schedule` calls `onNote`.
- [ ] `npm run build && npm run lint` → zero warnings. Commit with Task 3.

### Task 3: Stage UI

**Files:** Create `frontend/src/components/{Stage,DrumKit,Synth,BassGuitar,StockTray,Defs,Tag}.tsx`, `frontend/src/hooks/usePlayhead.ts`; Rewrite `App.tsx`, `App.css`, `index.css`; Delete `InstrumentSlot.tsx`, `LevelChart.tsx`.

- [ ] Stage geometry per mockup v2; `DropTarget` wrapper `<g>` handles dragover/drop with `DRAG_MIME`, glow on hover, pulse class on note.
- [ ] Tray: stock boxes with ticker + sparkline (from IR level) + playhead dot; prefetch all IRs on load.
- [ ] Play button with progress ring; error toast.
- [ ] `npm run build && npm run lint` → zero warnings. Commit.

### Task 4: Run it

- [ ] Start backend (`uv run market-band-serve`) and frontend (`npm run dev`); load in browser; drag, play, clear; screenshot.
- [ ] Add `.superpowers/` to root `.gitignore`.
