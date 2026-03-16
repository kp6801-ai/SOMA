'use client'

import { useEffect, useRef, useState } from 'react'

interface Props {
  audioUrl: string | null
  onEnded?: () => void
  /** If provided, the parent controls the audio element via this ref */
  audioRef?: React.RefObject<HTMLAudioElement | null>
  /** Called whenever play/pause state changes */
  onPlayingChange?: (playing: boolean) => void
}

export default function AudioPlayer({ audioUrl, onEnded, audioRef: externalRef, onPlayingChange }: Props) {
  const internalRef = useRef<HTMLAudioElement>(null)
  const audioRef = externalRef ?? internalRef

  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(0)
  const [duration, setDuration] = useState(0)
  const [autoplayBlocked, setAutoplayBlocked] = useState(false)

  const setPlayState = (v: boolean) => {
    setPlaying(v)
    onPlayingChange?.(v)
  }

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return
    if (audioUrl) {
      audio.load()
      audio.play()
        .then(() => { setPlayState(true); setAutoplayBlocked(false) })
        .catch(() => { setPlayState(false); setAutoplayBlocked(true) })
    } else {
      audio.pause()
      setPlayState(false)
      setProgress(0)
      setAutoplayBlocked(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audioUrl])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return
    const onTime = () => setProgress(audio.currentTime)
    const onMeta = () => setDuration(audio.duration)
    const onEnd  = () => { setPlayState(false); onEnded?.() }
    audio.addEventListener('timeupdate', onTime)
    audio.addEventListener('loadedmetadata', onMeta)
    audio.addEventListener('ended', onEnd)
    return () => {
      audio.removeEventListener('timeupdate', onTime)
      audio.removeEventListener('loadedmetadata', onMeta)
      audio.removeEventListener('ended', onEnd)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onEnded])

  const togglePlay = () => {
    const audio = audioRef.current
    if (!audio || !audioUrl) return
    if (playing) {
      audio.pause()
      setPlayState(false)
    } else {
      audio.play()
        .then(() => { setPlayState(true); setAutoplayBlocked(false) })
        .catch(() => setPlayState(false))
    }
  }

  const pct = duration ? (progress / duration) * 100 : 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, width: '100%' }}>
      <audio ref={audioRef as React.RefObject<HTMLAudioElement>} src={audioUrl || ''} preload="metadata" />

      {/* Progress bar */}
      <div
        style={{ position: 'relative', width: '100%', height: 3, borderRadius: 2, background: 'rgba(255,255,255,0.08)', cursor: 'pointer' }}
        onClick={e => {
          const rect = e.currentTarget.getBoundingClientRect()
          const p = (e.clientX - rect.left) / rect.width
          if (audioRef.current) audioRef.current.currentTime = p * duration
        }}
      >
        <div style={{
          position: 'absolute', left: 0, top: 0, height: '100%',
          width: `${pct}%`,
          background: 'linear-gradient(90deg, #e8305a, #c0195e)',
          boxShadow: '0 0 8px rgba(232,48,90,0.6)',
          borderRadius: 2,
          transition: 'width 0.5s linear',
        }} />
        <div style={{
          position: 'absolute', top: '50%',
          left: `${pct}%`,
          transform: 'translate(-50%, -50%)',
          width: 10, height: 10, borderRadius: '50%',
          background: '#e8305a',
          boxShadow: '0 0 6px #e8305a',
        }} />
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span className="label-dim">{fmt(progress)}</span>

        <button
          onClick={togglePlay}
          disabled={!audioUrl}
          style={{
            width: 40, height: 40, borderRadius: '50%',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: audioUrl ? 'rgba(232,48,90,0.15)' : 'rgba(255,255,255,0.05)',
            border: '1px solid rgba(232,48,90,0.3)',
            cursor: audioUrl ? 'pointer' : 'not-allowed',
            transition: 'background 0.2s ease',
          }}
        >
          {playing ? (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="rgba(255,255,255,0.8)">
              <rect x="2" y="1" width="4" height="12" rx="1" />
              <rect x="8" y="1" width="4" height="12" rx="1" />
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="rgba(255,255,255,0.8)">
              <polygon points="2,1 13,7 2,13" />
            </svg>
          )}
        </button>

        <span className="label-dim">{fmt(duration)}</span>
      </div>

      {autoplayBlocked && !playing && audioUrl && (
        <p className="label-dim" style={{ textAlign: 'center', color: '#ffaa22', opacity: 0.8 }}>
          Tap ▶ to start playback
        </p>
      )}

      {!audioUrl && (
        <p className="label-dim" style={{ textAlign: 'center', opacity: 0.35 }}>
          Audio not available for this track
        </p>
      )}
    </div>
  )
}

function fmt(s: number) {
  if (!s || isNaN(s)) return '0:00'
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60).toString().padStart(2, '0')
  return `${m}:${sec}`
}
