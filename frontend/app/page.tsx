'use client'

import { useState, useEffect, useCallback } from 'react'
import { api, ArcType, Session, NowPlaying } from '@/lib/api'
import CamelotWheel from '@/components/CamelotWheel'
import EnergyArc from '@/components/EnergyArc'
import TransitionScanner from '@/components/TransitionScanner'
import AudioPlayer from '@/components/AudioPlayer'
import SessionQueue from '@/components/SessionQueue'

type View = 'home' | 'session'

const ARC_SHAPES: Record<string, number[]> = {
  peak_hour:  [0.35, 0.48, 0.62, 0.75, 0.88, 0.97, 1.00, 1.00, 1.00, 0.92],
  workout:    [0.25, 0.45, 0.70, 0.90, 1.00, 1.00, 0.90, 0.75, 0.55, 0.35],
  deep_focus: [0.25, 0.32, 0.42, 0.56, 0.68, 0.80, 0.88, 0.90, 0.90, 0.90],
  sleep:      [0.75, 0.66, 0.56, 0.46, 0.37, 0.30, 0.24, 0.20, 0.17, 0.15],
  meditate:   [0.28, 0.30, 0.25, 0.32, 0.27, 0.31, 0.25, 0.32, 0.27, 0.30],
  recovery:   [0.65, 0.58, 0.51, 0.45, 0.40, 0.35, 0.31, 0.29, 0.27, 0.26],
  hiit:       [0.28, 0.95, 0.28, 0.95, 0.28, 0.95, 0.28, 0.95, 0.28, 0.95],
}

const ARC_ACCENT: Record<string, string> = {
  peak_hour:  '#e8305a',
  workout:    '#ff6b35',
  deep_focus: '#4488ff',
  sleep:      '#9966dd',
  meditate:   '#0fd4b8',
  recovery:   '#44cc88',
  hiit:       '#ffaa22',
}

/* ── Hero arc: full-width waveform for selected arc ── */
function HeroArc({ arcKey, color }: { arcKey: string; color: string }) {
  const pts = ARC_SHAPES[arcKey] || Array(10).fill(0.5)
  const W = 400; const H = 52
  const points = pts.map((v, i) =>
    `${(i / (pts.length - 1)) * W},${H - v * (H - 8) - 4}`
  ).join(' ')
  return (
    <svg
      width="100%" height={H}
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      style={{ display: 'block', overflow: 'visible' }}
    >
      <defs>
        <linearGradient id="heroGrad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%"   stopColor={color} stopOpacity="0.3" />
          <stop offset="50%"  stopColor={color} stopOpacity="1"   />
          <stop offset="100%" stopColor={color} stopOpacity="0.3" />
        </linearGradient>
        <filter id="heroGlow">
          <feGaussianBlur stdDeviation="2.5" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>
      <polyline
        points={points}
        fill="none"
        stroke="url(#heroGrad)"
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
        filter="url(#heroGlow)"
        className="draw-wave"
      />
    </svg>
  )
}

/* ── Mini arc for arc cards ── */
function MiniArc({ arcKey, color, active }: { arcKey: string; color: string; active: boolean }) {
  const pts = ARC_SHAPES[arcKey] || Array(10).fill(0.5)
  const W = 60; const H = 22
  const points = pts.map((v, i) =>
    `${(i / (pts.length - 1)) * W},${H - v * (H - 4) - 2}`
  ).join(' ')
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ overflow: 'visible', display: 'block', flexShrink: 0 }}>
      <polyline
        points={points}
        fill="none"
        stroke={active ? color : 'rgba(255,255,255,0.16)'}
        strokeWidth={active ? 1.5 : 1}
        strokeLinejoin="round"
        strokeLinecap="round"
        style={{ transition: 'stroke 0.3s ease' }}
      />
    </svg>
  )
}

/* ── SVG star icon ── */
function StarIcon({ filled, color }: { filled: boolean; color: string }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24"
      fill={filled ? color : 'none'}
      stroke={filled ? color : 'rgba(255,255,255,0.22)'}
      strokeWidth="1.5"
      strokeLinejoin="round"
    >
      <polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26" />
    </svg>
  )
}

