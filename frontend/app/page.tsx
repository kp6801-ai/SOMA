'use client'

import { useState, useEffect, useCallback } from 'react'
import { api, ArcType, Session, NowPlaying } from '@/lib/api'
import CamelotWheel from '@/components/CamelotWheel'
import EnergyArc from '@/components/EnergyArc'
import TransitionScanner from '@/components/TransitionScanner'
import AudioPlayer from '@/components/AudioPlayer'
import SessionQueue from '@/components/SessionQueue'

type View = 'home' | 'session'

export default function SomaDashboard() {
  const [view, setView] = useState<View>('home')
  const [arcTypes, setArcTypes] = useState<ArcType[]>([])
  const [selectedArc, setSelectedArc] = useState<string>('')
  const [duration, setDuration] = useState(60)
  const [loading, setLoading] = useState(false)
  const [session, setSession] = useState<Session | null>(null)
  const [nowPlaying, setNowPlaying] = useState<NowPlaying | null>(null)
  const [scanning, setScanning] = useState(false)
  const [done, setDone] = useState(false)

  useEffect(() => {
    api.getArcTypes().then(r => {
      setArcTypes(r.arc_types)
      setSelectedArc(r.arc_types[0]?.key || '')
    }).catch(console.error)
  }, [])

  const startSession = async () => {
    if (!selectedArc) return
    setLoading(true)
    try {
      const s = await api.createSession(selectedArc, duration)
      setSession(s)
      setView('session')
      await loadNextTrack(s.session_id)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const loadNextTrack = useCallback(async (sessionId: number) => {
    setScanning(true)
    try {
      const next = await api.nextTrack(sessionId)
      if (next.done) { setDone(true); setNowPlaying(null) }
      else setNowPlaying(next)
    } finally {
      setScanning(false)
    }
  }, [])

  const handleEvent = async (event: 'completed' | 'skipped', rating?: number) => {
    if (!session || !nowPlaying) return
    await api.recordEvent(session.session_id, event, nowPlaying.position, rating)
    // Refresh session to update statuses
    const updated = await api.getSession(session.session_id)
    setSession(updated)
    await loadNextTrack(session.session_id)
  }

  const currentPosition = nowPlaying?.position ?? 0

  /* ── HOME SCREEN ── */
  if (view === 'home') {
    return (
      <div className="relative min-h-screen flex flex-col items-center justify-center px-6 py-16 z-10">
        {/* Wordmark */}
        <div className="mb-16 text-center">
          <h1 className="heading-display text-5xl mb-2" style={{ letterSpacing: '0.3em' }}>
            SOMA
          </h1>
          <p className="label-dim">Generative DJ Intelligence</p>
        </div>

        {/* Arc selector */}
        <div className="w-full max-w-lg space-y-6">
          <div>
            <p className="label-dim mb-3">Session Type</p>
            <div className="grid grid-cols-2 gap-2">
              {arcTypes.map(arc => (
                <button
                  key={arc.key}
                  onClick={() => setSelectedArc(arc.key)}
                  className="glass-card px-4 py-4 text-left transition-all"
                  style={{
                    border: selectedArc === arc.key
                      ? '1px solid rgba(232,48,90,0.5)'
                      : '1px solid rgba(255,255,255,0.08)',
                    boxShadow: selectedArc === arc.key
                      ? '0 0 20px rgba(232,48,90,0.1)'
                      : 'none',
                  }}
                >
                  <p className="heading-display text-sm mb-1" style={{ letterSpacing: '0.1em' }}>
                    {arc.label}
                  </p>
                  <p className="label-dim" style={{ fontSize: 10 }}>{arc.description}</p>
                  <div className="flex gap-3 mt-2">
                    <span className="dot-matrix text-xs dot-matrix-glow-bpm">{arc.bpm_start}</span>
                    <span className="label-dim">→</span>
                    <span className="dot-matrix text-xs dot-matrix-glow-bpm">{arc.bpm_peak}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Duration slider */}
          <div>
            <div className="flex justify-between mb-2">
              <p className="label-dim">Duration</p>
              <span className="dot-matrix text-sm dot-matrix-glow-compat">{duration} min</span>
            </div>
            <input
              type="range" min={15} max={180} step={15}
              value={duration}
              onChange={e => setDuration(Number(e.target.value))}
              className="w-full"
              style={{ accentColor: '#4488ff' }}
            />
            <div className="flex justify-between mt-1">
              <span className="label-dim">15 min</span>
              <span className="label-dim">3 hr</span>
            </div>
          </div>

          {/* Start button */}
          <button
            onClick={startSession}
            disabled={loading || !selectedArc}
            className="w-full py-4 rounded-2xl heading-display text-sm"
            style={{
              background: 'linear-gradient(135deg, #e8305a, #c0195e)',
              boxShadow: '0 0 30px rgba(232,48,90,0.25)',
              letterSpacing: '0.2em',
              opacity: loading ? 0.6 : 1,
              cursor: loading ? 'not-allowed' : 'pointer',
              transition: 'opacity 0.2s ease, box-shadow 0.2s ease',
            }}
          >
            {loading ? 'Planning Session...' : 'Start Session'}
          </button>
        </div>
      </div>
    )
  }

  /* ── SESSION SCREEN ── */
  return (
    <div className="relative min-h-screen z-10 px-4 py-8 max-w-2xl mx-auto space-y-4">

      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <button onClick={() => setView('home')} className="label-dim hover:text-white transition-colors">
          ← Back
        </button>
        <span className="heading-display text-xs" style={{ letterSpacing: '0.2em' }}>SOMA</span>
        <span className="label-dim">
          {currentPosition}/{session?.total_tracks ?? 0}
        </span>
      </div>

      {/* Now Playing — main card */}
      <div className="glass-card glow-bpm p-6">
        {done ? (
          <div className="text-center py-8">
            <p className="heading-display text-2xl mb-2">Session Complete</p>
            <p className="label-dim mb-6">Your set has ended.</p>
            <button
              onClick={() => setView('home')}
              className="px-8 py-3 rounded-xl"
              style={{ background: 'rgba(232,48,90,0.15)', border: '1px solid rgba(232,48,90,0.3)' }}
            >
              <span className="heading-display text-sm">New Session</span>
            </button>
          </div>
        ) : scanning && !nowPlaying ? (
          <div className="flex flex-col items-center py-8 gap-4">
            <TransitionScanner scanning={true} label="Selecting next track" />
          </div>
        ) : nowPlaying ? (
          <>
            {/* Track info */}
            <div className="flex items-start justify-between mb-6">
              <div className="flex-1 min-w-0 pr-4">
                <p className="label-dim mb-1">Now Playing</p>
                <h2 className="text-xl font-light mb-1 leading-tight" style={{ color: 'rgba(255,255,255,0.92)' }}>
                  {nowPlaying.title}
                </h2>
                <p className="label-dim">{nowPlaying.artist}</p>
              </div>
              <TransitionScanner scanning={scanning} />
            </div>

            {/* Metrics row */}
            <div className="flex gap-4 mb-6">
              <div className="glass-card glow-bpm px-4 py-3 flex-1 text-center">
                <p className="label-dim mb-1">BPM</p>
                <span className="dot-matrix dot-matrix-glow-bpm text-3xl count-up">
                  {Math.round(nowPlaying.bpm)}
                </span>
              </div>
              <div className="glass-card glow-key px-4 py-3 flex-1 text-center">
                <p className="label-dim mb-1">Key</p>
                <span className="dot-matrix dot-matrix-glow-key text-3xl count-up">
                  {nowPlaying.camelot && nowPlaying.camelot !== 'Unknown'
                    ? nowPlaying.camelot : '—'}
                </span>
              </div>
              <div className="glass-card glow-compat px-4 py-3 flex-1 text-center">
                <p className="label-dim mb-1">Target</p>
                <span className="dot-matrix dot-matrix-glow-compat text-3xl count-up">
                  {Math.round(nowPlaying.target_bpm)}
                </span>
              </div>
            </div>

            {/* Audio player */}
            <div className="mb-6">
              <AudioPlayer
                audioUrl={nowPlaying.audio_url}
                onEnded={() => handleEvent('completed')}
              />
            </div>

            {/* Action buttons */}
            <div className="flex gap-3">
              <button
                onClick={() => handleEvent('skipped')}
                className="flex-1 py-3 rounded-xl label-dim hover:text-white transition-colors"
                style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}
              >
                Skip
              </button>
              {[1,2,3,4,5].map(r => (
                <button
                  key={r}
                  onClick={() => handleEvent('completed', r)}
                  className="flex-1 py-3 rounded-xl label-dim hover:text-white transition-colors"
                  style={{ background: 'rgba(232,48,90,0.06)', border: '1px solid rgba(232,48,90,0.15)' }}
                >
                  {r}★
                </button>
              ))}
            </div>
          </>
        ) : null}
      </div>

      {/* Camelot + Energy row */}
      {session && (
        <div className="grid grid-cols-2 gap-4">
          <div className="glass-card glow-key p-5 flex flex-col items-center">
            <p className="label-dim mb-3">Camelot Position</p>
            <CamelotWheel
              activeCode={nowPlaying?.camelot && nowPlaying.camelot !== 'Unknown'
                ? nowPlaying.camelot : null}
              size={200}
            />
          </div>
          <div className="glass-card glow-compat p-5">
            <p className="label-dim mb-3">BPM Arc</p>
            <EnergyArc tracks={session.tracks} currentPosition={currentPosition} />
            <div className="flex justify-between mt-3">
              <div>
                <span className="dot-matrix text-lg dot-matrix-glow-bpm">{session.bpm_start}</span>
                <p className="label-dim">start</p>
              </div>
              <div className="text-center">
                <span className="dot-matrix text-lg dot-matrix-glow-bpm">{session.bpm_peak}</span>
                <p className="label-dim">peak</p>
              </div>
              <div className="text-right">
                <span className="dot-matrix text-lg dot-matrix-glow-bpm">{session.bpm_end}</span>
                <p className="label-dim">end</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Session queue */}
      {session && (
        <div className="glass-card p-5">
          <SessionQueue tracks={session.tracks} currentPosition={currentPosition} />
        </div>
      )}
    </div>
  )
}
