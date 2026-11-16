/**
 * Instrument art in stage coordinates (see layout.ts). Pure drawings: no state, no events.
 * Colours follow the real instruments: red lacquered shells, brass cymbals, chrome hardware,
 * a black synth with wood cheeks, a sunburst bass with a rosewood board, a cream pad synth with
 * blue faders, and a natural-wood acoustic guitar.
 */

const CHROME = '#c9ced4'
const STAND = '#9aa3ad'
const HEAD = '#f4efe4'
/** Synth knob pointer length, so every knob's pointer stops the same distance from its rim. */
const KNOB_POINTER = 7

/** Kick drum, front view, centred at (180, 280). */
export function KickArt() {
  const lugs = [0, 45, 90, 135, 180, 225, 270, 315].map((deg) => {
    const rad = (deg * Math.PI) / 180
    return <circle key={deg} cx={180 + 88 * Math.cos(rad)} cy={280 + 88 * Math.sin(rad)} r={4} />
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
        <line x1={345} y1={268} x2={345} y2={400} />
        <path d="M345 372 L321 400 M345 372 L369 400" />
      </g>
      <path d="M301 232 V266 A44 9 0 0 0 389 266 V232 Z" fill="url(#mb-shell)" />
      <path d="M301 263 A44 9 0 0 0 389 263 V267 A44 9 0 0 1 301 267 Z" fill={CHROME} />
      <ellipse cx={345} cy={232} rx={44} ry={9} fill={HEAD} stroke={CHROME} strokeWidth={3} />
    </g>
  )
}

/** Hi-hat on its stand, centred on x = 452. */
export function HihatArt() {
  return (
    <g>
      <g stroke={STAND} strokeWidth={4} strokeLinecap="round" fill="none">
        <line x1={452} y1={160} x2={452} y2={400} />
        <path d="M452 372 L428 400 M452 372 L476 400" />
      </g>
      <ellipse cx={452} cy={169} rx={46} ry={7} fill="url(#mb-brass)" />
      <ellipse cx={452} cy={160} rx={46} ry={7} fill="url(#mb-brass)" stroke="#a87b14" strokeWidth={1} />
      <circle cx={452} cy={158} r={3} fill="#7a5a10" />
    </g>
  )
}

/** One octave of keys starting at x (synth-local units). */
function Octave({ x }: { readonly x: number }) {
  const whites = [0, 1, 2, 3, 4, 5, 6].map((i) => (
    <rect key={i} x={x + 35 + i * 25} y={62} width={25} height={68} rx={2} />
  ))
  const blacks = [17, 43, 92, 117, 142].map((dx) => (
    <rect key={dx} x={x + 35 + dx} y={62} width={15} height={40} rx={2} />
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
  // Knob centre x and pointer angle (degrees clockwise from up), so the knobs read as set to different values.
  const knobs = [
    { cx: 44, deg: 0 },
    { cx: 74, deg: 45 },
    { cx: 104, deg: -50 },
    { cx: 134, deg: 55 },
    { cx: 164, deg: -20 },
  ]
  return (
    <g transform="translate(410 428) scale(0.905)">
      <rect x={0} y={10} width={18} height={130} rx={4} fill="#8a5632" />
      <rect x={402} y={10} width={18} height={130} rx={4} fill="#8a5632" />
      <rect x={16} y={14} width={388} height={122} rx={6} fill="#1d1f23" />
      {knobs.map(({ cx, deg }) => (
        <g key={cx}>
          <circle cx={cx} cy={38} r={9} fill="#3a3d43" />
          <line
            x1={cx}
            y1={38}
            x2={cx + KNOB_POINTER * Math.sin((deg * Math.PI) / 180)}
            y2={38 - KNOB_POINTER * Math.cos((deg * Math.PI) / 180)}
            stroke="#e9eef3"
            strokeWidth={2}
            strokeLinecap="round"
          />
        </g>
      ))}
      <rect x={216} y={28} width={90} height={22} rx={3} fill="#0d0e10" />
      <circle cx={354} cy={39} r={6} fill="#e3a72f" />
      <circle cx={379} cy={39} r={6} fill="#3a3d43" />
      <Octave x={0} />
      <Octave x={175} />
    </g>
  )
}

/** Tuning pegs at each (x, y), each on a post running in under the headstock. Draw before the headstock. */
function Tuners({ xs, ys, r }: { readonly xs: readonly number[]; readonly ys: readonly number[]; readonly r: number }) {
  if (xs.length === 0 || ys.length === 0) throw new Error('Tuners needs peg positions')
  if (r <= 0) throw new Error('Tuners needs a positive peg radius')
  return (
    <g fill={CHROME} stroke={CHROME}>
      {ys.map((y) => (
        <g key={y}>
          <line x1={xs[0]} y1={y} x2={xs[xs.length - 1]} y2={y} strokeWidth={3} />
          {xs.map((x) => (
            <circle key={x} cx={x} cy={y} r={r} stroke="none" />
          ))}
        </g>
      ))}
    </g>
  )
}

/** Four-string bass guitar, vertical, drawn at 160x420 from (980, 50). */
export function BassArt() {
  const frets = [98, 119, 139, 158, 176, 193, 209, 224, 238]
  const strings = [74, 78, 82, 86]
  return (
    <g transform="translate(980 50)">
      <Tuners xs={[58, 102]} ys={[30, 52]} r={5} />
      <path d="M70 76 L65 22 C65 9 95 9 95 22 L90 76 Z" fill="#e6c487" />
      <path
        d="M80 240 C60 224 26 230 28 262 C30 290 48 300 42 320 C32 346 16 360 22 386 C30 412 62 414 80 408 C98 414 130 412 138 386 C144 360 128 346 118 320 C112 300 130 290 132 262 C134 230 100 224 80 240 Z"
        fill="url(#mb-sunburst)"
      />
      <rect x={70} y={72} width={20} height={178} fill="#e6c487" />
      <rect x={72} y={76} width={16} height={170} fill="#3b2416" />
      <g stroke={CHROME} strokeWidth={1.2}>
        {frets.map((y) => (
          <line key={y} x1={72} y1={y} x2={88} y2={y} />
        ))}
      </g>
      <path
        d="M80 250 C66 244 48 250 50 270 C52 290 62 300 58 318 L102 318 C98 300 108 290 110 270 C112 250 94 244 80 250 Z"
        fill={HEAD}
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

/** Pad synth: a cream keyboard with blue faders, drawn into its 270x120 outline at (530, 250). */
export function PadArt() {
  const faders = [0, 1, 2, 3, 4].map((i) => (
    <g key={i}>
      <rect x={20 + i * 22} y={20} width={4} height={30} rx={2} fill="#9fb3c8" />
      <rect x={15 + i * 22} y={22 + ((i * 7) % 20)} width={14} height={7} rx={2} fill="#5aa9e6" />
    </g>
  ))
  const whites = Array.from({ length: 12 }, (_, i) => (
    <rect key={i} x={15 + i * 20} y={60} width={20} height={48} rx={2} />
  ))
  const blacks = [1, 2, 4, 5, 6, 8, 9, 11].map((i) => (
    <rect key={i} x={15 + i * 20 - 6} y={60} width={12} height={28} rx={2} />
  ))
  return (
    <g transform="translate(530 250)">
      <rect x={4} y={6} width={262} height={108} rx={10} fill="#f3eee2" />
      <path d="M4 16 A10 10 0 0 1 14 6 H256 A10 10 0 0 1 266 16 Z" fill="#5aa9e6" />
      <rect x={4} y={6} width={262} height={108} rx={10} fill="none" stroke="#d8cfbd" strokeWidth={2} />
      {faders}
      <rect x={145} y={22} width={110} height={26} rx={4} fill="#1d2b3a" />
      <path d="M151 40 Q165 26 179 36 T207 34 T249 30" stroke="#ffd23f" strokeWidth={2} fill="none" />
      <g fill="#fbfaf6" stroke="#1d2b3a" strokeWidth={1.2}>{whites}</g>
      <g fill="#1d2b3a">{blacks}</g>
    </g>
  )
}

/** Acoustic guitar, vertical, natural wood with a round sound hole, drawn at 160x420 from (820, 50). */
export function GuitarArt() {
  const frets = [98, 119, 139, 158, 176, 193, 209, 224, 238, 251, 263]
  const strings = [72, 75.2, 78.4, 81.6, 84.8, 88]
  return (
    <g transform="translate(820 50)">
      <Tuners xs={[57, 103]} ys={[22, 38, 54]} r={4.5} />
      <path d="M68 76 L63 18 C63 6 97 6 97 18 L92 76 Z" fill="#8a5632" />
      <rect x={68} y={72} width={24} height={176} fill="#8a5632" />
      <path
        d="M80 236 C52 220 18 232 20 266 C22 296 42 304 36 324 C24 352 14 366 19 392 C26 416 60 418 80 414 C100 418 134 416 141 392 C146 366 136 352 124 324 C118 304 138 296 140 266 C142 232 108 220 80 236 Z"
        fill="#e2b77a"
        stroke="#a87444"
        strokeWidth={3}
      />
      <circle cx={80} cy={296} r={22} fill="#e2b77a" stroke="#a87444" strokeWidth={4} />
      <circle cx={80} cy={296} r={17} fill="#2a1a10" />
      <rect x={70} y={76} width={20} height={192} fill="#3b2416" />
      <g stroke={CHROME} strokeWidth={1.2}>
        {frets.map((y) => (
          <line key={y} x1={70} y1={y} x2={90} y2={y} />
        ))}
      </g>
      <rect x={60} y={360} width={40} height={10} rx={3} fill="#3b2416" />
      <g stroke="#f4efe4" strokeWidth={0.9}>
        {strings.map((x) => (
          <line key={x} x1={x} y1={18} x2={x} y2={366} />
        ))}
      </g>
    </g>
  )
}

/** Vocal mic on a tripod stand, centred on x = 220. */
export function VoiceArt() {
  const grille = [440, 448, 456, 464].map((y) => <line key={y} x1={207} y1={y} x2={233} y2={y} />)
  return (
    <g>
      <g stroke={STAND} strokeWidth={4} strokeLinecap="round" fill="none">
        <line x1={220} y1={508} x2={220} y2={552} />
        <path d="M220 552 L194 572 M220 552 L246 572 M220 552 L220 572" />
      </g>
      <rect x={211} y={474} width={18} height={36} rx={6} fill="#2a2f36" />
      <rect x={204} y={428} width={32} height={48} rx={16} fill={CHROME} />
      <g stroke={STAND} strokeWidth={1.5}>{grille}</g>
      <rect x={208} y={472} width={24} height={6} rx={2} fill={STAND} />
    </g>
  )
}