export default function SomaDashboard() {
  const [view, setView]               = useState<View>('home')
  const [arcTypes, setArcTypes]       = useState<ArcType[]>([])
  const [selectedArc, setSelectedArc] = useState<string>('')
  const [duration, setDuration]       = useState(60)
  const [loading, setLoading]         = useState(false)
  const [session, setSession]         = useState<Session | null>(null)
  const [nowPlaying, setNowPlaying]   = useState<NowPlaying | null>(null)
  const [scanning, setScanning]       = useState(false)
  const [done, setDone]               = useState(false)
  const [error, setError]             = useState<string | null>(null)
  const [hoverRating, setHoverRating] = useState(0)

  useEffect(() => {
    api.getArcTypes()
      .then(r => { setArcTypes(r.arc_types); setSelectedArc(r.arc_types[0]?.key || '') })
      .catch(() => setError('Could not reach the SOMA server. Is the backend running?'))
  }, [])

  const startSession = async () => {
    if (!selectedArc) return
    setLoading(true)
    setError(null)
    try {
      const s = await api.createSession(selectedArc, duration)
      setSession(s); setDone(false); setView('session')
      await loadNextTrack(s.session_id)
    } catch {
      setError('Failed to create session. Make sure the backend is running and the database has tracks.')
    } finally { setLoading(false) }
  }

  const loadNextTrack = useCallback(async (sessionId: number) => {
    setScanning(true)
    setError(null)
    setHoverRating(0)
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

  const currentPosition = nowPlaying?.position ?? 0
  const homeAccent      = ARC_ACCENT[selectedArc]             || '#e8305a'
  const sessionAccent   = ARC_ACCENT[session?.arc_type || ''] || '#e8305a'
  const totalTracks     = session?.total_tracks ?? 0
  const progressPct     = totalTracks > 0 ? (currentPosition / totalTracks) * 100 : 0

  /* ─── HOME ──────────────────────────────────────────────── */
  if (view === 'home') {
    return (
      <div className="relative min-h-screen z-10 flex flex-col">
        <div className="orb orb-pink" />
        <div className="orb orb-teal" />
        <div className="orb orb-blue" />

        <div
          className="flex-1 flex flex-col items-center justify-center"
          style={{ padding: '60px 20px', width: '100%', maxWidth: 500, margin: '0 auto' }}
        >
          {/* Wordmark */}
          <div className="text-center fade-up" style={{ marginBottom: 36 }}>
            <h1
              className="heading-hero"
              style={{
                fontSize: 'clamp(4rem, 14vw, 6.5rem)',
                background: `linear-gradient(135deg, ${homeAccent} 0%, rgba(255,255,255,0.92) 58%)`,
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
                transition: 'background 0.5s ease',
              }}
            >
              SOMA
            </h1>
            <p className="label-dim" style={{ marginTop: 10, letterSpacing: '0.32em' }}>
              Generative DJ Intelligence
            </p>
          </div>

          {/* Error banner */}
          {error && (
            <div
              className="w-full glass-card fade-up"
              style={{ padding: '14px 18px', borderColor: 'rgba(232,48,90,0.35)', marginBottom: 20 }}
            >
              <p style={{ fontSize: 12, color: '#e8305a', lineHeight: 1.55 }}>{error}</p>
            </div>
          )}

          {/* Hero arc visualization for selected arc */}
          {selectedArc && !error && (
            <div className="w-full fade-up" style={{ marginBottom: 28, animationDelay: '30ms' }}>
              <HeroArc key={selectedArc} arcKey={selectedArc} color={homeAccent} />
            </div>
          )}

          <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 22 }}>

            {/* Arc type list */}
            <div>
              <p className="label-dim" style={{ marginBottom: 12 }}>Session Type</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }} className="stagger">
                {arcTypes.length === 0 && !error && Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="skeleton" style={{ height: 56, borderRadius: 16 }} />
                ))}
                {arcTypes.map(arc => {
                  const color  = ARC_ACCENT[arc.key] || '#e8305a'
                  const active = selectedArc === arc.key
                  return (
                    <button
                      key={arc.key}
                      onClick={() => setSelectedArc(arc.key)}
                      className="fade-up"
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 16,
                        padding: '13px 16px',
                        borderRadius: 16,
                        background: active ? `${color}0d` : 'rgba(255,255,255,0.025)',
                        border: `1px solid ${active ? color + '38' : 'rgba(255,255,255,0.06)'}`,
                        boxShadow: active ? `0 0 28px ${color}12` : 'none',
                        transition: 'all 0.22s ease',
                        textAlign: 'left',
                        cursor: 'pointer',
                        width: '100%',
                      }}
                    >
                      {/* Mini waveform */}
                      <MiniArc arcKey={arc.key} color={color} active={active} />

                      {/* Label + description */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <span
                          className="heading-display"
                          style={{
                            fontSize: 10,
                            color: active ? color : 'rgba(255,255,255,0.58)',
                            transition: 'color 0.22s ease',
                            display: 'block',
                            marginBottom: 3,
                          }}
                        >
                          {arc.label}
                        </span>
                        <p style={{
                          fontSize: 10,
                          color: 'rgba(255,255,255,0.28)',
                          fontFamily: 'DM Sans',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          lineHeight: 1.4,
                        }}>
                          {arc.description}
                        </p>
                      </div>

                      {/* BPM range */}
                      <div style={{ textAlign: 'right', flexShrink: 0 }}>
                        <span
                          className="dot-matrix"
                          style={{ fontSize: 10, color: active ? color : 'rgba(255,255,255,0.22)', transition: 'color 0.22s ease' }}
                        >
                          {arc.bpm_start}–{arc.bpm_peak}
                        </span>
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Duration slider */}
            <div className="fade-up" style={{ animationDelay: '110ms' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 12 }}>
                <p className="label-dim">Duration</p>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 5 }}>
                  <span
                    className="dot-matrix"
                    style={{
                      fontSize: 22,
                      color: homeAccent,
                      textShadow: `0 0 12px ${homeAccent}80`,
                      transition: 'color 0.4s ease, text-shadow 0.4s ease',
                    }}
                  >
                    {duration}
                  </span>
                  <span className="label-dim">min</span>
                </div>
              </div>
              <input
                type="range" min={15} max={180} step={15}
                value={duration}
                onChange={e => setDuration(Number(e.target.value))}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
                <span className="label-dim">15 min</span>
                <span className="label-dim">3 hr</span>
              </div>
            </div>

            <div className="soma-divider" />

            {/* Start button */}
            <button
              onClick={startSession}
              disabled={loading || !selectedArc}
              className="heading-display fade-up"
              style={{
                width: '100%',
                fontSize: 11,
                letterSpacing: '0.3em',
                padding: '19px',
                borderRadius: 18,
                background: loading
                  ? 'rgba(255,255,255,0.06)'
                  : `linear-gradient(135deg, ${homeAccent}cc 0%, ${homeAccent}88 100%)`,
                border: `1px solid ${homeAccent}30`,
                boxShadow: loading ? 'none' : `0 0 48px ${homeAccent}1e, 0 8px 28px rgba(0,0,0,0.35)`,
                opacity: loading ? 0.65 : 1,
                cursor: loading ? 'not-allowed' : 'pointer',
                transition: 'all 0.28s ease',
                animationDelay: '150ms',
                color: 'rgba(255,255,255,0.95)',
              }}
            >
              {loading ? 'Planning Session…' : 'Start Session'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  /* ─── SESSION ────────────────────────────────────────────── */
  return (
    <div className="relative min-h-screen z-10">
      <div className="orb orb-pink" style={{ opacity: 0.28 }} />
      <div className="orb orb-teal" style={{ opacity: 0.18 }} />

      <div className="fade-in" style={{ maxWidth: 980, margin: '0 auto', padding: '18px 16px 48px' }}>

        {/* Error */}
        {error && (
          <div className="glass-card" style={{ padding: '12px 16px', borderColor: 'rgba(232,48,90,0.35)', marginBottom: 14 }}>
            <p style={{ fontSize: 12, color: '#e8305a' }}>{error}</p>
          </div>
        )}

        {/* Top bar */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <button
            onClick={() => setView('home')}
            className="label-mid"
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '8px 14px 8px 10px',
              borderRadius: 12,
              background: 'transparent',
              border: '1px solid transparent',
              cursor: 'pointer',
              transition: 'all 0.18s ease',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = 'transparent' }}
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <path d="M8 10L4 6l4-4" />
            </svg>
            Back
          </button>

          <span className="heading-display" style={{ fontSize: 9, letterSpacing: '0.52em', color: 'rgba(255,255,255,0.3)' }}>
            SOMA
          </span>

          <span className="dot-matrix" style={{ fontSize: 10, color: 'rgba(255,255,255,0.28)' }}>
            {currentPosition}&thinsp;/&thinsp;{totalTracks}
          </span>
        </div>

        {/* Session progress line */}
        {totalTracks > 0 && (
          <div style={{ marginBottom: 18 }}>
            <div style={{ height: 2, background: 'rgba(255,255,255,0.06)', borderRadius: 2 }}>
              <div style={{
                height: '100%',
                width: `${progressPct}%`,
                background: `linear-gradient(90deg, ${sessionAccent}88, ${sessionAccent})`,
                borderRadius: 2,
                boxShadow: `0 0 8px ${sessionAccent}55`,
                transition: 'width 0.7s cubic-bezier(0.22,1,0.36,1)',
              }} />
            </div>
          </div>
        )}

        {/* 2-col on desktop, 1-col on mobile */}
        <div className="session-grid">

          {/* ── LEFT: Now Playing ── */}
          <div
            className="glass-card"
            style={{
              padding: '28px 26px',
              boxShadow: `0 0 80px ${sessionAccent}0e, 0 24px 64px rgba(0,0,0,0.48)`,
              borderColor: `${sessionAccent}18`,
            }}
          >
            {done ? (
              /* ── Done ── */
              <div className="text-center scale-in" style={{ padding: '44px 0' }}>
                <p
                  className="heading-display"
                  style={{ fontSize: 22, color: sessionAccent, letterSpacing: '0.2em', marginBottom: 10 }}
                >
                  Session Complete
                </p>
                <p className="label-dim" style={{ marginBottom: 36 }}>Your set has ended.</p>
                <button
                  onClick={() => { setView('home'); setSession(null); setNowPlaying(null); setDone(false) }}
                  className="heading-display"
                  style={{
                    fontSize: 10, letterSpacing: '0.24em',
                    padding: '14px 38px', borderRadius: 14,
                    background: `${sessionAccent}10`,
                    border: `1px solid ${sessionAccent}32`,
                    cursor: 'pointer',
                    color: 'rgba(255,255,255,0.85)',
                    transition: 'background 0.2s ease',
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = `${sessionAccent}20`)}
                  onMouseLeave={e => (e.currentTarget.style.background = `${sessionAccent}10`)}
                >
                  New Session
                </button>
              </div>

            ) : scanning && !nowPlaying ? (
              /* ── Scanning ── */
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '52px 0', gap: 16 }}>
                <TransitionScanner scanning={true} label="Selecting next track" />
              </div>

            ) : nowPlaying ? (
              /* ── Now Playing ── */
              <div key={nowPlaying.position} className="track-enter">

                {/* Track info */}
                <div style={{ marginBottom: 22 }}>
                  <p className="label-dim" style={{ marginBottom: 10 }}>Now Playing</p>
                  <h2
                    className="font-display"
                    style={{
                      fontSize: 'clamp(1.8rem, 5vw, 2.5rem)',
                      fontWeight: 300,
                      color: 'rgba(255,255,255,0.96)',
                      letterSpacing: '-0.015em',
                      lineHeight: 1.12,
                      marginBottom: 9,
                    }}
                  >
                    {nowPlaying.title}
                  </h2>
                  <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.36)', fontFamily: 'DM Sans', fontWeight: 300, letterSpacing: '0.02em' }}>
                    {nowPlaying.artist}
                  </p>
                </div>

                {/* Metric pills */}
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 22 }}>
                  {[
                    { label: 'BPM',    value: String(Math.round(nowPlaying.bpm)),    color: '#e8305a' },
                    { label: 'Key',    value: (nowPlaying.camelot && nowPlaying.camelot !== 'Unknown') ? nowPlaying.camelot : '—', color: '#0fd4b8' },
                    { label: 'Target', value: String(Math.round(nowPlaying.target_bpm)), color: '#4488ff' },
                  ].map(m => (
                    <div
                      key={m.label}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '7px 14px',
                        borderRadius: 100,
                        background: `${m.color}0d`,
                        border: `1px solid ${m.color}26`,
                      }}
                    >
                      <span className="label-dim" style={{ fontSize: 9 }}>{m.label}</span>
                      <span
                        key={m.value}
                        className="dot-matrix count-up"
                        style={{ fontSize: 15, color: m.color, textShadow: `0 0 10px ${m.color}70` }}
                      >
                        {m.value}
                      </span>
                    </div>
                  ))}
                </div>

                <div className="soma-divider" style={{ marginBottom: 20 }} />

                {/* Audio player */}
                <div style={{ marginBottom: 20 }}>
                  <AudioPlayer
                    audioUrl={nowPlaying.audio_url}
                    onEnded={() => handleEvent('completed')}
                  />
                </div>

                {/* Controls: skip + star rating */}
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <button
                    onClick={() => handleEvent('skipped')}
                    className="label-mid"
                    style={{
                      padding: '12px 20px',
                      borderRadius: 14,
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.08)',
                      fontSize: 10,
                      letterSpacing: '0.1em',
                      textTransform: 'uppercase',
                      fontFamily: 'DM Sans',
                      cursor: 'pointer',
                      flexShrink: 0,
                      transition: 'background 0.18s ease',
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.08)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.04)')}
                  >
                    Skip
                  </button>

                  {/* Star rating */}
                  <div
                    style={{ display: 'flex', flex: 1, gap: 6 }}
                    onMouseLeave={() => setHoverRating(0)}
                  >
                    {[1, 2, 3, 4, 5].map(r => (
                      <button
                        key={r}
                        onClick={() => handleEvent('completed', r)}
                        onMouseEnter={() => setHoverRating(r)}
                        style={{
                          flex: 1,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          padding: '12px 0',
                          borderRadius: 14,
                          background: r <= hoverRating ? `${sessionAccent}18` : `${sessionAccent}07`,
                          border: `1px solid ${r <= hoverRating ? sessionAccent + '44' : sessionAccent + '14'}`,
                          cursor: 'pointer',
                          transition: 'all 0.12s ease',
                        }}
                      >
                        <StarIcon filled={r <= hoverRating} color={sessionAccent} />
                      </button>
                    ))}
                  </div>
                </div>

                {/* Scanning overlay while transitioning */}
                {scanning && (
                  <div style={{ display: 'flex', justifyContent: 'center', marginTop: 22 }}>
                    <TransitionScanner scanning={true} />
                  </div>
                )}
              </div>
            ) : null}
          </div>

          {/* ── RIGHT: Context sidebar ── */}
          {session && !done && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

              {/* BPM Arc */}
              <div className="glass-card" style={{ padding: '18px 20px' }}>
                <p className="label-dim" style={{ marginBottom: 12 }}>BPM Arc</p>
                <EnergyArc tracks={session.tracks} currentPosition={currentPosition} />
                <div className="soma-divider" style={{ margin: '12px 0 10px' }} />
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  {[
                    { label: 'start', val: session.bpm_start },
                    { label: 'peak',  val: session.bpm_peak  },
                    { label: 'end',   val: session.bpm_end   },
                  ].map(x => (
                    <div key={x.label} style={{ textAlign: x.label === 'end' ? 'right' : x.label === 'peak' ? 'center' : 'left' }}>
                      <span className="dot-matrix" style={{ fontSize: 13, color: sessionAccent }}>{x.val}</span>
                      <p className="label-dim" style={{ marginTop: 3 }}>{x.label}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Camelot Wheel */}
              {nowPlaying && (
                <div className="glass-card" style={{ padding: '18px 20px' }}>
                  <p className="label-dim" style={{ marginBottom: 14 }}>Camelot Wheel</p>
                  <div style={{ display: 'flex', justifyContent: 'center' }}>
                    <CamelotWheel
                      activeCode={(nowPlaying.camelot && nowPlaying.camelot !== 'Unknown') ? nowPlaying.camelot : null}
                      size={180}
                    />
                  </div>
                </div>
              )}

              {/* Queue */}
              <div className="glass-card" style={{ padding: '18px 20px' }}>
                <SessionQueue tracks={session.tracks} currentPosition={currentPosition} />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
