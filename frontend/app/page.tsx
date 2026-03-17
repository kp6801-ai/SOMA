'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { api, ArcType, Session, NowPlaying } from '@/lib/api'
import EnergyArc from '@/components/EnergyArc'
import TransitionScanner from '@/components/TransitionScanner'
import AudioPlayer from '@/components/AudioPlayer'
import SessionQueue from '@/components/SessionQueue'
import FrequencyVisualizer from '@/components/FrequencyVisualizer'
import BpmKnob from '@/components/BpmKnob'

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

function MiniArc({ arcKey, color, active }: { arcKey: string; color: string; active: boolean }) {
  const pts = ARC_SHAPES[arcKey] || Array(10).fill(0.5)
  const W = 56; const H = 20
  const points = pts.map((v, i) =>
    `${(i / (pts.length - 1)) * W},${H - v * (H - 4) - 2}`
  ).join(' ')
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ overflow: 'visible', display: 'block', flexShrink: 0 }}>
      <polyline
        points={points}
        fill="none"
        stroke={active ? color : 'rgba(255,255,255,0.14)'}
        strokeWidth={active ? 1.5 : 1}
        strokeLinejoin="round"
        strokeLinecap="round"
        style={{ transition: 'stroke 0.3s ease' }}
      />
    </svg>
  )
}

