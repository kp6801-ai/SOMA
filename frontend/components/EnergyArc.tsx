'use client'

import { useEffect, useRef } from 'react'
import { SessionTrack } from '@/lib/api'

interface Props {
  tracks: SessionTrack[]
  currentPosition: number
}

export default function EnergyArc({ tracks, currentPosition }: Props) {
  const svgRef = useRef<SVGPolylineElement>(null)

  const W = 600
  const H = 80
  const pad = 24

  const points = tracks.map((t, i) => {
    const x = pad + (i / Math.max(tracks.length - 1, 1)) * (W - pad * 2)
    // Normalize BPM: typical range 60–180 → flip for visual (higher = higher on screen)
    const minBpm = Math.min(...tracks.map(t => t.target_bpm))
    const maxBpm = Math.max(...tracks.map(t => t.target_bpm))
    const range = maxBpm - minBpm || 1
    const y = H - pad - ((t.target_bpm - minBpm) / range) * (H - pad * 2)
    return `${x},${y}`
  })

  const polylinePoints = points.join(' ')

  useEffect(() => {
    if (svgRef.current) {
      svgRef.current.style.strokeDashoffset = '1000'
      svgRef.current.getBoundingClientRect()
      svgRef.current.style.transition = 'stroke-dashoffset 1.2s ease'
      svgRef.current.style.strokeDashoffset = '0'
    }
  }, [tracks])

  if (!tracks.length) return null

  return (
    <div className="w-full">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        className="w-full"
        style={{ height: 80 }}
      >
        <defs>
          <linearGradient id="arcGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#2244cc" />
            <stop offset="50%" stopColor="#e8305a" />
            <stop offset="100%" stopColor="#c0195e" />
          </linearGradient>
          <filter id="waveGlow">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        {/* BPM gridlines */}
        {[0.25, 0.5, 0.75].map(frac => (
          <line
            key={frac}
            x1={pad} y1={pad + frac * (H - pad * 2)}
            x2={W - pad} y2={pad + frac * (H - pad * 2)}
            stroke="rgba(255,255,255,0.04)" strokeWidth={1}
          />
        ))}

        {/* Waveform line */}
        <polyline
          ref={svgRef}
          points={polylinePoints}
          stroke="url(#arcGrad)"
          strokeWidth={1.5}
          fill="none"
          strokeDasharray="1000"
          strokeDashoffset="1000"
          filter="url(#waveGlow)"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Track dots */}
        {tracks.map((t, i) => {
          const [x, y] = points[i].split(',').map(Number)
          const isCurrent = t.position === currentPosition
          const isPast = t.position < currentPosition
          return (
            <circle
              key={t.position}
              cx={x} cy={y} r={isCurrent ? 5 : 3}
              fill={isCurrent ? '#e8305a' : isPast ? 'rgba(255,255,255,0.4)' : 'rgba(255,255,255,0.15)'}
              stroke={isCurrent ? '#e8305a' : 'none'}
              strokeWidth={isCurrent ? 2 : 0}
              style={{
                filter: isCurrent ? 'drop-shadow(0 0 6px #e8305a)' : 'none',
                transition: 'fill 0.3s ease',
              }}
            />
          )
        })}
      </svg>
    </div>
  )
}
