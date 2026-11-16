/**
 * Stage geometry, in the stage SVG's viewBox units. Each instrument has an outline (drop
 * area + ring when filled) and a tag anchor (ticker pill). Outlines never overlap.
 */

export const STAGE_WIDTH = 1200
export const STAGE_HEIGHT = 620

export type Outline =
  | { readonly kind: 'circle'; readonly cx: number; readonly cy: number; readonly r: number }
  | {
      readonly kind: 'rect'
      readonly x: number
      readonly y: number
      readonly width: number
      readonly height: number
      readonly rx: number
    }

export interface PiecePlacement {
  readonly outline: Outline
  readonly tag: { readonly x: number; readonly y: number }
}

/** Placement per backend instrument id. */
export const PLACEMENTS: Readonly<Record<string, PiecePlacement>> = {
  kick: { outline: { kind: 'circle', cx: 180, cy: 280, r: 104 }, tag: { x: 180, y: 158 } },
  snare: {
    outline: { kind: 'rect', x: 294, y: 212, width: 102, height: 196, rx: 22 },
    tag: { x: 345, y: 190 },
  },
  hihat: {
    outline: { kind: 'rect', x: 402, y: 136, width: 100, height: 272, rx: 22 },
    tag: { x: 452, y: 112 },
  },
  synth: {
    outline: { kind: 'rect', x: 402, y: 430, width: 396, height: 136, rx: 14 },
    tag: { x: 600, y: 592 },
  },
  bass: {
    outline: { kind: 'rect', x: 990, y: 44, width: 140, height: 432, rx: 28 },
    tag: { x: 1060, y: 500 },
  },
  pad: {
    outline: { kind: 'rect', x: 530, y: 250, width: 270, height: 120, rx: 14 },
    tag: { x: 665, y: 228 },
  },
  guitar: {
    outline: { kind: 'rect', x: 830, y: 44, width: 140, height: 432, rx: 28 },
    tag: { x: 900, y: 500 },
  },
}

/** Soft light pools, one per zone (drums, synth, bass, pad, guitar). */
export const POOLS = [
  { cx: 290, cy: 280, rx: 250, ry: 160 },
  { cx: 600, cy: 498, rx: 230, ry: 95 },
  { cx: 1060, cy: 262, rx: 120, ry: 232 },
  { cx: 665, cy: 310, rx: 170, ry: 90 },
  { cx: 900, cy: 262, rx: 110, ry: 232 },
] as const

export const PLAY = { cx: 600, cy: 80, r: 34, ringR: 42 } as const

/** The Voice piece (a mic, bottom-left): a toggle, not a drop target, so it sits apart. */
export const VOICE = {
  outline: { x: 156, y: 420, width: 128, height: 160, rx: 22 },
  tag: { x: 220, y: 600 },
  pool: { cx: 220, cy: 510, rx: 120, ry: 90 },
} as const
