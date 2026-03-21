'use client'

import { useEffect, useRef, useState } from 'react'

interface Props {
  audioRef: React.RefObject<HTMLAudioElement | null>
  playing: boolean
  color: string
}

/**
 * Animated frequency bars driven purely by canvas + requestAnimationFrame.
 * Does NOT use Web Audio API / createMediaElementSource, which permanently
 * captures the <audio> element and breaks playback under Chrome's autoplay policy.
 */
export default function FrequencyVisualizer({ audioRef, playing, color }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const rafRef    = useRef<number | null>(null)
  const barsRef   = useRef<Float32Array | null>(null)
  const seedRef   = useRef<number[]>([])

  // Parse hex color
  const [r, g, b] = (() => {
    const hex = color.match(/^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i)
    if (hex) return [parseInt(hex[1], 16), parseInt(hex[2], 16), parseInt(hex[3], 16)]
    return [202, 253, 0] // fallback lime
  })()

  // Generate stable random seeds on mount
  useEffect(() => {
    const seeds: number[] = []
    for (let i = 0; i < 200; i++) seeds.push(Math.random() * Math.PI * 2)
    seedRef.current = seeds
  }, [])

  // Draw loop
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const numBars = 120
    if (!barsRef.current || barsRef.current.length !== numBars) {
      barsRef.current = new Float32Array(numBars)
    }
    const bars = barsRef.current

    let t = 0
    function draw() {
      rafRef.current = requestAnimationFrame(draw)
      const ctx = canvas!.getContext('2d')
      if (!ctx) return

      const W = canvas!.width
      const H = canvas!.height
      ctx.clearRect(0, 0, W, H)

      t += 0.02

      const barW = 3
      const gap = 2
      const step = barW + gap
      const visibleBars = Math.min(numBars, Math.floor(W / step))
      const seeds = seedRef.current

      for (let i = 0; i < visibleBars; i++) {
        const seed = seeds[i] || i * 0.3

        if (playing) {
          // Organic wave-driven animation with randomized phases
          const wave1 = Math.sin(t * 1.8 + seed) * 0.5 + 0.5
          const wave2 = Math.sin(t * 2.7 + seed * 1.4) * 0.3 + 0.5
          const wave3 = Math.sin(t * 0.9 + seed * 0.7) * 0.2 + 0.5
          // Bass-heavy left side, treble right side
          const posWeight = i < visibleBars * 0.3
            ? 0.9 : i < visibleBars * 0.6 ? 0.7 : 0.4
          const target = (wave1 * 0.5 + wave2 * 0.3 + wave3 * 0.2) * posWeight
          bars[i] += (target - bars[i]) * 0.18
        } else {
          // Decay to zero
          bars[i] *= 0.92
          if (bars[i] < 0.005) bars[i] = 0
        }

        const mag = bars[i]
        const barH = Math.max(2, mag * (H - 4))
        const x = i * step
        const y = H - barH

        const isMid = i > visibleBars * 0.1 && i < visibleBars * 0.7
        const opacity = Math.min(1, mag * (isMid ? 1.0 : 0.5) + 0.04)

        const radius = Math.min(barW / 2, 2)
        ctx.beginPath()
        ctx.moveTo(x + radius, y)
        ctx.lineTo(x + barW - radius, y)
        ctx.quadraticCurveTo(x + barW, y, x + barW, y + radius)
        ctx.lineTo(x + barW, H)
        ctx.lineTo(x, H)
        ctx.lineTo(x, y + radius)
        ctx.quadraticCurveTo(x, y, x + radius, y)
        ctx.closePath()

        ctx.fillStyle = `rgba(${r},${g},${b},${opacity.toFixed(3)})`
        ctx.fill()

        if (isMid && mag > 0.35) {
          ctx.shadowBlur = 8
          ctx.shadowColor = `rgba(${r},${g},${b},${(mag * 0.55).toFixed(3)})`
          ctx.fill()
          ctx.shadowBlur = 0
        }
      }
    }

    draw()
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current) }
  }, [playing, r, g, b])

  // Keep canvas pixel-width in sync with container
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
