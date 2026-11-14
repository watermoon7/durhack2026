# Stage frontend: design

## Intent

Replace the demo frontend with a polished, near-textless stage for judges: shapes over words,
light blue + yellow palette, instruments drawn in their real-life colours. Visual reference:
`.superpowers/brainstorm/*/content/stage-look-v2.html` ("Spotlights, tidied").

## Goals

- Five drop targets in one SVG stage: kick, snare, hi-hat (drawn as one kit, top-left), synth
  (centre), bass guitar (top-right). Stock boxes in a bottom tray, draggable onto any piece.
  One stock may sit on several pieces.
- Drag-over glow; assigned piece shows a yellow ring + ticker tag; clicking the tag clears it.
- While playing: each piece pulses on its notes; a dot runs along each stock box's price line;
  a progress ring around the play button.
- Only text on screen: tickers.

## Non-goals

Harmony/clash mappings, scenarios/captions, mobile layout (stage scales, laptop-first), `.mid`
download link, dataset names.

## Anti-goals

Overlapping instruments; drums that sound like a machine gun; anything fetched from the internet.

## Approaches

1. **Backend drum rhythm (chosen).** Per-instrument `subdivisions` and `offset_beats` in backend
   config; drums use level as a small tuning shift. Keeps all musical logic in the backend.
2. Frontend-only drum split by pitch band. Rejected: price level would choose the drum, which is
   hard to explain.

## Decided

- Backend instruments: `kick` (1,2), `snare` (1,2, offset 0.5 beat), `hihat` (2,4), `synth`
  (1,2,4), `bass` (1,2,4). Drums get a 1-octave range (level → subtle tuning); intensity →
  velocity unchanged.
- Frontend: Vite + React + TS strict + Tone.js as now. Drum voices are Tone synths
  (MembraneSynth kick, NoiseSynth snare, MetalSynth hi-hat); no samples.
- Native HTML5 drag-and-drop: HTML stock boxes as sources, SVG piece groups as targets.

## Left to the builder

Exact synth presets, pulse animation style, minor geometry.
