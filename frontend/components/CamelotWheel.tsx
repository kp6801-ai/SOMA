'use client'

const KEYS = [
  { code: '1A', label: 'Ab m' }, { code: '2A', label: 'Eb m' },
  { code: '3A', label: 'Bb m' }, { code: '4A', label: 'F m'  },
  { code: '5A', label: 'C m'  }, { code: '6A', label: 'G m'  },
  { code: '7A', label: 'D m'  }, { code: '8A', label: 'A m'  },
  { code: '9A', label: 'E m'  }, { code: '10A', label: 'B m' },
  { code: '11A', label: 'F# m'},  { code: '12A', label: 'Db m'},
  { code: '1B', label: 'B Maj' }, { code: '2B', label: 'F# Maj'},
  { code: '3B', label: 'Db Maj'},{ code: '4B', label: 'Ab Maj'},
  { code: '5B', label: 'Eb Maj'},{ code: '6B', label: 'Bb Maj'},
  { code: '7B', label: 'F Maj' },{ code: '8B', label: 'C Maj' },
  { code: '9B', label: 'G Maj' },{ code: '10B', label: 'D Maj'},
  { code: '11B', label: 'A Maj'},{ code: '12B', label: 'E Maj'},
]

function getCompatible(code: string): string[] {
  if (!code) return []
  const num = parseInt(code)
  const letter = code.replace(/\d+/, '')
  const opposite = letter === 'A' ? 'B' : 'A'
  const prev = num === 1 ? 12 : num - 1
  const next = num === 12 ? 1 : num + 1
  return [code, `${prev}${letter}`, `${next}${letter}`, `${num}${opposite}`]
}

interface Props {
  activeCode?: string | null
  size?: number
}

export default function CamelotWheel({ activeCode, size = 220 }: Props) {
  const cx = size / 2
  const cy = size / 2
  const outerR = size * 0.46
  const innerR = size * 0.26
  const compatible = getCompatible(activeCode || '')

  const renderSlices = (isOuter: boolean) => {
    const keys = isOuter
      ? KEYS.filter(k => k.code.endsWith('B'))
      : KEYS.filter(k => k.code.endsWith('A'))

    return keys.map((key, i) => {
      const angle = (i / 12) * Math.PI * 2 - Math.PI / 2
      const nextAngle = ((i + 1) / 12) * Math.PI * 2 - Math.PI / 2
      const r1 = isOuter ? outerR : innerR
      const r2 = isOuter ? outerR * 0.72 : innerR * 0.55
      const midAngle = (angle + nextAngle) / 2

      const x1 = cx + r1 * Math.cos(angle)
      const y1 = cy + r1 * Math.sin(angle)
      const x2 = cx + r1 * Math.cos(nextAngle)
      const y2 = cy + r1 * Math.sin(nextAngle)
      const x3 = cx + r2 * Math.cos(nextAngle)
      const y3 = cy + r2 * Math.sin(nextAngle)
      const x4 = cx + r2 * Math.cos(angle)
      const y4 = cy + r2 * Math.sin(angle)

      const isActive = key.code === activeCode
      const isCompat = compatible.includes(key.code)

      const fill = isActive
        ? (isOuter ? '#1a9e8f' : '#e8305a')
        : isCompat
          ? (isOuter ? 'rgba(15,212,184,0.2)' : 'rgba(232,48,90,0.2)')
          : 'rgba(255,255,255,0.03)'

      const stroke = isActive
        ? (isOuter ? '#0fd4b8' : '#e8305a')
        : 'rgba(255,255,255,0.08)'

      const labelR = (r1 + r2) / 2
      const lx = cx + labelR * Math.cos(midAngle)
      const ly = cy + labelR * Math.sin(midAngle)

      return (
        <g key={key.code}>
          <path
            d={`M ${x1} ${y1} A ${r1} ${r1} 0 0 1 ${x2} ${y2} L ${x3} ${y3} A ${r2} ${r2} 0 0 0 ${x4} ${y4} Z`}
            fill={fill}
            stroke={stroke}
            strokeWidth={isActive ? 1.5 : 0.5}
            style={{ transition: 'fill 0.3s ease, stroke 0.3s ease' }}
          />
          <text
            x={lx} y={ly}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize={size * 0.042}
            fill={isActive ? '#fff' : isCompat ? 'rgba(255,255,255,0.8)' : 'rgba(255,255,255,0.25)'}
            fontFamily="'Share Tech Mono', monospace"
            style={{ transition: 'fill 0.3s ease' }}
          >
            {key.code}
          </text>
        </g>
      )
    })
  }

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {/* Center glow */}
      <circle cx={cx} cy={cy} r={innerR * 0.5} fill="rgba(15,212,184,0.05)" />
      <circle cx={cx} cy={cy} r={innerR * 0.5} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth={0.5} />

      {renderSlices(false)}
      {renderSlices(true)}

      {/* Active code center label */}
      {activeCode && (
        <text
          x={cx} y={cy}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize={size * 0.072}
          fontFamily="'Share Tech Mono', monospace"
          fill="#0fd4b8"
          style={{ textShadow: '0 0 12px #0fd4b8' }}
        >
          {activeCode}
        </text>
      )}
    </svg>
  )
}
