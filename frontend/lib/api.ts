const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api'

export interface ArcType {
  key: string
  label: string
  bpm_start: number
  bpm_peak: number
  bpm_end: number
  description: string
}

export interface SessionTrack {
  position: number
  target_bpm: number
  track_id: number
  title: string
  artist: string
  bpm: number
  camelot: string | null
  energy: number | null
  score?: number
  status?: string
  resonance_rating?: number | null
}

export interface Session {
  session_id: number
  arc_type: string
  arc_label: string
  duration_min: number
  bpm_start: number
  bpm_peak: number
  bpm_end: number
  total_tracks: number
  status: string
  tracks: SessionTrack[]
}

export interface NowPlaying {
  position: number
  target_bpm: number
  track_id: number
  title: string
  artist: string
  bpm: number
  camelot: string | null
  energy: number | null
  duration: number | null
  audio_url: string | null
  done?: boolean
  message?: string
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

export const api = {
  getArcTypes: () => get<{ arc_types: ArcType[] }>('/sessions/arc-types'),
  createSession: (arc_type: string, duration_min: number) =>
    post<Session>('/sessions', { arc_type, duration_min }),
  getSession: (id: number) => get<Session>(`/sessions/${id}`),
  nextTrack: (id: number) => get<NowPlaying>(`/sessions/${id}/next-track`),
  recordEvent: (id: number, event: 'completed' | 'skipped', position: number, rating?: number) =>
    post(`/sessions/${id}/events`, { event, position, rating }),
  getSummary: (id: number) => get(`/sessions/${id}/summary`),
}
