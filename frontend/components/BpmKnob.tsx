'use client'

import { useEffect, useRef, useState } from 'react'

interface Props {
  bpm: number
  targetBpm: number
  color: string
}

const MIN_BPM = 60
const MAX_BPM = 200
const BPM_RANGE = MAX_BPM - MIN_BPM

// Arc goes from 225° to 315° clockwise (270° total sweep)
// In SVG angles: 0° = 3 o'clock, clockwise positive
const START_ANGLE_DEG = 225
const END_ANGLE_DEG = 315 // wraps past 360, i.e. 315° = 360-45
const SWEEP_DEG = 270

const SIZE = 120
const CENTER = SIZE / 2
const OUTER_RADIUS = 50
const INNER_RADIUS = 44

function degToRad(deg: number) {
  return (deg * Math.PI) / 180
}

// Convert a BPM value to its angle along the arc (in degrees, SVG convention)
function bpmToAngleDeg(bpm: number): number {
  const pct = Math.min(1, Math.max(0, (bpm - MIN_BPM) / BPM_RANGE))
  return START_ANGLE_DEG + pct * SWEEP_DEG
}

// Convert polar (angle in degrees, radius) to SVG x,y coordinates
function polarToXY(angleDeg: number, radius: number): { x: number; y: number } {
  const rad = degToRad(angleDeg)
  return {
    x: CENTER + radius * Math.cos(rad),
    y: CENTER + radius * Math.sin(rad),
  }
}

// Build an SVG arc path between two angles at a given radius
function arcPath(
  startDeg: number,
  endDeg: number,
  radius: number,
  largeArc: boolean
): string {
  const start = polarToXY(startDeg, radius)
  const end = polarToXY(endDeg, radius)
  return `M ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArc ? 1 : 0} 1 ${end.x} ${end.y}`
}

// Circumference of the arc track for strokeDasharray animation
const TRACK_CIRCUMFERENCE = 2 * Math.PI * INNER_RADIUS
const ARC_FRACTION = SWEEP_DEG / 360

export default function BpmKnob({ bpm, targetBpm, color }: Props) {
  const prevBpmRef = useRef(bpm)
  const [displayBpm, setDisplayBpm] = useState(bpm)

  // Smooth BPM number display (counts up/down)
  useEffect(() => {
    const start = prevBpmRef.current
    const end = bpm
    if (start === end) return

    const duration = 400 // ms
    const startTime = performance.now()

    let raf: number
    function step(now: number) {
      const elapsed = now - startTime
      const t = Math.min(elapsed / duration, 1)
      // ease-out cubic
      const eased = 1 - Math.pow(1 - t, 3)
      setDisplayBpm(Math.round(start + (end - start) * eased))
      if (t < 1) {
        raf = requestAnimationFrame(step)
      } else {
        prevBpmRef.current = end
      }
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [bpm])

  // Current BPM arc fill — use strokeDashoffset technique on the full circle
  const bpmPct = Math.min(1, Math.max(0, (bpm - MIN_BPM) / BPM_RANGE))
  const filledLength = bpmPct * ARC_FRACTION * TRACK_CIRCUMFERENCE
  const dashArray = `${filledLength} ${TRACK_CIRCUMFERENCE}`
  // Rotate so the dash starts at START_ANGLE_DEG
  const rotateOffset = START_ANGLE_DEG - 90 // SVG stroke starts at top (270° = -90°)

  // Target BPM dot position
  const targetAngle = bpmToAngleDeg(targetBpm)
  const targetDot = polarToXY(targetAngle, INNER_RADIUS)

  // Outer track arc path (full 270° sweep)
  const trackLargeArc = SWEEP_DEG > 180
  const trackPath = arcPath(START_ANGLE_DEG, START_ANGLE_DEG + SWEEP_DEG, OUTER_RADIUS, trackLargeArc)

  // Unique filter id per instance (avoid collisions if multiple knobs rendered)
  const filterId = `knob-glow-${color.replace(/[^a-z0-9]/gi, '')}`

  return (
    <div
      style={{
        width: SIZE,
        height: SIZE,
        position: 'relative',
        flexShrink: 0,
      }}
    >
      <svg
        width={SIZE}
        height={SIZE}
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        style={{ display: 'block' }}
      >
        <defs>
          <filter id={filterId} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Background circle */}
        <circle
          cx={CENTER}
          cy={CENTER}
          r={OUTER_RADIUS + 4}
          fill="rgba(0,0,0,0.35)"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth="1"
        />

        {/* Outer track ring (full 270° sweep, dimmed) */}
        <path
          d={trackPath}
          fill="none"
          stroke="rgba(255,255,255,0.10)"
          strokeWidth="3"
          strokeLinecap="round"
        />

        {/* Active arc fill using strokeDashoffset on a full circle, rotated */}
        <circle
          cx={CENTER}
          cy={CENTER}
          r={INNER_RADIUS}
          fill="none"
          stroke={color}
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={dashArray}
          strokeDashoffset="0"
          transform={`rotate(${rotateOffset} ${CENTER} ${CENTER})`}
          filter={`url(#${filterId})`}
          style={{
            transition: 'stroke-dasharray 0.35s cubic-bezier(0.4, 0, 0.2, 1)',
          }}
        />

        {/* Target BPM dot marker */}
        <circle
          cx={targetDot.x}
          cy={targetDot.y}
          r={3}
          fill={color}
          opacity={0.45}
        />

        {/* Inner knob face */}
        <circle
          cx={CENTER}
          cy={CENTER}
          r={34}
          fill="rgba(18,18,24,0.9)"
          stroke="rgba(255,255,255,0.05)"
          strokeWidth="1"
        />

        {/* BPM number */}
        <text
          x={CENTER}
          y={CENTER + 5}
          textAnchor="middle"
          dominantBaseline="middle"
          fontFamily="'Share Tech Mono', 'Courier New', monospace"
          fontSize="18"
          fontWeight="600"
          fill="rgba(255,255,255,0.92)"
          letterSpacing="0.5"
          style={{ transition: 'fill 0.2s' }}
        >
          {displayBpm}
        </text>

        {/* BPM label */}
        <text
          x={CENTER}
          y={CENTER + 20}
          textAnchor="middle"
          dominantBaseline="middle"
          fontFamily="'Share Tech Mono', 'Courier New', monospace"
          fontSize="8"
          fill="rgba(255,255,255,0.35)"
          letterSpacing="2"
        >
          BPM
        </text>
      </svg>
    </div>
  )
}