function StarIcon({ filled, color }: { filled: boolean; color: string }) {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24"
      fill={filled ? color : 'none'}
      stroke={filled ? color : 'rgba(255,255,255,0.2)'}
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
  const [isPlaying, setIsPlaying]     = useState(false)

  const audioRef = useRef<HTMLAudioElement>(null)

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

  const currentPosition = nowPlaying?.position ?? 0
  const homeAccent      = ARC_ACCENT[selectedArc]             || '#e8305a'
  const sessionAccent   = ARC_ACCENT[session?.arc_type || ''] || '#e8305a'
  const totalTracks     = session?.total_tracks ?? 0
  const progressPct     = totalTracks > 0 ? (currentPosition / totalTracks) * 100 : 0

  /* ─── HOME ──────────────────────────────────────────────── */
  if (view === 'home') {
    return (
      <div style={{ position: 'relative', minHeight: '100vh', zIndex: 10 }}>
        <div className="orb orb-pink" />
        <div className="orb orb-teal" />
        <div className="orb orb-blue" />

        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          padding: '60px 20px 80px', width: '100%', maxWidth: 480, margin: '0 auto',
        }}>
          {/* Wordmark */}
          <div className="fade-up" style={{ textAlign: 'center', marginBottom: 40 }}>
            <h1
              className="heading-hero"
              style={{
                fontSize: 'clamp(4rem, 14vw, 6.5rem)',
                background: `linear-gradient(135deg, ${homeAccent} 0%, rgba(255,255,255,0.92) 55%)`,
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
                transition: 'background 0.5s ease',
              }}
            >
              SOMA
            </h1>
            <p className="label-dim" style={{ marginTop: 8, letterSpacing: '0.3em' }}>
              Generative DJ Intelligence
            </p>
          </div>

          {/* Error banner */}
          {error && (
            <div className="glass-card fade-up" style={{
              width: '100%', padding: '14px 18px',
              borderColor: 'rgba(232,48,90,0.35)', marginBottom: 20,
            }}>
              <p style={{ fontSize: 12, color: '#e8305a', lineHeight: 1.55 }}>{error}</p>
            </div>
          )}

          <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 24 }}>

            {/* Arc type list */}
            <div className="fade-up" style={{ animationDelay: '40ms' }}>
              <p className="label-dim" style={{ marginBottom: 14 }}>Session Type</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }} className="stagger">
                {arcTypes.length === 0 && !error && Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="skeleton" style={{ height: 58, borderRadius: 16 }} />
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
                        display: 'flex', alignItems: 'center', gap: 14,
                        padding: '12px 16px', borderRadius: 16,
                        background: active ? `${color}0d` : 'rgba(255,255,255,0.022)',
                        border: `1px solid ${active ? color + '35' : 'rgba(255,255,255,0.055)'}`,
                        boxShadow: active ? `0 0 24px ${color}10, 0 4px 20px rgba(0,0,0,0.3)` : 'none',
                        transition: 'all 0.22s ease', textAlign: 'left',
                        cursor: 'pointer', width: '100%',
                      }}
                    >
                      <MiniArc arcKey={arc.key} color={color} active={active} />

                      <div style={{ flex: 1, minWidth: 0 }}>
                        <span className="heading-display" style={{
                          fontSize: 10,
                          color: active ? color : 'rgba(255,255,255,0.55)',
                          transition: 'color 0.22s ease',
                          display: 'block', marginBottom: 2,
                        }}>
                          {arc.label}
                        </span>
                        <p style={{
                          fontSize: 10, color: 'rgba(255,255,255,0.26)',
                          fontFamily: 'DM Sans', fontWeight: 300,
                          overflow: 'hidden', textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap', lineHeight: 1.4,
                        }}>
                          {arc.description}
                        </p>
                      </div>

                      <span className="dot-matrix" style={{
                        fontSize: 10, flexShrink: 0,
                        color: active ? color : 'rgba(255,255,255,0.2)',
                        transition: 'color 0.22s ease',
                      }}>
                        {arc.bpm_start}–{arc.bpm_peak}
                      </span>
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Duration slider */}
            <div className="fade-up" style={{ animationDelay: '80ms' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 14 }}>
                <p className="label-dim">Duration</p>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 5 }}>
                  <span className="dot-matrix" style={{
                    fontSize: 22, color: homeAccent,
                    textShadow: `0 0 12px ${homeAccent}80`,
                    transition: 'color 0.4s ease, text-shadow 0.4s ease',
                  }}>
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
                width: '100%', fontSize: 11, letterSpacing: '0.3em',
                padding: '20px', borderRadius: 18,
                background: loading
                  ? 'rgba(255,255,255,0.06)'
                  : `linear-gradient(135deg, ${homeAccent}cc 0%, ${homeAccent}88 100%)`,
                border: `1px solid ${homeAccent}28`,
                boxShadow: loading ? 'none' : `0 0 48px ${homeAccent}1a, 0 8px 28px rgba(0,0,0,0.35)`,
                opacity: loading ? 0.65 : 1,
                cursor: loading ? 'not-allowed' : 'pointer',
                transition: 'all 0.28s ease',
                animationDelay: '120ms',
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
    <div style={{ position: 'relative', minHeight: '100vh', zIndex: 10 }}>
      <div className="orb orb-pink" style={{ opacity: 0.22 }} />
      <div className="orb orb-teal" style={{ opacity: 0.14 }} />

      <div className="fade-in" style={{ maxWidth: 1020, margin: '0 auto', padding: '16px 14px 60px' }}>

        {/* Error */}
        {error && (
          <div className="glass-card" style={{ padding: '12px 16px', borderColor: 'rgba(232,48,90,0.35)', marginBottom: 14 }}>
            <p style={{ fontSize: 12, color: '#e8305a' }}>{error}</p>
          </div>
        )}

        {/* Top bar */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <button
            onClick={() => setView('home')}
            className="label-mid"
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '8px 14px 8px 10px', borderRadius: 12,
              background: 'transparent', border: '1px solid transparent',
              cursor: 'pointer', transition: 'all 0.18s ease',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = 'transparent' }}
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <path d="M8 10L4 6l4-4" />
            </svg>
            Back
          </button>

          <h1
            className="heading-hero"
            style={{
              fontSize: 'clamp(2rem, 6vw, 3.2rem)',
              background: `linear-gradient(135deg, ${sessionAccent} 0%, rgba(255,255,255,0.92) 60%)`,
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
              transition: 'background 0.5s ease',
              lineHeight: 1,
            }}
          >
            SOMA
          </h1>

          <span className="dot-matrix" style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)' }}>
            {currentPosition}&thinsp;/&thinsp;{totalTracks}
          </span>
        </div>

        {/* Session progress line */}
        {totalTracks > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ height: 2, background: 'rgba(255,255,255,0.05)', borderRadius: 2 }}>
              <div style={{
                height: '100%', width: `${progressPct}%`,
                background: `linear-gradient(90deg, ${sessionAccent}66, ${sessionAccent})`,
                borderRadius: 2, boxShadow: `0 0 8px ${sessionAccent}44`,
                transition: 'width 0.7s cubic-bezier(0.22,1,0.36,1)',
              }} />
            </div>
          </div>
        )}

        {/* 2-col on desktop */}
        <div className="session-grid">

          {/* ── LEFT: Now Playing ── */}
          <div
            className="glass-card"
            style={{
              padding: '26px 24px',
              boxShadow: `0 0 80px ${sessionAccent}0c, 0 24px 64px rgba(0,0,0,0.44)`,
              borderColor: `${sessionAccent}16`,
            }}
          >
            {done ? (
              <div className="scale-in" style={{ textAlign: 'center', padding: '52px 0' }}>
                <p className="heading-display" style={{ fontSize: 22, color: sessionAccent, letterSpacing: '0.2em', marginBottom: 10 }}>
                  Session Complete
                </p>
                <p className="label-dim" style={{ marginBottom: 40 }}>Your set has ended.</p>
                <button
                  onClick={() => { setView('home'); setSession(null); setNowPlaying(null); setDone(false) }}
                  className="heading-display"
                  style={{
                    fontSize: 10, letterSpacing: '0.24em',
                    padding: '14px 38px', borderRadius: 14,
                    background: `${sessionAccent}10`, border: `1px solid ${sessionAccent}30`,
                    cursor: 'pointer', color: 'rgba(255,255,255,0.85)',
                    transition: 'background 0.2s ease',
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = `${sessionAccent}1e`)}
                  onMouseLeave={e => (e.currentTarget.style.background = `${sessionAccent}10`)}
                >
                  New Session
                </button>
              </div>

            ) : scanning && !nowPlaying ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '60px 0', gap: 16 }}>
                <TransitionScanner scanning={true} label="Selecting next track" />
              </div>

            ) : nowPlaying ? (
              <div key={nowPlaying.position} className="track-enter">

                {/* Row: Track info + BPM Knob */}
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 20, marginBottom: 18 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p className="label-dim" style={{ marginBottom: 10 }}>Now Playing</p>
                    <h2
                      className="font-display"
                      style={{
                        fontSize: 'clamp(1.6rem, 4.5vw, 2.4rem)',
                        fontWeight: 300,
                        color: 'rgba(255,255,255,0.96)',
                        letterSpacing: '-0.015em',
                        lineHeight: 1.12,
                        marginBottom: 8,
                        overflow: 'hidden',
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical' as const,
                      }}
                    >
                      {nowPlaying.title}
                    </h2>
                    <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.34)', fontFamily: 'DM Sans', fontWeight: 300, letterSpacing: '0.02em' }}>
                      {nowPlaying.artist}
                    </p>

                    {/* Target BPM badge */}
                    <div style={{ marginTop: 12 }}>
                      <span style={{
                        fontFamily: 'Share Tech Mono, monospace', fontSize: 10,
                        padding: '4px 10px', borderRadius: 8,
                        background: `${sessionAccent}0d`, border: `1px solid ${sessionAccent}25`,
                        color: sessionAccent,
                      }}>
                        target {Math.round(nowPlaying.target_bpm)} bpm
                      </span>
                    </div>
                  </div>

                  {/* BPM Knob */}
                  <BpmKnob
                    bpm={Math.round(nowPlaying.bpm)}
                    targetBpm={Math.round(nowPlaying.target_bpm)}
                    color={sessionAccent}
                  />
                </div>

                {/* Frequency Visualizer */}
                <div style={{
                  borderRadius: 12,
                  background: 'rgba(0,0,0,0.2)',
                  border: `1px solid ${sessionAccent}14`,
                  padding: '12px 14px',
                  marginBottom: 18,
                  overflow: 'hidden',
                }}>
                  <FrequencyVisualizer
                    audioRef={audioRef}
                    playing={isPlaying}
                    color={sessionAccent}
                  />
                </div>

                <div className="soma-divider" style={{ marginBottom: 18 }} />

                {/* Audio player */}
                <div style={{ marginBottom: 18 }}>
                  <AudioPlayer
                    audioUrl={nowPlaying.audio_url}
                    onEnded={() => handleEvent('completed')}
                    audioRef={audioRef}
                    onPlayingChange={setIsPlaying}
                  />
                </div>

                {/* Skip + Star rating */}
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <button
                    onClick={() => handleEvent('skipped')}
                    className="label-mid"
                    style={{
                      padding: '12px 20px', borderRadius: 14,
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.07)',
                      fontSize: 10, letterSpacing: '0.1em', textTransform: 'uppercase',
                      fontFamily: 'DM Sans', cursor: 'pointer', flexShrink: 0,
                      transition: 'background 0.18s ease',
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.08)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.04)')}
                  >
                    Skip
                  </button>

                  <div
                    style={{ display: 'flex', flex: 1, gap: 5 }}
                    onMouseLeave={() => setHoverRating(0)}
                  >
                    {[1, 2, 3, 4, 5].map(r => (
                      <button
                        key={r}
                        onClick={() => handleEvent('completed', r)}
                        onMouseEnter={() => setHoverRating(r)}
                        style={{
                          flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
                          padding: '12px 0', borderRadius: 14,
                          background: r <= hoverRating ? `${sessionAccent}18` : `${sessionAccent}07`,
                          border: `1px solid ${r <= hoverRating ? sessionAccent + '40' : sessionAccent + '12'}`,
                          cursor: 'pointer', transition: 'all 0.12s ease',
                        }}
                      >
                        <StarIcon filled={r <= hoverRating} color={sessionAccent} />
                      </button>
                    ))}
                  </div>
                </div>

                {scanning && (
                  <div style={{ display: 'flex', justifyContent: 'center', marginTop: 20 }}>
                    <TransitionScanner scanning={true} />
                  </div>
                )}
              </div>
            ) : null}
          </div>

          {/* ── RIGHT: Context sidebar ── */}
          {session && !done && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>

              {/* Queue */}
              <div className="glass-card" style={{ padding: '18px 20px' }}>
                <SessionQueue tracks={session.tracks} currentPosition={currentPosition} />
              </div>

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

            </div>
          )}
        </div>
      </div>
    </div>
  )
}
