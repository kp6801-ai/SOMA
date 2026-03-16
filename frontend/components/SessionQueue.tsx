'use client'

import { SessionTrack } from '@/lib/api'

interface Props {
  tracks: SessionTrack[]
  currentPosition: number
}

export default function SessionQueue({ tracks, currentPosition }: Props) {
  const upcoming = tracks.filter(t => t.position > currentPosition).slice(0, 5)

  return (
    <div>
      <p className="label-dim" style={{ marginBottom: 14 }}>Up Next</p>

      {upcoming.length === 0 && (
        <p className="label-dim" style={{ opacity: 0.35, padding: '8px 0' }}>End of session</p>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {upcoming.map((t, i) => (
          <div
            key={t.position}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '10px 14px',
              borderRadius: 14,
              background: 'rgba(255,255,255,0.025)',
              border: '1px solid rgba(255,255,255,0.055)',
              opacity: Math.max(0.3, 1 - i * 0.16),
              transition: 'opacity 0.3s ease',
            }}
          >
            {/* Position */}
            <span
              className="dot-matrix"
              style={{ fontSize: 10, color: 'rgba(255,255,255,0.22)', minWidth: 22, flexShrink: 0 }}
            >
              {String(t.position).padStart(2, '0')}
            </span>

            {/* Track info */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{
                fontSize: 12,
                fontWeight: 300,
                color: 'rgba(255,255,255,0.72)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                marginBottom: 2,
                fontFamily: 'DM Sans',
              }}>
                {t.title}
              </p>
              <p className="label-dim" style={{
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}>
                {t.artist}
              </p>
            </div>

            {/* BPM */}
            <div style={{ textAlign: 'right', flexShrink: 0 }}>
              <span className="dot-matrix" style={{ fontSize: 12, color: 'rgba(232,48,90,0.7)' }}>
                {Math.round(t.target_bpm)}
              </span>
              <p className="label-dim" style={{ fontSize: 8, marginTop: 1 }}>bpm</p>
            </div>

            {/* Camelot key badge */}
            {t.camelot && t.camelot !== 'Unknown' && (
              <span style={{
                fontFamily: 'Share Tech Mono, monospace',
                fontSize: 9,
                padding: '3px 8px',
                borderRadius: 8,
                background: 'rgba(15,212,184,0.08)',
                border: '1px solid rgba(15,212,184,0.18)',
                color: '#0fd4b8',
                flexShrink: 0,
              }}>
                {t.camelot}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
