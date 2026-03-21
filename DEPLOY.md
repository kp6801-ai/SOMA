# Deploy SOMA (make the site live)

You need **two public URLs**: the **API** and the **Next.js app**. They must know about each other via env vars and CORS.

## Option A — Render (matches `render.yaml`)

1. Push this repo to GitHub (`kp6801-ai/SOMA` or your fork).
2. In [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint**.
3. Connect the repo and apply the blueprint. Render will create:
   - `soma-backend` (FastAPI)
   - `soma-frontend` (Next.js)

### Environment variables (required)

| Service        | Variable                 | Value |
|----------------|--------------------------|--------|
| **soma-backend** | `DATABASE_URL`         | Your Postgres URL (Render Postgres or external). |
| **soma-backend** | `CORS_ORIGINS`         | Your **frontend** origin(s), comma-separated. Example: `https://soma-frontend.onrender.com` |
| **soma-frontend** | `NEXT_PUBLIC_API_URL` | Backend base **including** `/api`. Example: `https://soma-backend.onrender.com/api` |

After the first deploy, copy the backend URL from Render and paste it into `NEXT_PUBLIC_API_URL`, then redeploy the frontend (or trigger a rebuild). Set `CORS_ORIGINS` on the backend to the exact frontend URL (no trailing slash).

### Health checks

- API: `GET https://<backend-host>/health`
- API root: `GET https://<backend-host>/`

## Option B — Vercel (frontend) + Render (backend)

1. Deploy **backend** on Render as in Option A (or only the backend service from the YAML).
2. In [Vercel](https://vercel.com) → **Import** the repo, set **Root Directory** to `frontend`.
3. Add env: `NEXT_PUBLIC_API_URL` = `https://<your-backend>.onrender.com/api`
4. On Render backend, set `CORS_ORIGINS` to your Vercel URL, e.g. `https://soma.vercel.app`

## Local production check

```bash
cd frontend && npm ci && npm run build && npm start
```

---

**Note:** Free Render services spin down when idle; first request after idle can be slow. For a always-on demo, use a paid instance or Vercel for the static/edge-friendly parts.
