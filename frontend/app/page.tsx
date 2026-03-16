'use client'

import { useState, useEffect, useCallback } from 'react'
import { api, ArcType, Session, NowPlaying } from '@/lib/api'
import CamelotWheel from '@/components/CamelotWheel'
import EnergyArc from '@/components/EnergyArc'
import TransitionScanner from '@/components/TransitionScanner'
import AudioPlayer from '@/components/AudioPlayer'
import SessionQueue from '@/components/SessionQueue'

type View = 'home' | 'session'

// Normalised BPM shape for each arc type (10 points, 0–1)
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

function MiniArc({ arcKey, color, active }: { arcKey: string; color: string; active: boolean }) {
  const pts = ARC_SHAPES[arcKey] || Array(10).fill(0.5)
  const W = 76; const H = 26
  const points = pts.map((v, i) =>
    `${(i / (pts.length - 1)) * W},${H - v * (H - 4) - 2}`
  ).join(' ')
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ overflow: 'visible', display: 'block' }}>
      <polyline
        points={points}
        fill="none"
        stroke={active ? color : 'rgba(255,255,255,0.18)'}
        strokeWidth={active ? 1.5 : 1}
        strokeLinejoin="round"
        strokeLinecap="round"
        style={{ transition: 'stroke 0.3s ease' }}
      />
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
    } catch (e) {
      setError('Failed to create session. Make sure the backend is running and the database has tracks.')
    } finally { setLoading(false) }
  }

  const loadNextTrack = useCallback(async (sessionId: number) => {
    setScanning(true)
    setError(null)
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
  const homeAccent    = ARC_ACCENT[selectedArc]             || '#e8305a'
  const sessionAccent = ARC_ACCENT[session?.arc_type || ''] || '#e8305a'

  /* ─── HOME ──────────────────────────────────────── */
  if (view === 'home') {
    return (
      <div className="relative min-h-screen z-10 flex flex-col">
        {/* Ambient orbs */}
        <div className="orb orb-pink" />
        <div className="orb orb-teal" />
        <div className="orb orb-blue" />

        <div className="flex-1 flex flex-col items-center justify-center px-5 py-16 w-full max-w-xl mx-auto">

          {/* Wordmark */}
          <div className="mb-14 text-center fade-up" style={{ animationDelay: '0ms' }}>
            <h1
              className="heading-hero"
              style={{
                fontSize: 'clamp(3.5rem, 12vw, 5.5rem)',
                background: `linear-gradient(135deg, ${homeAccent} 0%, rgba(255,255,255,0.88) 60%)`,
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
                transition: 'background 0.6s ease',
              }}
            >
              SOMA
            </h1>
            <p className="label-dim mt-3" style={{ letterSpacing: '0.3em' }}>
              Generative DJ Intelligence
            </p>
          </div>

          {/* Error banner */}
          {error && (
            <div
              className="w-full glass-card mb-6 fade-up"
              style={{ padding: '14px 18px', borderColor: 'rgba(232,48,90,0.35)', boxShadow: '0 0 24px rgba(232,48,90,0.1)' }}
            >
              <p style={{ fontSize: 12, color: '#e8305a', lineHeight: 1.5 }}>{error}</p>
            </div>
          )}

          {/* Arc type grid */}
          <div className="w-full space-y-7">
            <div>
              <p className="label-dim mb-4">Session Type</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 stagger">
                {arcTypes.map(arc => {
                  const color  = ARC_ACCENT[arc.key] || '#e8305a'
                  const active = selectedArc === arc.key
                  return (
                    <button
                      key={arc.key}
                      onClick={() => setSelectedArc(arc.key)}
                      className="glass-card glass-card-hover p-4 text-left fade-up"
                      style={{
                        borderColor:  active ? `${color}50` : 'rgba(255,255,255,0.06)',
                        boxShadow: active
                          ? `0 0 28px ${color}18, 0 8px 32px rgba(0,0,0,0.35)`
                          : '0 4px 16px rgba(0,0,0,0.2)',
                      }}
                    >
                      {/* Label + BPM range */}
                      <div className="flex items-start justify-between mb-3">
                        <span
                          className="heading-display"
                          style={{
                            fontSize: 11,
                            color: active ? color : 'rgba(255,255,255,0.65)',
                            transition: 'color 0.25s ease',
                          }}
                        >
                          {arc.label}
                        </span>
                        <div className="flex items-center gap-1" style={{ marginTop: 1 }}>
                          <span className="dot-matrix" style={{ fontSize: 9, color: active ? color : 'rgba(255,255,255,0.28)' }}>
                            {arc.bpm_start}
                          </span>
                          <span style={{ color: 'rgba(255,255,255,0.18)', fontSize: 8 }}>–</span>
                          <span className="dot-matrix" style={{ fontSize: 9, color: active ? color : 'rgba(255,255,255,0.28)' }}>
                            {arc.bpm_peak}
                          </span>
                        </div>
                      </div>

                      {/* Mini waveform */}
                      <div className="mb-3">
                        <MiniArc arcKey={arc.key} color={color} active={active} />
                      </div>

                      {/* Description */}
                      <p style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', lineHeight: 1.5, fontFamily: 'DM Sans' }}>
                        {arc.description}
                      </p>
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Duration slider */}
            <div className="fade-up" style={{ animationDelay: '120ms' }}>
              <div className="flex justify-between items-baseline mb-3">
                <p className="label-dim">Duration</p>
                <div className="flex items-baseline gap-1">
                  <span
                    className="dot-matrix"
                    style={{ fontSize: 22, color: homeAccent, textShadow: `0 0 12px ${homeAccent}`, transition: 'color 0.4s ease, text-shadow 0.4s ease' }}
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
                style={{ '--accent': homeAccent } as React.CSSProperties}
              />
              <div className="flex justify-between mt-2">
                <span className="label-dim">15 min</span>
                <span className="label-dim">3 hr</span>
              </div>
            </div>

            {/* Divider */}
            <div className="soma-divider" />

            {/* Start button */}
            <button
              onClick={startSession}
              disabled={loading || !selectedArc}
              className="w-full py-5 rounded-2xl heading-display fade-up"
              style={{
                fontSize: 12,
                letterSpacing: '0.28em',
                background: `linear-gradient(135deg, ${homeAccent}e0 0%, ${homeAccent}99 100%)`,
                border: `1px solid ${homeAccent}44`,
                boxShadow: `0 0 48px ${homeAccent}28, 0 8px 28px rgba(0,0,0,0.4)`,
                opacity: loading ? 0.6 : 1,
                cursor: loading ? 'not-allowed' : 'pointer',
                transition: 'opacity 0.3s ease, box-shadow 0.3s ease',
                animationDelay: '160ms',
              }}
            >
              {loading ? 'Planning Session...' : 'Start Session'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  /* ─── SESSION ──────────────────────────────────── */
  const totalTracks = session?.total_tracks ?? 0

  return (
    <div className="relative min-h-screen z-10">
      {/* Ambient orbs — dimmer in session */}
      <div className="orb orb-pink" style={{ opacity: 0.35 }} />
      <div className="orb orb-teal" style={{ opacity: 0.25 }} />

      <div className="max-w-2xl mx-auto px-4 py-6 space-y-4 fade-in">

        {/* Error banner */}
        {error && (
          <div
            className="glass-card"
            style={{ padding: '12px 16px', borderColor: 'rgba(232,48,90,0.35)' }}
          >
            <p style={{ fontSize: 12, color: '#e8305a' }}>{error}</p>
          </div>
        )}

        {/* Top bar */}
        <div className="flex items-center justify-between">
          <button
            onClick={() => setView('home')}
            className="label-mid hover:text-white transition-colors px-3 py-2 -ml-3 rounded-xl"
            style={{ background: 'rgba(255,255,255,0.0)', transition: 'background 0.2s ease, color 0.2s ease' }}
            onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.05)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.0)')}
          >
            ← Back
          </button>
          <span className="heading-display" style={{ fontSize: 10, letterSpacing: '0.45em', color: 'rgba(255,255,255,0.4)' }}>
            SOMA
          </span>
          <span className="dot-matrix" style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)' }}>
            {currentPosition}&nbsp;/&nbsp;{totalTracks}
          </span>
        </div>

        {/* Session progress dots */}
        {totalTracks > 0 && (
          <div className="flex gap-1.5 flex-wrap px-1">
            {Array.from({ length: Math.min(totalTracks, 30) }).map((_, i) => {
              const pos       = i + 1
              const isCurrent = pos === currentPosition
              const isPast    = pos < currentPosition
              return (
                <div
                  key={i}
                  style={{
                    width: isCurrent ? 18 : 5,
                    height: 5,
                    borderRadius: isCurrent ? 3 : '50%',
                    background: isCurrent
                      ? sessionAccent
                      : isPast
                        ? 'rgba(255,255,255,0.22)'
                        : 'rgba(255,255,255,0.07)',
                    boxShadow: isCurrent ? `0 0 8px ${sessionAccent}` : 'none',
                    transition: 'all 0.4s cubic-bezier(0.34,1.56,0.64,1)',
                    flexShrink: 0,
                  }}
                />
              )
            })}
          </div>
        )}

        {/* Now Playing card */}
        <div
          className="glass-card"
          style={{
            padding: '28px 24px',
            boxShadow: `0 0 70px ${sessionAccent}12, 0 20px 60px rgba(0,0,0,0.55)`,
            borderColor: `${sessionAccent}20`,
          }}
        >
          {done ? (
            /* ── Session complete ── */
            <div className="text-center py-10 fade-up">
              <p
                className="heading-display mb-3"
                style={{ fontSize: 26, color: sessionAccent, letterSpacing: '0.18em' }}
              >
                Session Complete
              </p>
              <p className="label-dim mb-10">Your set has ended.</p>
              <button
                onClick={() => { setView('home'); setSession(null); setNowPlaying(null); setDone(false) }}
                className="px-10 py-4 rounded-2xl heading-display"
                style={{
                  fontSize: 11,
                  letterSpacing: '0.22em',
                  background: `${sessionAccent}15`,
                  border: `1px solid ${sessionAccent}40`,
                  cursor: 'pointer',
                  transition: 'background 0.2s ease',
                }}
              >
                New Session
              </button>
            </div>

          ) : scanning && !nowPlaying ? (
            /* ── Scanning ── */
            <div className="flex flex-col items-center py-10 gap-4">
              <TransitionScanner scanning={true} label="Selecting next track" />
            </div>

          ) : nowPlaying ? (
            /* ── Now playing ── */
            <>
              {/* Track info */}
              <div className="mb-7">
                <p className="label-dim mb-3">Now Playing</p>
                <h2
                  className="font-display font-light leading-tight mb-2"
                  style={{ fontSize: 'clamp(1.5rem, 4vw, 2.1rem)', color: 'rgba(255,255,255,0.95)', letterSpacing: '-0.01em' }}
                >
                  {nowPlaying.title}
                </h2>
                <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.4)', fontFamily: 'DM Sans', fontWeight: 300 }}>
                  {nowPlaying.artist}
                </p>
              </div>

              {/* Metrics row */}
              <div className="grid grid-cols-3 gap-3 mb-7">
                {[
                  { label: 'BPM',    value: String(Math.round(nowPlaying.bpm)),    color: '#e8305a' },
                  { label: 'Key',    value: (nowPlaying.camelot && nowPlaying.camelot !== 'Unknown') ? nowPlaying.camelot : '—', color: '#0fd4b8' },
                  { label: 'Target', value: String(Math.round(nowPlaying.target_bpm)), color: '#4488ff' },
                ].map(m => (
                  <div
                    key={m.label}
                    className="glass-card text-center"
                    style={{ padding: '14px 8px', boxShadow: `0 0 18px ${m.color}10` }}
                  >
                    <p className="label-dim mb-2">{m.label}</p>
                    <span
                      key={m.value}
                      className="dot-matrix count-up"
                      style={{ fontSize: 24, display: 'block', color: m.color, textShadow: `0 0 12px ${m.color}, 0 0 24px ${m.color}55` }}
                    >
                      {m.value}
                    </span>
                  </div>
                ))}
              </div>

              {/* Divider */}
              <div className="soma-divider mb-6" />

              {/* Audio player */}
              <div className="mb-6">
                <AudioPlayer
                  audioUrl={nowPlaying.audio_url}
                  onEnded={() => handleEvent('completed')}
                />
              </div>

              {/* Controls: skip + star rating */}
              <div className="flex gap-2 items-center">
                <button
                  onClick={() => handleEvent('skipped')}
                  className="label-mid hover:text-white rounded-xl transition-all"
                  style={{
                    padding: '11px 16px',
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(255,255,255,0.07)',
                    fontSize: 10,
                    letterSpacing: '0.1em',
                    textTransform: 'uppercase',
                    fontFamily: 'DM Sans',
                    cursor: 'pointer',
                    transition: 'background 0.2s ease',
                    flexShrink: 0,
                  }}
                >
                  Skip
                </button>
                <div className="flex flex-1 gap-1.5">
                  {[1, 2, 3, 4, 5].map(r => (
                    <button
                      key={r}
                      onClick={() => handleEvent('completed', r)}
                      className="flex-1 rounded-xl transition-all"
                      style={{
                        padding: '11px 4px',
                        background: `${sessionAccent}0c`,
                        border: `1px solid ${sessionAccent}22`,
                        color: 'rgba(255,255,255,0.5)',
                        fontSize: 13,
                        cursor: 'pointer',
                        transition: 'background 0.2s ease, color 0.2s ease',
                      }}
                      onMouseEnter={e => {
                        const b = e.currentTarget
                        b.style.background = `${sessionAccent}28`
                        b.style.color = 'rgba(255,255,255,0.9)'
                      }}
                      onMouseLeave={e => {
                        const b = e.currentTarget
                        b.style.background = `${sessionAccent}0c`
                        b.style.color = 'rgba(255,255,255,0.5)'
                      }}
                    >
                      {'★'.repeat(r)}{'☆'.repeat(5 - r)}
                    </button>
                  ))}
                </div>
              </div>

              {/* Scanning overlay indicator */}
              {scanning && (
                <div className="flex justify-center mt-5">
                  <TransitionScanner scanning={true} />
                </div>
              )}
            </>
          ) : null}
        </div>

        {/* Camelot wheel + BPM arc */}
        {session && nowPlaying && !done && (
          <div className="grid grid-cols-2 gap-4">
            <div className="glass-card glow-key p-5 flex flex-col items-center">
              <p className="label-dim mb-4">Camelot</p>
              <CamelotWheel
                activeCode={(nowPlaying.camelot && nowPlaying.camelot !== 'Unknown') ? nowPlaying.camelot : null}
                size={188}
              />
            </div>
            <div className="glass-card glow-compat p-5 flex flex-col">
              <p className="label-dim mb-3">BPM Arc</p>
              <div className="flex-1">
                <EnergyArc tracks={session.tracks} currentPosition={currentPosition} />
              </div>
              <div className="soma-divider my-3" />
              <div className="flex justify-between">
                {[
                  { label: 'start', val: session.bpm_start },
                  { label: 'peak',  val: session.bpm_peak  },
                  { label: 'end',   val: session.bpm_end   },
                ].map(x => (
                  <div key={x.label} style={{ textAlign: x.label === 'end' ? 'right' : x.label === 'peak' ? 'center' : 'left' }}>
                    <span className="dot-matrix" style={{ fontSize: 14, color: sessionAccent }}>{x.val}</span>
                    <p className="label-dim" style={{ marginTop: 2 }}>{x.label}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Queue */}
        {session && !done && (
          <div className="glass-card p-5">
            <SessionQueue tracks={session.tracks} currentPosition={currentPosition} />
          </div>
        )}

        <div style={{ height: 24 }} />
      </div>
    </div>
  )
}
