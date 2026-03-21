'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { api, ArcType, Session, NowPlaying, SessionTrack } from '@/lib/api'
import AudioPlayer from '@/components/AudioPlayer'
import FrequencyVisualizer from '@/components/FrequencyVisualizer'
import BpmKnob from '@/components/BpmKnob'

/* ─── Types ─────────────────────────────────────────────────── */
type Tab = 'discover' | 'laboratory' | 'journey' | 'library'

/* ─── Arc shape data for waveform previews ──────────────────── */
const ARC_SHAPES: Record<string, number[]> = {
  peak_hour:  [0.35, 0.48, 0.62, 0.75, 0.88, 0.97, 1.00, 1.00, 1.00, 0.92],
  workout:    [0.25, 0.45, 0.70, 0.90, 1.00, 1.00, 0.90, 0.75, 0.55, 0.35],
  deep_focus: [0.25, 0.32, 0.42, 0.56, 0.68, 0.80, 0.88, 0.90, 0.90, 0.90],
  sleep:      [0.75, 0.66, 0.56, 0.46, 0.37, 0.30, 0.24, 0.20, 0.17, 0.15],
  meditate:   [0.28, 0.30, 0.25, 0.32, 0.27, 0.31, 0.25, 0.32, 0.27, 0.30],
  recovery:   [0.65, 0.58, 0.51, 0.45, 0.40, 0.35, 0.31, 0.29, 0.27, 0.26],
  hiit:       [0.28, 0.95, 0.28, 0.95, 0.28, 0.95, 0.28, 0.95, 0.28, 0.95],
}

/* ─── Inline shared styles ──────────────────────────────────── */
const S = {
  labelDim: {
    fontFamily: 'Inter',
    fontSize: 9,
    fontWeight: 700 as const,
    letterSpacing: '0.18em',
    textTransform: 'uppercase' as const,
    color: '#adaaaa',
  },
  headline: {
    fontFamily: 'Space Grotesk',
    fontWeight: 700 as const,
    textTransform: 'uppercase' as const,
    letterSpacing: '-0.02em',
  },
  mono: {
    fontFamily: 'Inter',
    fontVariantNumeric: 'tabular-nums' as const,
    fontWeight: 700 as const,
  },
}

/* ─── WaveformBars ──────────────────────────────────────────── */
function WaveformBars({ arcKey, active }: { arcKey: string; active: boolean }) {
  const pts = ARC_SHAPES[arcKey] || Array(10).fill(0.5)
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: '2px', height: 24, width: 56, flexShrink: 0 }}>
      {pts.map((v, i) => (
        <div key={i} style={{
          flex: 1,
          height: `${Math.max(8, v * 100)}%`,
          background: active ? '#cafd00' : 'rgba(255,255,255,0.15)',
          boxShadow: active && v >= 0.9 ? '0 0 8px rgba(202,253,0,0.65)' : 'none',
          transition: 'background 0.22s ease',
        }} />
      ))}
    </div>
  )
}

/* ─── BPM Journey Chart ─────────────────────────────────────── */
function BpmJourneyChart({ tracks, currentPosition }: { tracks: SessionTrack[]; currentPosition: number }) {
  if (!tracks.length) return null

  const W = 1000, H = 280
  const padL = 52, padR = 16, padT = 24, padB = 44
  const iW = W - padL - padR
  const iH = H - padT - padB

  const bpms = tracks.map(t => t.target_bpm)
  const minB = Math.min(...bpms) - 3
  const maxB = Math.max(...bpms) + 3
  const rangeB = maxB - minB || 10

  const tx = (i: number) => padL + (i / Math.max(tracks.length - 1, 1)) * iW
  const ty = (b: number) => padT + iH - ((b - minB) / rangeB) * iH

  const pts = tracks.map((t, i) => [tx(i), ty(t.target_bpm)] as [number, number])
  const lineD = `M ${pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' L ')}`
  const fillD = `${lineD} L ${pts[pts.length - 1][0].toFixed(1)},${(padT + iH).toFixed(1)} L ${pts[0][0].toFixed(1)},${(padT + iH).toFixed(1)} Z`

  const cpIdx = Math.min(Math.max(currentPosition - 1, 0), tracks.length - 1)
  const cpX = tx(cpIdx)
  const cpBpm = tracks[cpIdx]?.target_bpm ?? (minB + rangeB / 2)
  const cpY = ty(cpBpm)

  // Y-axis grid values
  const step = Math.max(5, Math.ceil(rangeB / 5 / 5) * 5)
  const gridVals: number[] = []
  for (let v = Math.ceil(minB / step) * step; v <= maxB; v += step) gridVals.push(v)

  // X-axis time labels
  const xLabels = [0, Math.floor(tracks.length / 2), tracks.length - 1].filter((v, i, a) => a.indexOf(v) === i)

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: '100%', height: 280, display: 'block' }}>
      <defs>
        <linearGradient id="jFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#00eefc" stopOpacity="0.18" />
          <stop offset="100%" stopColor="#000000" stopOpacity="0" />
        </linearGradient>
        <filter id="jGlow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="3" result="b" />
          <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <filter id="phGlow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="5" result="b" />
          <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      {/* Grid lines + Y labels */}
      {gridVals.map(v => (
        <g key={v}>
          <line x1={padL} y1={ty(v)} x2={W - padR} y2={ty(v)} stroke="rgba(255,255,255,0.04)" strokeWidth={1} />
          <text x={padL - 7} y={ty(v)} textAnchor="end" dominantBaseline="middle"
            fontSize={9} fill="rgba(255,255,255,0.22)" fontFamily="Inter" fontWeight="700">{v}</text>
        </g>
      ))}

      {/* Axes */}
      <line x1={padL} y1={padT} x2={padL} y2={padT + iH} stroke="rgba(255,255,255,0.06)" strokeWidth={1} />
      <line x1={padL} y1={padT + iH} x2={W - padR} y2={padT + iH} stroke="rgba(255,255,255,0.06)" strokeWidth={1} />

      {/* Energy fill */}
      <path d={fillD} fill="url(#jFill)" />

      {/* Dashed energy arc (cyan) */}
      <path d={lineD} fill="none" stroke="#00eefc" strokeWidth={1.5} strokeDasharray="6,4" opacity={0.45} />

      {/* BPM line (lime) */}
      <path d={lineD} fill="none" stroke="#cafd00" strokeWidth={3}
        strokeLinecap="round" strokeLinejoin="round" filter="url(#jGlow)" />

      {/* Track dots */}
      {tracks.map((t, i) => {
        const past = t.position < currentPosition
        const cur = t.position === currentPosition
        return (
          <circle key={i} cx={tx(i)} cy={ty(t.target_bpm)} r={cur ? 5 : 3}
            fill={cur ? '#cafd00' : past ? 'rgba(202,253,0,0.5)' : 'rgba(255,255,255,0.18)'}
            filter={cur ? 'url(#phGlow)' : 'none'} />
        )
      })}

      {/* Playhead */}
      {tracks.length > 0 && (
        <g>
          <line x1={cpX} y1={padT} x2={cpX} y2={padT + iH}
            stroke="rgba(202,253,0,0.8)" strokeWidth={2} filter="url(#phGlow)" />
          <circle cx={cpX} cy={cpY} r={5} fill="#cafd00" filter="url(#phGlow)" />
          <rect x={cpX - 34} y={padT + iH + 5} width={68} height={16} rx={2} fill="#1a1919" />
          <text x={cpX} y={padT + iH + 15} textAnchor="middle" fontSize={8} fill="#cafd00"
            fontFamily="Inter" fontWeight="700" letterSpacing="0.5">
            {currentPosition}/{tracks.length} • {Math.round(cpBpm)} BPM
          </text>
        </g>
      )}

      {/* X-axis labels */}
      {xLabels.map(i => (
        <text key={i} x={tx(i)} y={padT + iH + 36} textAnchor="middle"
          fontSize={9} fill="rgba(255,255,255,0.22)" fontFamily="Inter" fontWeight="700">
          {i === 0 ? '00:00' : i === tracks.length - 1 ? `${Math.round(i * 4 / 60)}:00` : `${Math.round(i * 2 / 60)}:00`}
        </text>
      ))}
    </svg>
  )
}

