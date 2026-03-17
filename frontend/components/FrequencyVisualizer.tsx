'use client'

import { useEffect, useRef } from 'react'

interface Props {
  audioRef: React.RefObject<HTMLAudioElement | null>
  playing: boolean
  color: string
}

function parseColor(color: string): [number, number, number] {
  const hex = color.match(/^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i)
  if (hex) return [parseInt(hex[1], 16), parseInt(hex[2], 16), parseInt(hex[3], 16)]
  const rgb = color.match(/rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)/)
  if (rgb) return [parseInt(rgb[1]), parseInt(rgb[2]), parseInt(rgb[3])]
  return [255, 255, 255]
}

export default function FrequencyVisualizer({ audioRef, playing, color }: Props) {
  const canvasRef   = useRef<HTMLCanvasElement>(null)
  const ctxRef      = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const sourceRef   = useRef<MediaElementAudioSourceNode | null>(null)
  const rafRef      = useRef<number | null>(null)
  const decayRef    = useRef<Float32Array | null>(null)

  // ── Set up Web Audio graph (runs when playing first becomes true) ──────────
  useEffect(() => {
    if (!playing) return
    const audio = audioRef.current
    if (!audio) return
    if (ctxRef.current) {
      // Already set up — just resume if suspended
      if (ctxRef.current.state === 'suspended') ctxRef.current.resume().catch(() => {})
      return
    }

    const AudioCtx =
      window.AudioContext ||
      (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!AudioCtx) return

    try {
      const ctx      = new AudioCtx()
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 512
      analyser.smoothingTimeConstant = 0.82

      const source = ctx.createMediaElementSource(audio)
      source.connect(analyser)
      analyser.connect(ctx.destination)

      ctxRef.current      = ctx
      analyserRef.current = analyser
      sourceRef.current   = source
      decayRef.current    = new Float32Array(analyser.frequencyBinCount)

      if (ctx.state === 'suspended') ctx.resume().catch(() => {})
    } catch (e) {
      console.warn('FrequencyVisualizer setup failed:', e)
    }

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      try {
        sourceRef.current?.disconnect()
        analyserRef.current?.disconnect()
        ctxRef.current?.close()
      } catch {}
      ctxRef.current = analyserRef.current = sourceRef.current = null
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing])

  // ── Draw loop ──────────────────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const [r, g, b] = parseColor(color)

    function draw() {
      rafRef.current = requestAnimationFrame(draw)
      const ctx2d = canvas!.getContext('2d')
      if (!ctx2d) return

      const W = canvas!.width
      const H = canvas!.height
      ctx2d.clearRect(0, 0, W, H)

      const analyser = analyserRef.current
      const decay    = decayRef.current

      const binCount = analyser ? analyser.frequencyBinCount : 64
      if (!decay || decay.length !== binCount) {
        decayRef.current = new Float32Array(binCount)
        return
      }

      if (analyser && playing) {
        const byteData = new Uint8Array(binCount)
        analyser.getByteFrequencyData(byteData)
        for (let i = 0; i < binCount; i++) decay[i] = byteData[i]
      } else {
        // Decay bars when paused
        for (let i = 0; i < binCount; i++) {
          decay[i] *= 0.88
          if (decay[i] < 0.5) decay[i] = 0
        }
      }

      const barW = 3
      const gap  = 2
      const step = barW + gap
      const numBars = Math.floor(W / step)
      const sampleRate = ctxRef.current?.sampleRate ?? 44100
      const hzPerBin = (sampleRate / 2) / binCount

      for (let i = 0; i < numBars; i++) {
        const binIndex = Math.floor((i / numBars) * binCount)
        const mag = decay[binIndex] / 255

        const barH  = Math.max(2, mag * (H - 4))
        const x     = i * step
        const y     = H - barH

        const hz = binIndex * hzPerBin
        const isMid = hz >= 80 && hz <= 5000
        const opacity = Math.min(1, mag * (isMid ? 1.0 : 0.5) + 0.04)

        const radius = Math.min(barW / 2, 2)
        ctx2d.beginPath()
        ctx2d.moveTo(x + radius, y)
        ctx2d.lineTo(x + barW - radius, y)
        ctx2d.quadraticCurveTo(x + barW, y, x + barW, y + radius)
        ctx2d.lineTo(x + barW, H)
        ctx2d.lineTo(x, H)
        ctx2d.lineTo(x, y + radius)
        ctx2d.quadraticCurveTo(x, y, x + radius, y)
        ctx2d.closePath()

        ctx2d.fillStyle = `rgba(${r},${g},${b},${opacity.toFixed(3)})`
        ctx2d.fill()

        if (isMid && mag > 0.35) {
          ctx2d.shadowBlur  = 8
          ctx2d.shadowColor = `rgba(${r},${g},${b},${(mag * 0.55).toFixed(3)})`
          ctx2d.fill()
          ctx2d.shadowBlur  = 0
        }
      }
    }

    draw()
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current) }
  }, [playing, color])

  // ── Keep canvas pixel-width in sync with container ────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ro = new ResizeObserver(entries => {
      for (const e of entries) canvas.width = e.contentRect.width
    })
    ro.observe(canvas.parentElement || canvas)
    if (canvas.parentElement) canvas.width = canvas.parentElement.offsetWidth
    return () => ro.disconnect()
  }, [])

  return (
    <canvas
      ref={canvasRef}
      height={72}
      style={{ width: '100%', height: 72, display: 'block' }}
    />
  )
}
