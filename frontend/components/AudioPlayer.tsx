'use client'

import { useEffect, useRef, useState } from 'react'

interface Props {
  audioUrl: string | null
  onEnded?: () => void
}

export default function AudioPlayer({ audioUrl, onEnded }: Props) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(0)
  const [duration, setDuration] = useState(0)

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return
    if (audioUrl) {
      audio.load()
      audio.play().then(() => setPlaying(true)).catch(() => setPlaying(false))
    } else {
      audio.pause()
      setPlaying(false)
      setProgress(0)
    }
  }, [audioUrl])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return
    const onTime = () => setProgress(audio.currentTime)
    const onMeta = () => setDuration(audio.duration)
    audio.addEventListener('timeupdate', onTime)
    audio.addEventListener('loadedmetadata', onMeta)
    audio.addEventListener('ended', () => { setPlaying(false); onEnded?.() })
    return () => {
      audio.removeEventListener('timeupdate', onTime)
      audio.removeEventListener('loadedmetadata', onMeta)
    }
  }, [onEnded])

  const togglePlay = () => {
    const audio = audioRef.current
    if (!audio || !audioUrl) return
    if (playing) { audio.pause(); setPlaying(false) }
    else { audio.play(); setPlaying(true) }
  }

  const pct = duration ? (progress / duration) * 100 : 0

  return (
    <div className="flex flex-col gap-3 w-full">
      <audio ref={audioRef} src={audioUrl || ''} preload="metadata" />

      {/* Progress bar */}
      <div
        className="relative w-full h-1 rounded-full cursor-pointer"
        style={{ background: 'rgba(255,255,255,0.08)' }}
        onClick={e => {
          const rect = e.currentTarget.getBoundingClientRect()
          const pct = (e.clientX - rect.left) / rect.width
          if (audioRef.current) audioRef.current.currentTime = pct * duration
        }}
      >
        <div
          className="absolute left-0 top-0 h-full rounded-full"
          style={{
            width: `${pct}%`,
            background: 'linear-gradient(90deg, #e8305a, #c0195e)',
            boxShadow: '0 0 8px rgba(232,48,90,0.6)',
            transition: 'width 0.5s linear',
          }}
        />
        {/* Marker */}
        <div
          className="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full"
          style={{
            left: `${pct}%`,
            background: '#e8305a',
            boxShadow: '0 0 6px #e8305a',
            transform: 'translate(-50%, -50%)',
          }}
        />
      </div>

      {/* Controls */}
      <div className="flex items-center justify-between">
        <span className="label-dim">{fmt(progress)}</span>

        <button
          onClick={togglePlay}
          disabled={!audioUrl}
          className="w-10 h-10 rounded-full flex items-center justify-center"
          style={{
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

      {!audioUrl && (
        <p className="label-dim text-center" style={{ opacity: 0.35 }}>
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
