/**
 * Instrument art in stage coordinates (see layout.ts). Pure drawings: no state, no events.
 * Colours follow the real instruments: red lacquered shells, brass cymbals, chrome hardware,
 * a black synth with wood cheeks, a sunburst bass with a rosewood board.
 */

const CHROME = '#c9ced4'
const STAND = '#9aa3ad'
const HEAD = '#f4efe4'

/** Kick drum, front view, centred at (180, 280). */
export function KickArt() {
  const lugs = [0, 45, 90, 135, 180, 225, 270, 315].map((deg) => {
    const rad = (deg * Math.PI) / 180
    return <circle key={deg} cx={180 + 90 * Math.cos(rad)} cy={280 + 90 * Math.sin(rad)} r={4} />
  })
  return (
    <g>
      <path d="M108 340 L90 400 M252 340 L270 400" stroke={STAND} strokeWidth={4} strokeLinecap="round" />
      <circle cx={180} cy={280} r={94} fill="url(#mb-shell)" />
      <circle cx={180} cy={280} r={80} fill={HEAD} stroke={CHROME} strokeWidth={4} />
      <circle cx={180} cy={280} r={26} fill="none" stroke="#e5ddcd" strokeWidth={3} />
      <g fill={CHROME}>{lugs}</g>
    </g>
  )
}

/** Snare on its stand, centred on x = 345. */
export function SnareArt() {
  return (
    <g>
      <g stroke={STAND} strokeWidth={4} strokeLinecap="round" fill="none">
        <line x1={345} y1={268} x2={345} y2={372} />
        <path d="M345 372 L321 400 M345 372 L369 400" />
      </g>
      <rect x={301} y={232} width={88} height={34} fill="url(#mb-shell)" />
      <ellipse cx={345} cy={266} rx={44} ry={9} fill="#5a0d14" />
      <rect x={301} y={232} width={88} height={4} fill={CHROME} />
      <rect x={301} y={262} width={88} height={4} fill={CHROME} />
      <ellipse cx={345} cy={232} rx={44} ry={9} fill={HEAD} stroke={CHROME} strokeWidth={3} />
    </g>
  )
}

/** Hi-hat on its stand, centred on x = 452. */
export function HihatArt() {
  return (
    <g>
      <g stroke={STAND} strokeWidth={4} strokeLinecap="round" fill="none">
        <line x1={452} y1={160} x2={452} y2={392} />
        <path d="M452 372 L428 400 M452 372 L476 400" />
      </g>
      <ellipse cx={452} cy={160} rx={46} ry={7} fill="url(#mb-brass)" />
      <ellipse cx={452} cy={169} rx={46} ry={7} fill="url(#mb-brass)" opacity={0.85} />
      <circle cx={452} cy={158} r={3} fill="#7a5a10" />
    </g>
  )
}

/** One octave of keys starting at x (synth-local units). */
function Octave({ x }: { readonly x: number }) {
  const whites = [0, 1, 2, 3, 4, 5, 6].map((i) => (
    <rect key={i} x={x + 28 + i * 25} y={62} width={25} height={68} rx={2} />
  ))
  const blacks = [17, 43, 92, 117, 142].map((dx) => (
    <rect key={dx} x={x + 28 + dx} y={62} width={15} height={40} rx={2} />
  ))
  return (
    <>
      <g fill="#f7f6f2" stroke="#1d1f23" strokeWidth={1.5}>{whites}</g>
      <g fill="#111214">{blacks}</g>
    </>
  )
}

/** Synth keyboard, drawn at 420x150 and placed into its outline. */
export function SynthArt() {
  // Knob centre x and the end point of its pointer, so the knobs read as set to different values.
  const knobs = [
    { cx: 50, tx: 50, ty: 31 },
    { cx: 80, tx: 85, ty: 33 },
    { cx: 110, tx: 104, ty: 33 },
    { cx: 140, tx: 146, ty: 34 },
    { cx: 170, tx: 170, ty: 31 },
  ]
  return (
    <g transform="translate(410 428) scale(0.905)">
      <rect x={0} y={10} width={18} height={130} rx={4} fill="#8a5632" />
      <rect x={402} y={10} width={18} height={130} rx={4} fill="#8a5632" />
      <rect x={16} y={14} width={388} height={122} rx={6} fill="#1d1f23" />
      {knobs.map(({ cx, tx, ty }) => (
        <g key={cx}>
          <circle cx={cx} cy={38} r={9} fill="#3a3d43" />
          <line
            x1={cx}
            y1={38}
            x2={tx}
            y2={ty}
            stroke="#e9eef3"
            strokeWidth={2}
            strokeLinecap="round"
          />
        </g>
      ))}
      <rect x={220} y={28} width={90} height={22} rx={3} fill="#0d0e10" />
      <circle cx={340} cy={39} r={6} fill="#e3a72f" />
      <circle cx={365} cy={39} r={6} fill="#3a3d43" />
      <Octave x={0} />
      <Octave x={175} />
    </g>
  )
}

/** Four-string bass guitar, vertical, drawn at 160x420 from (980, 50). */
export function BassArt() {
  const frets = [98, 119, 139, 158, 176, 193, 209, 224, 238]
  const strings = [74, 78, 82, 86]
  return (
    <g transform="translate(980 50)">
      <path d="M68 76 L66 22 C66 10 94 8 96 20 L94 76 Z" fill="#e6c487" />
      <g fill={CHROME}>
        <circle cx={60} cy={30} r={5} />
        <circle cx={60} cy={52} r={5} />
        <circle cx={102} cy={30} r={5} />
        <circle cx={102} cy={52} r={5} />
      </g>
      <rect x={70} y={72} width={20} height={178} fill="#e6c487" />
      <rect x={72} y={76} width={16} height={170} fill="#3b2416" />
      <g stroke={CHROME} strokeWidth={1.2}>
        {frets.map((y) => (
          <line key={y} x1={72} y1={y} x2={88} y2={y} />
        ))}
      </g>
      <path
        d="M80 240 C60 224 26 230 28 262 C30 290 48 300 42 320 C32 346 16 360 22 386 C30 412 62 414 80 408 C98 414 130 412 138 386 C144 360 128 346 118 320 C112 300 130 290 132 262 C134 230 100 224 80 240 Z"
        fill="url(#mb-sunburst)"
      />
      <path
        d="M80 250 C66 244 48 250 50 270 C52 290 62 300 58 318 L102 318 C98 300 108 290 110 270 C112 250 94 244 80 250 Z"
        fill={HEAD}
        opacity={0.92}
      />
      <rect x={62} y={300} width={36} height={12} rx={4} fill="#1d1f23" />
      <rect x={62} y={374} width={36} height={12} rx={2} fill={CHROME} />
      <g stroke="#e9eef3" strokeWidth={1}>
        {strings.map((x) => (
          <line key={x} x1={x} y1={22} x2={x} y2={378} />
        ))}
      </g>
    </g>
  )
}

