const BACKEND = process.env.API_URL || 'http://localhost:8000/api'

export async function GET() {
  const res = await fetch(`${BACKEND}/sessions/arc-types`, { cache: 'no-store' })
  const data = await res.json()
  return Response.json(data, { status: res.status })
}
