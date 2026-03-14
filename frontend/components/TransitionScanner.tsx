'use client'

interface Props {
  scanning: boolean
  label?: string
}

export default function TransitionScanner({ scanning, label }: Props) {
  const size = 96
  const cx = size / 2
  const r = size * 0.42

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Static outer ring */}
        <circle cx={cx} cy={cx} r={r}
          fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={1} />

        {/* Dashed scanning ring */}
        <circle
          cx={cx} cy={cx} r={r}
          fill="none"
          stroke={scanning ? '#4488ff' : 'rgba(68,136,255,0.3)'}
          strokeWidth={1.5}
          strokeDasharray="8 6"
          strokeLinecap="round"
          className={scanning ? 'scanner-ring' : ''}
          style={{ filter: scanning ? 'drop-shadow(0 0 4px #4488ff)' : 'none' }}
        />

        {/* Inner pulse dot */}
        <circle
          cx={cx} cy={cx} r={4}
          fill={scanning ? '#4488ff' : 'rgba(68,136,255,0.3)'}
          className={scanning ? 'pulse-ring' : ''}
        />
      </svg>
      {label && <span className="label-dim">{label}</span>}
    </div>
  )
}