/* ─── Error Banner ──────────────────────────────────────────── */
function ErrorBanner({ msg }: { msg: string }) {
  return (
    <div style={{
      padding: '12px 16px', marginBottom: 16,
      background: 'rgba(181,41,2,0.12)', borderLeft: '3px solid #d53d18',
    }}>
      <p style={{ fontSize: 11, color: '#ff7351', fontFamily: 'Inter', lineHeight: 1.5 }}>{msg}</p>
    </div>
  )
}

/* ─── Desktop Top Bar ───────────────────────────────────────── */
function TopBar({ tab, setTab, hasSession }: { tab: Tab; setTab: (t: Tab) => void; hasSession: boolean }) {
  const navItems: { id: Tab; label: string; icon: string }[] = [
    { id: 'discover', label: 'Discover', icon: 'explore' },
    { id: 'laboratory', label: 'Laboratory', icon: 'science' },
    { id: 'journey', label: 'Journey', icon: 'show_chart' },
    { id: 'library', label: 'Library', icon: 'library_music' },
  ]
  return (
    <header style={{
      position: 'fixed', top: 0, left: 0, right: 0, zIndex: 50,
      background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(20px)',
      WebkitBackdropFilter: 'blur(20px)',
      borderBottom: '1px solid rgba(243,255,202,0.08)',
      boxShadow: '0 4px 30px rgba(0,0,0,0.5)',
      display: 'none',
    }} className="md-topbar">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 24px', height: 64 }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span className="material-symbols-outlined" style={{ color: '#f3ffca', fontSize: 22 }}>sensors</span>
          <span style={{ ...S.headline, fontSize: 22, color: '#f3ffca', letterSpacing: '0.05em' }}>SOMA</span>
        </div>

        {/* Nav */}
        <nav style={{ display: 'flex', gap: 36 }}>
          {navItems.map(item => (
            <button key={item.id} onClick={() => setTab(item.id)} style={{
              background: 'none', border: 'none', cursor: 'pointer',
              fontFamily: 'Inter', fontSize: 10, fontWeight: 700,
              textTransform: 'uppercase', letterSpacing: '0.2em',
              color: tab === item.id ? '#f3ffca' : '#adaaaa',
              filter: tab === item.id ? 'drop-shadow(0 0 8px rgba(243,255,202,0.5))' : 'none',
              transition: 'color 0.18s ease',
              opacity: item.id === 'journey' && !hasSession ? 0.4 : 1,
            }}>
              {item.label}
            </button>
          ))}
        </nav>

        {/* Session indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {hasSession && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#cafd00', animation: 'pulse-glow 1.5s ease-in-out infinite', display: 'inline-block' }} />
              <span style={{ fontSize: 9, fontFamily: 'Inter', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.15em', color: '#cafd00' }}>Live</span>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}

/* ─── Mobile Bottom Nav ─────────────────────────────────────── */
function BottomNav({ tab, setTab, hasSession }: { tab: Tab; setTab: (t: Tab) => void; hasSession: boolean }) {
  const navItems: { id: Tab; label: string; icon: string }[] = [
    { id: 'discover', label: 'Discover', icon: 'explore' },
    { id: 'laboratory', label: 'Laboratory', icon: 'science' },
    { id: 'journey', label: 'Journey', icon: 'show_chart' },
    { id: 'library', label: 'Library', icon: 'library_music' },
  ]
  return (
    <nav style={{
      position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 50,
      height: 72, background: '#121212',
      borderTop: '1px solid rgba(243,255,202,0.08)',
      boxShadow: '0 -8px 30px rgba(0,0,0,0.8)',
      display: 'flex',
    }}>
      {navItems.map(item => {
        const active = tab === item.id
        const disabled = item.id === 'journey' && !hasSession
        return (
          <button key={item.id} onClick={() => !disabled && setTab(item.id)} style={{
            flex: 1, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            gap: 3, background: 'none', border: 'none',
            cursor: disabled ? 'default' : 'pointer',
            color: active ? '#f3ffca' : '#adaaaa',
            filter: active ? 'drop-shadow(0 0 8px rgba(243,255,202,0.55))' : 'none',
            opacity: disabled ? 0.3 : 1,
            transition: 'all 0.15s ease',
          }}>
            <span className="material-symbols-outlined" style={{ fontSize: 22 }}>{item.icon}</span>
            <span style={{ fontFamily: 'Inter', fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.18em' }}>
              {item.label}
            </span>
          </button>
        )
      })}
    </nav>
  )
}

/* ─── DISCOVER VIEW ─────────────────────────────────────────── */
interface DiscoverProps {
  arcTypes: ArcType[]
  selectedArc: string
  setSelectedArc: (k: string) => void
  duration: number
  setDuration: (d: number) => void
  loading: boolean
  error: string | null
  onStart: () => void
}

function DiscoverView({ arcTypes, selectedArc, setSelectedArc, duration, setDuration, loading, error, onStart }: DiscoverProps) {
  return (
    <div style={{ maxWidth: 580, margin: '0 auto', padding: '28px 20px 90px' }}>
      {error && <ErrorBanner msg={error} />}

      {/* Section header */}
      <div style={{ marginBottom: 28 }}>
        <p style={{ ...S.labelDim, marginBottom: 6, color: '#00eefc' }}>Session Configuration</p>
        <h2 style={{ ...S.headline, fontSize: 'clamp(1.8rem, 8vw, 2.8rem)', color: '#ffffff', lineHeight: 1 }}>
          Select Arc <span style={{ color: '#cafd00' }}>Type</span>
        </h2>
      </div>

      {/* Arc type list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3, marginBottom: 32 }}>
        {arcTypes.length === 0 && !error && Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="skeleton" style={{ height: 68, borderRadius: 2 }} />
        ))}

        {arcTypes.map((arc, idx) => {
          const active = selectedArc === arc.key
          return (
            <button
              key={arc.key}
              onClick={() => setSelectedArc(arc.key)}
              className="soma-fade-up"
              style={{
                display: 'flex', alignItems: 'center', gap: 16,
                padding: '14px 18px',
                background: active ? '#131313' : 'transparent',
                border: 'none',
                borderLeft: `3px solid ${active ? '#cafd00' : 'rgba(255,255,255,0.05)'}`,
                cursor: 'pointer', width: '100%', textAlign: 'left',
                transition: 'background 0.18s ease, border-color 0.18s ease',
                animationDelay: `${idx * 40}ms`,
              }}
              onMouseEnter={e => { if (!active) e.currentTarget.style.background = '#0d0d0d' }}
              onMouseLeave={e => { if (!active) e.currentTarget.style.background = 'transparent' }}
            >
              <WaveformBars arcKey={arc.key} active={active} />

              <div style={{ flex: 1, minWidth: 0 }}>
                <span style={{
                  ...S.headline, fontSize: 13,
                  color: active ? '#ffffff' : '#adaaaa',
                  display: 'block', marginBottom: 3,
                  transition: 'color 0.18s ease',
                }}>
                  {arc.label}
                </span>
                <p style={{
                  fontSize: 10, color: 'rgba(255,255,255,0.28)',
                  fontFamily: 'Inter', fontWeight: 400,
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {arc.description}
                </p>
              </div>

              <div style={{ textAlign: 'right', flexShrink: 0 }}>
                <span style={{ ...S.mono, fontSize: 11, color: active ? '#00eefc' : '#494847' }}>
                  {arc.bpm_start}–{arc.bpm_peak}
                </span>
                <p style={{ ...S.labelDim, fontSize: 8, marginTop: 2 }}>bpm</p>
              </div>
            </button>
          )
        })}
      </div>

      {/* Duration slider */}
      <div style={{ marginBottom: 32, padding: '0 0' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 14 }}>
          <p style={S.labelDim}>Duration</p>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 5 }}>
            <span style={{ ...S.mono, fontFamily: 'Space Grotesk', fontSize: 28, color: '#cafd00', textShadow: '0 0 16px rgba(202,253,0,0.35)' }}>
              {duration}
            </span>
            <span style={S.labelDim}>min</span>
          </div>
        </div>
        <input type="range" min={15} max={180} step={15} value={duration}
          onChange={e => setDuration(Number(e.target.value))} />
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 7 }}>
          <span style={{ ...S.labelDim, fontSize: 8 }}>15 min</span>
          <span style={{ ...S.labelDim, fontSize: 8 }}>3 hr</span>
        </div>
      </div>

      {/* Divider */}
      <div style={{ height: 1, background: 'rgba(255,255,255,0.05)', marginBottom: 28 }} />

      {/* Start CTA */}
      <button
        onClick={onStart}
        disabled={loading || !selectedArc}
        style={{
          width: '100%', padding: '20px',
          background: loading ? 'rgba(255,255,255,0.04)' : '#cafd00',
          color: loading ? 'rgba(255,255,255,0.25)' : '#3a4a00',
          fontFamily: 'Space Grotesk', fontWeight: 700, fontSize: 11,
          letterSpacing: '0.3em', textTransform: 'uppercase',
          border: 'none', borderRadius: 2,
          boxShadow: loading ? 'none' : '0 0 40px rgba(202,253,0,0.22), 0 4px 24px rgba(0,0,0,0.3)',
          cursor: loading ? 'not-allowed' : 'pointer',
          opacity: loading ? 0.55 : 1,
          transition: 'all 0.22s ease',
        }}
        onMouseEnter={e => { if (!loading && selectedArc) e.currentTarget.style.background = '#beee00' }}
        onMouseLeave={e => { if (!loading && selectedArc) e.currentTarget.style.background = '#cafd00' }}
      >
        {loading ? 'Initializing Session…' : 'Start Session'}
      </button>
    </div>
  )
}

/* ─── JOURNEY VIEW ──────────────────────────────────────────── */
interface JourneyProps {
  session: Session | null
  nowPlaying: NowPlaying | null
  scanning: boolean
  done: boolean
  error: string | null
  isPlaying: boolean
  hoverRating: number
  setHoverRating: (r: number) => void
  audioRef: React.RefObject<HTMLAudioElement | null>
  onSetIsPlaying: (v: boolean) => void
  onEvent: (event: 'completed' | 'skipped', rating?: number) => void
  onNewSession: () => void
}

function JourneyView({ session, nowPlaying, scanning, done, error, isPlaying, hoverRating, setHoverRating, audioRef, onSetIsPlaying, onEvent, onNewSession }: JourneyProps) {
  if (!session) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '65vh', gap: 16, padding: 24 }}>
        <span className="material-symbols-outlined" style={{ fontSize: 56, color: '#262626' }}>show_chart</span>
        <p style={{ ...S.headline, fontSize: 13, color: '#adaaaa', letterSpacing: '0.2em' }}>No Active Session</p>
        <p style={{ fontSize: 11, color: '#494847', textAlign: 'center', fontFamily: 'Inter' }}>
          Start a session from Discover to visualize your journey
        </p>
      </div>
    )
  }

  const currentPosition = nowPlaying?.position ?? 0
  const totalTracks = session.total_tracks
  const progressPct = totalTracks > 0 ? (currentPosition / totalTracks) * 100 : 0
  const avgBpm = session.tracks.length
    ? Math.round(session.tracks.reduce((s, t) => s + t.target_bpm, 0) / session.tracks.length)
    : 0

  return (
    <div style={{ padding: '16px 12px 88px', maxWidth: 1100, margin: '0 auto' }}>
      {error && <ErrorBanner msg={error} />}

      {/* Session header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <p style={{ ...S.labelDim, color: '#00eefc', marginBottom: 5 }}>Live Session Visualizer</p>
          <h2 style={{ ...S.headline, fontSize: 'clamp(1.4rem, 5vw, 2.2rem)', color: '#ffffff', lineHeight: 1 }}>
            {session.arc_label} <span style={{ color: '#cafd00' }}>Journey</span>
          </h2>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <div style={{ background: '#131313', padding: '8px 14px', borderLeft: '2px solid #00eefc' }}>
            <p style={{ ...S.labelDim, marginBottom: 3 }}>Avg BPM</p>
            <p style={{ ...S.mono, fontFamily: 'Space Grotesk', fontSize: 18, color: '#00eefc' }}>{avgBpm}</p>
          </div>
          <div style={{ background: '#131313', padding: '8px 14px', borderLeft: '2px solid #cafd00' }}>
            <p style={{ ...S.labelDim, marginBottom: 3 }}>Progress</p>
            <p style={{ ...S.mono, fontFamily: 'Space Grotesk', fontSize: 18, color: '#cafd00' }}>{Math.round(progressPct)}%</p>
          </div>
        </div>
      </div>

      {/* BPM Arc chart */}
      <div style={{ background: '#131313', padding: '18px 14px 10px', marginBottom: 14 }}>
        <div style={{ display: 'flex', gap: 20, marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 14, height: 2, background: '#cafd00', boxShadow: '0 0 8px rgba(202,253,0,0.8)' }} />
            <span style={S.labelDim}>BPM Curve</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 14, height: 0, borderTop: '2px dashed #00eefc' }} />
            <span style={S.labelDim}>Energy Arc</span>
          </div>
        </div>
        <BpmJourneyChart tracks={session.tracks} currentPosition={currentPosition} />
      </div>

      {/* 2-col grid: Now Playing + Sidebar */}
      <div className="journey-grid">

        {/* ── Now Playing Card ── */}
        <div style={{ background: '#131313', padding: 22 }}>
          {done ? (
            <div className="soma-fade-up" style={{ textAlign: 'center', padding: '48px 0' }}>
              <p style={{ ...S.headline, fontSize: 20, color: '#cafd00', letterSpacing: '0.2em', marginBottom: 8 }}>
                Session Complete
              </p>
              <p style={{ fontSize: 12, color: '#adaaaa', marginBottom: 36, fontFamily: 'Inter' }}>Your set has ended.</p>
              <button onClick={onNewSession} style={{
                padding: '12px 36px', background: 'transparent',
                border: '1px solid rgba(202,253,0,0.3)', borderRadius: 2,
                color: '#cafd00', fontFamily: 'Space Grotesk', fontWeight: 700,
                fontSize: 10, letterSpacing: '0.25em', textTransform: 'uppercase',
                cursor: 'pointer', transition: 'background 0.18s ease',
              }}
                onMouseEnter={e => e.currentTarget.style.background = 'rgba(202,253,0,0.07)'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >New Session</button>
            </div>
          ) : scanning && !nowPlaying ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '48px 0', gap: 14 }}>
              <div style={{ width: 44, height: 44, borderRadius: '50%', border: '2px dashed #00eefc', animation: 'spin-slow 3s linear infinite', boxShadow: '0 0 12px rgba(0,238,252,0.25)' }} />
              <span style={{ ...S.labelDim, color: '#adaaaa' }}>Selecting next track</span>
            </div>
          ) : nowPlaying ? (
            <div key={nowPlaying.position} className="soma-track-in">
              {/* Track info + BPM Knob */}
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 18, marginBottom: 18 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ ...S.labelDim, marginBottom: 8 }}>Now Playing</p>
                  <h2 style={{
                    fontFamily: 'Space Grotesk', fontWeight: 700,
                    fontSize: 'clamp(1.3rem, 4vw, 1.9rem)',
                    color: '#ffffff', textTransform: 'uppercase',
                    letterSpacing: '-0.01em', lineHeight: 1.1, marginBottom: 5,
                    overflow: 'hidden', display: '-webkit-box',
                    WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' as const,
                  }}>
                    {nowPlaying.title}
                  </h2>
                  <p style={{ fontSize: 12, color: '#adaaaa', fontFamily: 'Inter', marginBottom: 10 }}>
                    {nowPlaying.artist}
                  </p>
                  {/* Metadata chips */}
                  <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
                    <span style={{ ...S.labelDim, padding: '3px 8px', background: 'rgba(202,253,0,0.07)', borderLeft: '2px solid #cafd00', color: '#cafd00' }}>
                      {Math.round(nowPlaying.target_bpm)} bpm target
                    </span>
                    {nowPlaying.camelot && nowPlaying.camelot !== 'Unknown' && (
                      <span style={{ ...S.labelDim, padding: '3px 8px', background: 'rgba(0,238,252,0.07)', borderLeft: '2px solid #00eefc', color: '#00eefc' }}>
                        {nowPlaying.camelot}
                      </span>
                    )}
                  </div>
                </div>
                <BpmKnob bpm={Math.round(nowPlaying.bpm)} targetBpm={Math.round(nowPlaying.target_bpm)} color="#cafd00" />
              </div>

              {/* Frequency visualizer */}
              <div style={{ padding: '10px 12px', background: 'rgba(0,0,0,0.35)', marginBottom: 16 }}>
                <FrequencyVisualizer audioRef={audioRef} playing={isPlaying} color="#cafd00" />
              </div>

              {/* Audio player */}
              <div style={{ marginBottom: 16 }}>
                <AudioPlayer
                  audioUrl={nowPlaying.audio_url}
                  onEnded={() => onEvent('completed')}
                  audioRef={audioRef}
                  onPlayingChange={onSetIsPlaying}
                  accentColor="#cafd00"
                />
              </div>

              {/* Skip + star rating */}
              <div style={{ display: 'flex', gap: 7, alignItems: 'center' }}>
                <button onClick={() => onEvent('skipped')} style={{
                  padding: '12px 18px', background: 'transparent',
                  border: '1px solid rgba(255,255,255,0.07)', borderRadius: 2,
                  fontSize: 9, letterSpacing: '0.15em', textTransform: 'uppercase',
                  fontFamily: 'Inter', fontWeight: 700, color: '#adaaaa',
                  cursor: 'pointer', flexShrink: 0, transition: 'background 0.15s ease',
                }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >Skip</button>

                <div style={{ display: 'flex', flex: 1, gap: 4 }} onMouseLeave={() => setHoverRating(0)}>
                  {[1, 2, 3, 4, 5].map(r => (
                    <button key={r}
                      onClick={() => onEvent('completed', r)}
                      onMouseEnter={() => setHoverRating(r)}
                      style={{
                        flex: 1, padding: '12px 0', borderRadius: 2,
                        background: r <= hoverRating ? 'rgba(202,253,0,0.12)' : 'rgba(202,253,0,0.04)',
                        border: `1px solid ${r <= hoverRating ? 'rgba(202,253,0,0.4)' : 'rgba(202,253,0,0.09)'}`,
                        cursor: 'pointer', transition: 'all 0.1s ease',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                      }}>
                      <svg width="12" height="12" viewBox="0 0 24 24"
                        fill={r <= hoverRating ? '#cafd00' : 'none'}
                        stroke={r <= hoverRating ? '#cafd00' : 'rgba(255,255,255,0.2)'}
                        strokeWidth="1.5" strokeLinejoin="round">
                        <polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26" />
                      </svg>
                    </button>
                  ))}
                </div>
              </div>

              {scanning && (
                <div style={{ display: 'flex', justifyContent: 'center', marginTop: 14 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 7, color: '#adaaaa' }}>
                    <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#cafd00', display: 'inline-block', animation: 'pulse-glow 1.2s ease-in-out infinite' }} />
                    <span style={S.labelDim}>Loading next track</span>
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </div>

        {/* ── Right sidebar ── */}
        {session && !done && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>

            {/* Transition Preview */}
            <div style={{ background: '#201f1f', padding: '18px 20px' }}>
              <p style={{ ...S.labelDim, marginBottom: 14 }}>Current Transition</p>

              {nowPlaying ? (
                <>
                  {/* Outgoing track */}
                  <div style={{ marginBottom: 10 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 5 }}>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <p style={{ fontSize: 11, fontWeight: 700, color: '#00eefc', textTransform: 'uppercase', fontFamily: 'Space Grotesk', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {nowPlaying.title}
                        </p>
                        <p style={{ fontSize: 10, color: '#adaaaa', fontFamily: 'Inter' }}>{nowPlaying.artist}</p>
                      </div>
                      {nowPlaying.camelot && nowPlaying.camelot !== 'Unknown' && (
                        <span style={{ ...S.labelDim, padding: '2px 6px', background: '#262626', marginLeft: 8, flexShrink: 0 }}>
                          {nowPlaying.camelot}
                        </span>
                      )}
                    </div>
                    <div style={{ height: 20, background: '#131313', display: 'flex', alignItems: 'flex-end', gap: '1px', padding: '2px 4px', opacity: 0.45 }}>
                      {[20, 45, 70, 50, 90, 60, 30, 20].map((h, i) => (
                        <div key={i} style={{ flex: 1, height: `${h}%`, background: '#00eefc' }} />
                      ))}
                    </div>
                  </div>

                  {/* Mix point */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                    <div style={{ flex: 1, height: 1, background: 'linear-gradient(to right, rgba(0,238,252,0.35), #cafd00)' }} />
                    <span className="material-symbols-outlined" style={{ fontSize: 14, color: '#cafd00' }}>sync_alt</span>
                    <div style={{ flex: 1, height: 1, background: 'linear-gradient(to left, rgba(202,253,0,0.35), #cafd00)' }} />
                  </div>

                  {/* Incoming track */}
                  {(() => {
                    const next = session.tracks.find(t => t.position === nowPlaying.position + 1)
                    if (!next) return <p style={{ fontSize: 10, color: '#494847', fontFamily: 'Inter' }}>Last track in session</p>
                    return (
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 5 }}>
                          <div style={{ minWidth: 0, flex: 1 }}>
                            <p style={{ fontSize: 11, fontWeight: 700, color: '#cafd00', textTransform: 'uppercase', fontFamily: 'Space Grotesk', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {next.title}
                            </p>
                            <p style={{ fontSize: 10, color: '#adaaaa', fontFamily: 'Inter' }}>{next.artist}</p>
                          </div>
                          {next.camelot && next.camelot !== 'Unknown' && (
                            <span style={{ ...S.labelDim, padding: '2px 6px', background: 'rgba(202,253,0,0.1)', borderLeft: '1px solid rgba(202,253,0,0.25)', color: '#cafd00', marginLeft: 8, flexShrink: 0 }}>
                              {next.camelot}
                            </span>
                          )}
                        </div>
                        <div style={{ height: 20, background: '#131313', display: 'flex', alignItems: 'flex-end', gap: '1px', padding: '2px 4px' }}>
                          {[10, 30, 20, 55, 85, 100, 65, 40].map((h, i) => (
                            <div key={i} style={{ flex: 1, height: `${h}%`, background: '#cafd00' }} />
                          ))}
                        </div>
                      </div>
                    )
                  })()}

                  {/* Phrase match indicator */}
                  <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid rgba(255,255,255,0.04)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span style={S.labelDim}>Phrase Match</span>
                      <span style={{ ...S.labelDim, color: '#cafd00' }}>Aligned</span>
                    </div>
                    <div style={{ display: 'flex', gap: 3, height: 4 }}>
                      {[1, 1, 1, 0].map((filled, i) => (
                        <div key={i} style={{ flex: 1, background: filled ? '#cafd00' : 'rgba(255,255,255,0.08)', borderRadius: 1 }} />
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                <p style={{ fontSize: 10, color: '#494847', fontFamily: 'Inter' }}>Waiting for first track…</p>
              )}
            </div>

            {/* Set info stat cards */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <div style={{ background: '#131313', padding: '12px 14px', borderLeft: '3px solid #cafd00' }}>
                <p style={{ ...S.labelDim, marginBottom: 5 }}>Active Track</p>
                <p style={{ ...S.headline, fontSize: 16, color: '#ffffff', marginBottom: 2 }}>#{currentPosition}</p>
                <p style={{ fontSize: 10, color: '#adaaaa', fontFamily: 'Inter', fontVariantNumeric: 'tabular-nums' }}>
                  {nowPlaying ? `${Math.round(nowPlaying.target_bpm)} BPM` : '--'}
                </p>
              </div>

              <div style={{ background: '#131313', padding: '12px 14px', opacity: 0.65 }}>
                <p style={{ ...S.labelDim, marginBottom: 5 }}>Upcoming</p>
                {(() => {
                  const next = session.tracks.find(t => t.position === currentPosition + 1)
                  return next ? (
                    <>
                      <p style={{ ...S.headline, fontSize: 16, color: '#adaaaa', marginBottom: 2 }}>#{next.position}</p>
                      <p style={{ fontSize: 10, color: '#494847', fontFamily: 'Inter', fontVariantNumeric: 'tabular-nums' }}>
                        {Math.round(next.target_bpm)} BPM
                      </p>
                    </>
                  ) : <p style={{ fontSize: 10, color: '#494847', fontFamily: 'Inter' }}>End of session</p>
                })()}
              </div>

              <div style={{ background: '#131313', padding: '12px 14px' }}>
                <p style={{ ...S.labelDim, marginBottom: 4 }}>Tracks Played</p>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
                  <span style={{ ...S.mono, fontFamily: 'Space Grotesk', fontSize: 22, color: '#00eefc' }}>{currentPosition}</span>
                  <span style={{ ...S.labelDim, fontSize: 8 }}>/ {totalTracks}</span>
                </div>
              </div>

              <div style={{ background: '#131313', padding: '12px 14px' }}>
                <p style={{ ...S.labelDim, marginBottom: 4 }}>BPM Peak</p>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
                  <span style={{ ...S.mono, fontFamily: 'Space Grotesk', fontSize: 22, color: '#cafd00' }}>{session.bpm_peak}</span>
                  <span style={{ ...S.labelDim, fontSize: 8 }}>target</span>
                </div>
              </div>
            </div>

            {/* Queue */}
            <div style={{ background: '#131313', padding: '16px 18px' }}>
              <p style={{ ...S.labelDim, marginBottom: 12 }}>Up Next</p>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                {session.tracks.filter(t => t.position > currentPosition).slice(0, 6).map((t, i) => (
                  <div key={t.position} style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '9px 0',
                    borderTop: i > 0 ? '1px solid rgba(255,255,255,0.03)' : 'none',
                    opacity: Math.max(0.28, 1 - i * 0.14),
                  }}>
                    <span style={{ ...S.mono, fontSize: 9, color: '#494847', minWidth: 22, flexShrink: 0 }}>
                      {String(t.position).padStart(2, '0')}
                    </span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <p style={{ fontSize: 11, fontWeight: 700, color: '#adaaaa', textTransform: 'uppercase', fontFamily: 'Space Grotesk', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', letterSpacing: '-0.01em' }}>
                        {t.title}
                      </p>
                      <p style={{ fontSize: 9, color: '#494847', fontFamily: 'Inter', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {t.artist}
                      </p>
                    </div>
                    <span style={{ ...S.mono, fontSize: 10, color: '#00eefc', flexShrink: 0 }}>{Math.round(t.target_bpm)}</span>
                    {t.camelot && t.camelot !== 'Unknown' && (
                      <span style={{ ...S.labelDim, fontSize: 8, padding: '2px 5px', background: '#262626', flexShrink: 0 }}>{t.camelot}</span>
                    )}
                  </div>
                ))}
                {session.tracks.filter(t => t.position > currentPosition).length === 0 && (
                  <p style={{ fontSize: 10, color: '#494847', fontFamily: 'Inter', padding: '8px 0' }}>End of session</p>
                )}
              </div>
            </div>

          </div>
        )}
      </div>
    </div>
  )
}

/* ─── LABORATORY VIEW ───────────────────────────────────────── */
interface LaboratoryProps {
  session: Session | null
  nowPlaying: NowPlaying | null
}

function LaboratoryView({ session, nowPlaying }: LaboratoryProps) {
  if (!session) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '65vh', gap: 16, padding: 24 }}>
        <span className="material-symbols-outlined" style={{ fontSize: 56, color: '#262626' }}>science</span>
        <p style={{ ...S.headline, fontSize: 13, color: '#adaaaa', letterSpacing: '0.2em' }}>Laboratory Offline</p>
        <p style={{ fontSize: 11, color: '#494847', textAlign: 'center', fontFamily: 'Inter' }}>
          Start a session to access track intelligence
        </p>
      </div>
    )
  }

  const currentPosition = nowPlaying?.position ?? 0
  const upcoming = session.tracks.filter(t => t.position > currentPosition)

  const arcKey = session.arc_type
  const isRising = arcKey.includes('deep') || arcKey.includes('recovery')
  const isPeak = arcKey.includes('peak') || arcKey.includes('hiit') || arcKey.includes('workout')
  const isValley = arcKey.includes('sleep')
  const isSteady = arcKey.includes('meditate')

  const energyVectors = [
    { icon: 'trending_up', label: 'Rise', active: isRising },
    { icon: 'bolt', label: 'Peak', active: isPeak },
    { icon: 'trending_down', label: 'Valley', active: isValley },
    { icon: 'equalizer', label: 'Steady', active: isSteady },
  ]

  return (
    <div className="lab-grid" style={{ padding: '16px 12px 88px', maxWidth: 1100, margin: '0 auto' }}>

      {/* ── Left: Lab Bench ── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

        {/* Base Node */}
        {nowPlaying ? (
          <div style={{ background: '#201f1f', padding: '18px 20px', position: 'relative', overflow: 'hidden' }}>
            <span style={{ position: 'absolute', top: 14, right: 16, ...S.labelDim, color: '#00eefc' }}>Base Node</span>
            <div style={{ display: 'flex', gap: 16, marginTop: 2 }}>
              <div style={{ width: 88, height: 88, flexShrink: 0, background: '#262626', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <span className="material-symbols-outlined" style={{ fontSize: 32, color: '#494847' }}>music_note</span>
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <h2 style={{ ...S.headline, fontSize: 18, color: '#ffffff', lineHeight: 1.1, marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {nowPlaying.title}
                </h2>
                <p style={{ fontSize: 11, color: '#adaaaa', fontFamily: 'Inter', marginBottom: 10 }}>{nowPlaying.artist}</p>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <div style={{ background: '#262626', padding: '5px 10px', borderLeft: '2px solid #f3ffca' }}>
                    <p style={{ ...S.labelDim, fontSize: 8, marginBottom: 2 }}>BPM</p>
                    <span style={{ ...S.mono, fontFamily: 'Space Grotesk', fontSize: 16 }}>{Math.round(nowPlaying.bpm)}</span>
                  </div>
                  {nowPlaying.camelot && nowPlaying.camelot !== 'Unknown' && (
                    <div style={{ background: '#262626', padding: '5px 10px', borderLeft: '2px solid #00eefc' }}>
                      <p style={{ ...S.labelDim, fontSize: 8, marginBottom: 2 }}>Key</p>
                      <span style={{ ...S.mono, fontFamily: 'Space Grotesk', fontSize: 16, color: '#00eefc' }}>{nowPlaying.camelot}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div style={{ background: '#201f1f', padding: '18px 20px', position: 'relative' }}>
            <span style={{ position: 'absolute', top: 14, right: 16, ...S.labelDim, color: '#00eefc' }}>Base Node</span>
            <p style={{ fontSize: 11, color: '#494847', fontFamily: 'Inter', paddingTop: 4 }}>No track currently playing</p>
          </div>
        )}

        {/* Parameters */}
        <div style={{ background: '#131313', padding: '20px 20px', display: 'flex', flexDirection: 'column', gap: 22 }}>

          {/* BPM Range */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 12 }}>
              <label style={{ ...S.labelDim }}>BPM Range Intelligence</label>
              <span style={{ ...S.mono, fontSize: 12, color: '#00eefc' }}>{session.bpm_start}–{session.bpm_peak}</span>
            </div>
            <div style={{ position: 'relative', height: 4, background: '#262626', borderRadius: 1, marginBottom: 8 }}>
              <div style={{
                position: 'absolute', left: 0, top: 0, height: '100%',
                width: '65%', background: '#00eefc',
                boxShadow: '0 0 10px rgba(0,238,252,0.35)', borderRadius: 1,
              }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              {[session.bpm_start, session.bpm_peak, session.bpm_end].map((v, i) => (
                <span key={i} style={{ ...S.labelDim, fontSize: 8, color: '#494847', fontVariantNumeric: 'tabular-nums' }}>{v}</span>
              ))}
            </div>
          </div>

          {/* Energy Vector */}
          <div>
            <label style={{ ...S.labelDim, display: 'block', marginBottom: 10 }}>Energy Vector</label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 6 }}>
              {energyVectors.map(({ icon, label, active }) => (
                <div key={label} style={{
                  background: active ? '#cafd00' : '#262626',
                  padding: '10px 6px', borderRadius: 2,
                  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5,
                  boxShadow: active ? '0 0 18px rgba(202,253,0,0.28)' : 'none',
                  transition: 'all 0.2s ease',
                }}>
                  <span className="material-symbols-outlined" style={{ fontSize: 20, color: active ? '#3a4a00' : '#adaaaa' }}>{icon}</span>
                  <span style={{ ...S.labelDim, fontSize: 7, color: active ? '#3a4a00' : '#adaaaa' }}>{label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Harmonic lock toggle */}
          <div style={{ paddingTop: 10, borderTop: '1px solid rgba(255,255,255,0.04)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 11, color: '#adaaaa', fontFamily: 'Inter', fontStyle: 'italic' }}>Harmonic Lock Enabled</span>
            <div style={{ width: 36, height: 18, background: '#006970', borderRadius: 12, position: 'relative', cursor: 'pointer' }}>
              <div style={{ position: 'absolute', right: 2, top: 2, width: 14, height: 14, borderRadius: '50%', background: '#00eefc' }} />
            </div>
          </div>
        </div>
      </div>

      {/* ── Right: Intelligence Results ── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ ...S.headline, fontSize: 11, letterSpacing: '0.3em', color: '#ffffff', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#cafd00', display: 'inline-block', animation: 'pulse-glow 1.5s ease-in-out infinite' }} />
            Intelligence Results
          </h3>
          <span style={{ ...S.labelDim, color: '#494847' }}>{upcoming.length} tracks queued</span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {upcoming.slice(0, 8).map((t, i) => {
            const refBpm = nowPlaying?.target_bpm ?? session.bpm_peak
            const score = Math.max(62, Math.round(100 - Math.abs(t.target_bpm - refBpm) * 1.2 - i * 1.5))
            const isTop = i === 0
            return (
              <div key={t.position} style={{
                background: isTop ? '#201f1f' : '#131313',
                padding: '14px 16px',
                display: 'flex', alignItems: 'center', gap: 14,
                position: 'relative', overflow: 'hidden',
                borderLeft: `3px solid ${isTop ? '#cafd00' : `rgba(202,253,0,${Math.max(0.08, 0.6 - i * 0.08)})`}`,
                transition: 'background 0.15s ease',
              }}>
                {/* Track icon */}
                <div style={{ width: 38, height: 38, background: '#262626', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <span className="material-symbols-outlined" style={{ fontSize: 18, color: isTop ? '#cafd00' : '#adaaaa' }}>
                    {isTop ? 'play_circle' : 'music_note'}
                  </span>
                </div>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 3 }}>
                    <h4 style={{ ...S.headline, fontSize: 14, color: '#ffffff', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', paddingRight: 8, letterSpacing: '-0.01em' }}>
                      {t.title}
                    </h4>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 1, color: isTop ? '#cafd00' : '#adaaaa', flexShrink: 0 }}>
                      <span style={{ fontFamily: 'Space Grotesk', fontWeight: 900, fontSize: 18, fontStyle: 'italic' }}>{score}</span>
                      <span style={{ fontSize: 9, fontWeight: 700, fontFamily: 'Inter' }}>%</span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 11, color: '#adaaaa', fontFamily: 'Inter', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {t.artist}
                    </span>
                    <div style={{ width: 1, height: 10, background: '#262626', flexShrink: 0 }} />
                    <span style={{ ...S.mono, fontSize: 9, color: '#00eefc', flexShrink: 0 }}>{Math.round(t.target_bpm)} BPM</span>
                    {t.camelot && t.camelot !== 'Unknown' && (
                      <span style={{ ...S.labelDim, fontSize: 8, padding: '1px 6px', background: '#262626', flexShrink: 0 }}>{t.camelot}</span>
                    )}
                  </div>
                </div>

                {/* Mini waveform */}
                <div style={{ display: 'flex', alignItems: 'flex-end', gap: '2px', height: 26, width: 50, flexShrink: 0, opacity: isTop ? 1 : 0.25 }}>
                  {[3, 5, 8, 6, 4, 7, 5].map((h, j) => (
                    <div key={j} style={{
                      flex: 1, height: `${h * 10}%`,
                      background: isTop ? '#cafd00' : '#00eefc',
                      boxShadow: isTop && j === 2 ? '0 0 8px rgba(202,253,0,0.6)' : 'none',
                    }} />
                  ))}
                </div>
              </div>
            )
          })}

          {upcoming.length === 0 && (
            <div style={{ padding: '28px', textAlign: 'center', background: '#131313' }}>
              <p style={{ fontSize: 11, color: '#494847', fontFamily: 'Inter' }}>No upcoming tracks in queue</p>
            </div>
          )}
        </div>

        {/* BPM arc summary */}
        <div style={{ background: '#131313', padding: '14px 16px' }}>
          <p style={{ ...S.labelDim, marginBottom: 12 }}>Session BPM Arc</p>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            {[
              { label: 'start', val: session.bpm_start },
              { label: 'peak', val: session.bpm_peak },
              { label: 'end', val: session.bpm_end },
            ].map(x => (
              <div key={x.label} style={{ textAlign: x.label === 'end' ? 'right' : x.label === 'peak' ? 'center' : 'left' }}>
                <span style={{ ...S.mono, fontFamily: 'Space Grotesk', fontSize: 20, color: x.label === 'peak' ? '#cafd00' : '#adaaaa' }}>{x.val}</span>
                <p style={{ ...S.labelDim, marginTop: 3 }}>{x.label}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

/* ─── LIBRARY VIEW ──────────────────────────────────────────── */
function LibraryView() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '65vh', gap: 18, padding: 24 }}>
      <span className="material-symbols-outlined" style={{ fontSize: 64, color: '#262626' }}>library_music</span>
      <div style={{ textAlign: 'center' }}>
        <p style={{ ...S.headline, fontSize: 14, color: '#adaaaa', letterSpacing: '0.3em', marginBottom: 10 }}>Track Library</p>
        <p style={{ fontSize: 12, color: '#494847', fontFamily: 'Inter', lineHeight: 1.7, maxWidth: 320 }}>
          Your track library is built from your FMA dataset.<br />
          Upload DJ sets to expand the intelligence engine.
        </p>
      </div>
      <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
        <div style={{ background: '#131313', padding: '12px 20px', borderLeft: '2px solid #cafd00' }}>
          <p style={{ ...S.labelDim, marginBottom: 4 }}>Source</p>
          <p style={{ fontFamily: 'Space Grotesk', fontWeight: 700, fontSize: 13, color: '#ffffff', textTransform: 'uppercase' }}>FMA Dataset</p>
        </div>
        <div style={{ background: '#131313', padding: '12px 20px', borderLeft: '2px solid #00eefc' }}>
          <p style={{ ...S.labelDim, marginBottom: 4 }}>Model</p>
          <p style={{ fontFamily: 'Space Grotesk', fontWeight: 700, fontSize: 13, color: '#ffffff', textTransform: 'uppercase' }}>LightGBM</p>
        </div>
      </div>
    </div>
  )
}

/* ─── MAIN COMPONENT ────────────────────────────────────────── */
export default function SomaDashboard() {
  const [tab, setTab]               = useState<Tab>('discover')
  const [arcTypes, setArcTypes]     = useState<ArcType[]>([])
  const [selectedArc, setSelectedArc] = useState<string>('')
  const [duration, setDuration]     = useState(60)
  const [loading, setLoading]       = useState(false)
  const [session, setSession]       = useState<Session | null>(null)
  const [nowPlaying, setNowPlaying] = useState<NowPlaying | null>(null)
  const [scanning, setScanning]     = useState(false)
  const [done, setDone]             = useState(false)
  const [error, setError]           = useState<string | null>(null)
  const [hoverRating, setHoverRating] = useState(0)
  const [isPlaying, setIsPlaying]   = useState(false)

  const audioRef = useRef<HTMLAudioElement>(null)

  // Load arc types on mount
  useEffect(() => {
    api.getArcTypes()
      .then(r => { setArcTypes(r.arc_types); setSelectedArc(r.arc_types[0]?.key || '') })
      .catch(() => setError('Could not reach the SOMA server. Is the backend running?'))
  }, [])

  // Inject desktop top bar CSS (show on md+)
  useEffect(() => {
    const style = document.createElement('style')
    style.textContent = `@media (min-width: 768px) { .md-topbar { display: flex !important; } }`
    document.head.appendChild(style)
    return () => document.head.removeChild(style)
  }, [])

  const startSession = async () => {
    if (!selectedArc) return
    setLoading(true)
    setError(null)
    try {
      const s = await api.createSession(selectedArc, duration)
      setSession(s)
      setDone(false)
      setTab('journey')
      await loadNextTrack(s.session_id)
    } catch {
      setError('Failed to create session. Make sure the backend is running and the database has tracks.')
    } finally { setLoading(false) }
  }

  const loadNextTrack = useCallback(async (sessionId: number) => {
    setScanning(true)
    setError(null)
    setHoverRating(0)
    setIsPlaying(false)
    try {
      const next = await api.nextTrack(sessionId)
      if (next.done) { setDone(true); setNowPlaying(null) }
      else setNowPlaying(next)
    } catch {
      setError('Failed to load next track.')
    } finally { setScanning(false) }
  }, [])

  const handleEvent = async (event: 'completed' | 'skipped', rating?: number) => {
    if (!session || !nowPlaying) return
    await api.recordEvent(session.session_id, event, nowPlaying.position, rating)
    const updated = await api.getSession(session.session_id)
    setSession(updated)
    await loadNextTrack(session.session_id)
  }

  const handleNewSession = () => {
    setSession(null)
    setNowPlaying(null)
    setDone(false)
    setError(null)
    setTab('discover')
  }

  return (
    <div style={{ background: '#0e0e0e', color: '#ffffff', fontFamily: 'Inter', minHeight: '100dvh' }}>
      {/* Desktop top bar */}
      <TopBar tab={tab} setTab={setTab} hasSession={!!session} />

      {/* Main content — offset on desktop for fixed top bar */}
      <main className="main-offset">
        {tab === 'discover' && (
          <DiscoverView
            arcTypes={arcTypes}
            selectedArc={selectedArc}
            setSelectedArc={setSelectedArc}
            duration={duration}
            setDuration={setDuration}
            loading={loading}
            error={error}
            onStart={startSession}
          />
        )}
        {tab === 'journey' && (
          <JourneyView
            session={session}
            nowPlaying={nowPlaying}
            scanning={scanning}
            done={done}
            error={error}
            isPlaying={isPlaying}
            hoverRating={hoverRating}
            setHoverRating={setHoverRating}
            audioRef={audioRef}
            onSetIsPlaying={setIsPlaying}
            onEvent={handleEvent}
            onNewSession={handleNewSession}
          />
        )}
        {tab === 'laboratory' && (
          <LaboratoryView session={session} nowPlaying={nowPlaying} />
        )}
        {tab === 'library' && <LibraryView />}
      </main>

      {/* Mobile bottom nav */}
      <BottomNav tab={tab} setTab={setTab} hasSession={!!session} />
    </div>
  )
}
