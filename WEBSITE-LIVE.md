# Make the new UI visible on the web

Your **latest UI is already in GitHub** (`main`). A website only updates after a **host** builds and serves that code.

Pick **one** path below.

---

## Path A — Vercel (fastest for the Next.js UI)

1. Open **[vercel.com](https://vercel.com)** → sign in → **Add New…** → **Project**.
2. **Import** `kp6801-ai/SOMA` (GitHub).
3. Set **Root Directory** to **`frontend`** → **Deploy**.
4. After the first deploy, open **Project → Settings → Environment Variables** and add:
   - **`NEXT_PUBLIC_API_URL`** = your real API base **with `/api`**  
     Example: `https://YOUR-BACKEND.onrender.com/api`
5. **Redeploy** (Deployments → … → Redeploy) so the env is baked into the build.
6. **Backend CORS:** wherever the API runs, set **`CORS_ORIGINS`** to your Vercel URL exactly, e.g. `https://soma-xxx.vercel.app` (no trailing slash).

Then open the Vercel URL — you should see the new top bar, bottom nav, and Discover screen.

---

## Path B — Render (frontend + backend from `render.yaml`)

1. **[dashboard.render.com](https://dashboard.render.com)** → **New** → **Blueprint**.
2. Connect **`kp6801-ai/SOMA`** and apply **`render.yaml`**.
3. Set **`DATABASE_URL`**, **`CORS_ORIGINS`** (frontend Render URL), and **`NEXT_PUBLIC_API_URL`** (`https://<backend-service>.onrender.com/api`).
4. Wait for both services to go **Live**; open the **frontend** service URL.

---

## Path C — CI deploy (GitHub Actions → Vercel)

Only if you want deploys from **Actions** instead of Vercel’s Git integration. Your GitHub token needs the **`workflow`** scope to add workflow files via `git push`; otherwise create the workflow in the GitHub **Actions** tab UI.

1. Add secrets: **`VERCEL_TOKEN`**, **`VERCEL_ORG_ID`**, **`VERCEL_PROJECT_ID`**.
2. Use a workflow that runs **`amondnet/vercel-action`** with **`working-directory: frontend`** and **`vercel-args: '--prod'`**.

---

## No backend yet?

The **new UI** will still **load** on Vercel/Render, but Discover may show an error until **`NEXT_PUBLIC_API_URL`** points at a running API with a database.
