/** Shared gradients for the instrument art. Rendered once inside the stage SVG. */
export function Defs() {
  return (
    <defs>
      <radialGradient id="mb-sunburst" cx="50%" cy="58%" r="58%">
        <stop offset="0%" stopColor="#f3c25a" />
        <stop offset="45%" stopColor="#d9822b" />
        <stop offset="80%" stopColor="#6e2c0e" />
        <stop offset="100%" stopColor="#1e0e06" />
      </radialGradient>
      <linearGradient id="mb-brass" x1="0" x2="1">
        <stop offset="0%" stopColor="#a87b14" />
        <stop offset="50%" stopColor="#e8c55a" />
        <stop offset="100%" stopColor="#a87b14" />
      </linearGradient>
      <linearGradient id="mb-shell" x1="0" x2="1">
        <stop offset="0%" stopColor="#6d1018" />
        <stop offset="50%" stopColor="#b3212c" />
        <stop offset="100%" stopColor="#6d1018" />
      </linearGradient>
      <radialGradient id="mb-pool">
        <stop offset="0%" stopColor="#fff1b0" />
        <stop offset="70%" stopColor="#fff4c8" stopOpacity="0.7" />
        <stop offset="100%" stopColor="#fff4c8" stopOpacity="0" />
      </radialGradient>
    </defs>
  )
}
