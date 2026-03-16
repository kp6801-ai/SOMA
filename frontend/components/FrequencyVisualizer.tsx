'use client'

import { useEffect, useRef } from 'react'

interface Props {
  audioRef: React.RefObject<HTMLAudioElement>
  playing: boolean
  color: string
}

// Parse a hex or rgb color string into [r, g, b] components
function parseColor(color: string): [number, number, number] {
  // Try hex
  const hex = color.match(/^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i)
  if (hex) {
    return [parseInt(hex[1], 16), parseInt(hex[2], 16), parseInt(hex[3], 16)]
  }
  // Try rgb(r, g, b)
  const rgb = color.match(/rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)/)
  if (rgb) {
    return [parseInt(rgb[1]), parseInt(rgb[2]), parseInt(rgb[3])]
  }
  // Fallback: white
  return [255, 255, 255]
}

export default function FrequencyVisualizer({ audioRef, playing, color }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const contextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const sourceRef = useRef<MediaElementAudioSourceNode | null>(null)
  const animFrameRef = useRef<number | null>(null)
  const decayDataRef = useRef<Float32Array | null>(null)

  // Set up AudioContext and AnalyserNode once the audio element is available
  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    // Check for Web Audio API support
    if (typeof window === 'undefined' || !('AudioContext' in window || 'webkitAudioContext' in window)) {
      return
    }

    // Only create the context once per audio element
    if (contextRef.current) return

    try {
      const AudioCtxClass =
        window.AudioContext ||
        (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext

      if (!AudioCtxClass) return

      const ctx = new AudioCtxClass()
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 256
      analyser.smoothingTimeConstant = 0.8

      const source = ctx.createMediaElementSource(audio)
      source.connect(analyser)
      analyser.connect(ctx.destination)

      contextRef.current = ctx
      analyserRef.current = analyser
      sourceRef.current = source

      // Initialize decay buffer
      decayDataRef.current = new Float32Array(analyser.frequencyBinCount)
    } catch (err) {
      // Graceful degradation — visualizer won't render but audio still works
      console.warn('FrequencyVisualizer: Web Audio API setup failed', err)
    }

    return () => {
      if (animFrameRef.current !== null) {
        cancelAnimationFrame(animFrameRef.current)
        animFrameRef.current = null
      }
      try {
        sourceRef.current?.disconnect()
        analyserRef.current?.disconnect()
        contextRef.current?.close()
      } catch {
        // ignore cleanup errors
      }
      contextRef.current = null
      analyserRef.current = null
      sourceRef.current = null
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audioRef])

  // Resume AudioContext on first play (browsers require user gesture)
  useEffect(() => {
    if (playing && contextRef.current?.state === 'suspended') {
      contextRef.current.resume().catch(() => {})
    }
  }, [playing])

  // Animation loop
  useEffect(() => {
    const canvas = canvasRef.current
    const analyser = analyserRef.current
    if (!canvas) return

    const [r, g, b] = parseColor(color)
    const binCount = analyser ? analyser.frequencyBinCount : 128
    const byteData = new Uint8Array(binCount)

    if (!decayDataRef.current || decayDataRef.current.length !== binCount) {
      decayDataRef.current = new Float32Array(binCount)
    }
    const decayData = decayDataRef.current

    // Approximate sample rate for frequency-to-bin mapping (default 44100)
    const sampleRate = contextRef.current?.sampleRate ?? 44100
    const nyquist = sampleRate / 2
    const hzPerBin = nyquist / binCount

    function draw() {
      animFrameRef.current = requestAnimationFrame(draw)

      const ctx2d = canvas!.getContext('2d')
      if (!ctx2d) return

      const W = canvas!.width
      const H = canvas!.height

      ctx2d.clearRect(0, 0, W, H)

      if (analyser && playing) {
        analyser.getByteFrequencyData(byteData)
        for (let i = 0; i < binCount; i++) {
          decayData[i] = byteData[i]
        }
      } else {
        // Decay toward zero when paused/stopped
        for (let i = 0; i < binCount; i++) {
          decayData[i] *= 0.92
          if (decayData[i] < 0.5) decayData[i] = 0
        }
      }

      const barW = 3
      const gap = 2
      const step = barW + gap
      const numBars = Math.floor(W / step)

      for (let i = 0; i < numBars; i++) {
        // Map bar index to frequency bin
        const binIndex = Math.floor((i / numBars) * binCount)
        const magnitude = decayData[binIndex] / 255 // 0..1

        const barH = Math.max(1, magnitude * H)
        const x = i * step

        // Glow boost for mid frequencies (100–4000 Hz)
        const hz = binIndex * hzPerBin
        const isMid = hz >= 100 && hz <= 4000
        const glowBoost = isMid ? 1.0 : 0.55
        const opacity = Math.min(1, magnitude * glowBoost + 0.05)

        const y = H - barH

        // Draw bar with rounded top
        ctx2d.beginPath()
        const radius = Math.min(barW / 2, barH / 2, 2)
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

        // Subtle glow for mid frequencies
        if (isMid && magnitude > 0.3) {
          ctx2d.shadowBlur = 6
          ctx2d.shadowColor = `rgba(${r},${g},${b},${(magnitude * 0.6).toFixed(3)})`
          ctx2d.fill()
          ctx2d.shadowBlur = 0
        }
      }
    }

    draw()

    return () => {
      if (animFrameRef.current !== null) {
        cancelAnimationFrame(animFrameRef.current)
        animFrameRef.current = null
      }
    }
  }, [playing, color])

  // Keep canvas width in sync with container
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ro = new ResizeObserver(entries => {
      for (const entry of entries) {
        canvas.width = entry.contentRect.width
      }
    })
    ro.observe(canvas.parentElement || canvas)
    // Set initial size
    if (canvas.parentElement) {
      canvas.width = canvas.parentElement.offsetWidth
    }
    return () => ro.disconnect()
  }, [])

  return (
    <canvas
      ref={canvasRef}
      height={80}
      style={{
        width: '100%',
        height: '80px',
        display: 'block',
      }}
    />
  )
}
