'use client'

import { SessionTrack } from '@/lib/api'

interface Props {
  tracks: SessionTrack[]
  currentPosition: number
}

export default function SessionQueue({ tracks, currentPosition }: Props) {
  const upcoming = tracks.filter(t => t.position > currentPosition).slice(0, 5)

  return (
    <div className="flex flex-col gap-2">
      <span className="label-dim mb-1">Up next</span>
      {upcoming.length === 0 && (
        <p className="label-dim" style={{ opacity: 0.35 }}>End of session</p>
      )}
      {upcoming.map((t, i) => (
        <div
          key={t.position}
          className="flex items-center gap-3 px-4 py-3 rounded-2xl"
          style={{
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.06)',
            opacity: 1 - i * 0.15,
            transition: 'opacity 0.3s ease',
          }}
        >
          {/* Position number */}
          <span className="dot-matrix text-xs" style={{ color: 'rgba(255,255,255,0.25)', minWidth: 20 }}>
            {String(t.position).padStart(2, '0')}
          </span>

          {/* Track info */}
          <div className="flex-1 min-w-0">
            <p className="text-sm font-light truncate" style={{ color: 'rgba(255,255,255,0.75)' }}>
              {t.title}
            </p>
            <p className="label-dim truncate">{t.artist}</p>
          </div>

          {/* BPM */}
          <div className="text-right shrink-0">
            <span className="dot-matrix text-sm dot-matrix-glow-bpm">
              {Math.round(t.target_bpm)}
            </span>
            <p className="label-dim">bpm</p>
          </div>

          {/* Camelot */}
          {t.camelot && t.camelot !== 'Unknown' && (
            <span
              className="dot-matrix text-xs px-2 py-1 rounded-lg"
              style={{ background: 'rgba(15,212,184,0.08)', color: '#0fd4b8' }}
            >
              {t.camelot}
            </span>
          )}
        </div>
      ))}
    </div>
  )
}
