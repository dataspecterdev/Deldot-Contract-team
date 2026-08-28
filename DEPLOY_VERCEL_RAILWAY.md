# Deploy DORA: Railway (backend) + Vercel (frontend)

## Overview

| Layer    | Platform | What runs there              |
|----------|----------|------------------------------|
| Backend  | Railway  | FastAPI + contract_review pipeline |
| Frontend | Vercel   | React/Vite static build      |

Vercel proxies all `/api/*` requests to your Railway backend, so the browser never needs a hardcoded backend URL.

---

## Prerequisites

- Git repo pushed to GitHub (Railway and Vercel both deploy from GitHub)
- [Railway account](https://railway.app) (free tier works)
- [Vercel account](https://vercel.com) (free tier works)
- AWS credentials with Bedrock + Knowledge Base access (same as before)

---

## Part 1 — Deploy the backend to Railway

### 1. Create a new Railway project

1. Go to [railway.app](https://railway.app) → **New Project**
2. Choose **Deploy from GitHub repo**
3. Select your `Deldot-Contract-team-1` repo
4. Railway will detect `railway.toml` and start the build automatically

### 2. Add a persistent volume (required — the app stores files on disk)

1. In your Railway service, go to **Settings → Volumes**
2. Click **Add Volume**
3. Set the mount path to `/app/dora_workspace`
4. Click **Add**

> Without this, uploaded files and project data are lost on every redeploy.

### 3. Set environment variables in Railway

Go to your service → **Variables** tab and add:

| Variable          | Value                                      |
|-------------------|--------------------------------------------|
| `AWS_REGION`      | `us-east-1`                                |
| `AWS_ACCESS_KEY_ID` | your AWS access key                      |
| `AWS_SECRET_ACCESS_KEY` | your AWS secret key                |
| `KB_ID`           | `7BKLBOJA7F`                               |
| `BEDROCK_MODEL_ID`| `us.anthropic.claude-sonnet-4-6`           |
| `DORA_WORKSPACE`  | `/app/dora_workspace`                      |
| `CORS_ORIGINS`    | *(leave blank for now — fill in after step Part 2 step 3)* |

### 4. Get your Railway URL

After the deploy succeeds, go to **Settings → Networking → Generate Domain**.  
Your backend URL will look like:
```
https://deldot-contract-team-1-production.up.railway.app
```

Verify it's working:
```
https://<your-railway-url>/api/health
```
Should return: `{"status":"ok","service":"DORA"}`

---

## Part 2 — Deploy the frontend to Vercel

### 1. Update vercel.json with your Railway URL

Open `dora-ui/vercel.json` and replace the placeholder with your real Railway URL:

```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://<your-railway-url>/api/:path*"
    }
  ],
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite"
}
```

Commit and push this change:
```bash
git add dora-ui/vercel.json
git commit -m "set Railway backend URL in vercel.json"
git push
```

### 2. Create a new Vercel project

1. Go to [vercel.com](https://vercel.com) → **Add New Project**
2. Import your GitHub repo
3. Set the **Root Directory** to `dora-ui`
4. Vercel will auto-detect Vite — leave all other settings as defaults
5. Click **Deploy**

### 3. Get your Vercel URL and update Railway CORS

After deploy, Vercel gives you a URL like:
```
https://deldot-contract-team-1.vercel.app
```

Go back to Railway → **Variables** and set:
```
CORS_ORIGINS = https://deldot-contract-team-1.vercel.app
```

Railway will redeploy automatically. Your app is now live.

---

## Part 3 — Custom domain (optional)

If you have a custom domain, add it in both:
- Vercel → **Settings → Domains**
- Railway → `CORS_ORIGINS` (append with a comma: `https://yourdomain.com,https://deldot-contract-team-1.vercel.app`)

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `/api/health` returns 502 on Vercel | Railway backend not running | Check Railway deploy logs |
| CORS errors in browser | Vercel URL not in `CORS_ORIGINS` | Add it to Railway env var |
| Uploads lost after redeploy | No persistent volume | Add volume at `/app/dora_workspace` |
| Analysis times out | Railway free tier sleeps after inactivity | Upgrade to Railway Hobby ($5/mo) or keep-alive ping |
| `KB_ID` not found error | Wrong AWS region or KB ID | Double-check Bedrock console |

---

## Cost estimate

- **Railway**: Free tier (500 hrs/month) or Hobby at $5/month for always-on
- **Vercel**: Free tier is plenty for this use case
- **AWS Bedrock**: ~$1–3 per contract package analyzed (unchanged)
