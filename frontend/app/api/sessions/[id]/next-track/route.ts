const BACKEND = process.env.API_URL || 'http://localhost:8000/api'

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const res = await fetch(`${BACKEND}/sessions/${id}/next-track`, { cache: 'no-store' })
  const data = await res.json()
  return Response.json(data, { status: res.status })
}
