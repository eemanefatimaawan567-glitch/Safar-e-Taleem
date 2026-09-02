---
title: Safar-e-Taleem
emoji: 🚌
colorFrom: green
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# 🚌 Safar-e-Taleem — Smart School Transport for Pakistan

An AI-powered platform that cuts school-transport costs for Pakistani families
through **walking-group clustering**, **fuel-aware hybrid scheduling**, and a
**Roman-Urdu voice assistant** ("Ask Ammi/Abba"). Built for the Alibaba Cloud
Hackathon.

> The name means *"Journey of Education"*.

---

## ✨ Core features

| Feature | What it does |
|---|---|
| **AI Walking Groups** | DBSCAN clustering (scikit-learn, haversine) groups families within 1 km attending the same school into a "Walking School Bus". |
| **Fuel-aware routing** | Recommends walking / shared / carpool / bike based on distance and live petrol price; computes monthly savings. |
| **Live petrol monitor** | Scrapes current Pakistani fuel prices, tracks history, and charts trends (Chart.js). |
| **Hybrid shift simulation** | Principal can trigger a 3-days-school / 2-days-online rotation to cut transport cost ~40%. |
| **Ask Ammi/Abba AI** | Qwen (Alibaba DashScope) chat + voice assistant that replies in natural Roman-Urdu + English mix, with a rule-based fallback when no API key is set. |
| **Mohallah Study Pods** | Matches nearby families so children without devices can share offline learning packets (PDF). |
| **Offline-first PWA** | Service worker + web manifest; installable and works on flaky 3G networks. |

## 🛠 Tech stack

- **Backend:** Python 3.12, Flask, Flask-SQLAlchemy, SQLite
- **AI:** Alibaba Cloud DashScope (Qwen) via the `openai`-compatible SDK
- **ML:** scikit-learn (DBSCAN), numpy, pandas
- **Frontend:** vanilla JS, CSS design tokens, Chart.js, Web Speech API (STT + TTS)
- **Deploy:** Docker (Hugging Face Spaces) or gunicorn (Render/Railway via `Procfile` + `render.yaml`)

## 🚀 Run locally

```bash
pip install -r requirements.txt
cp .env.example .env          # optionally add DASHSCOPE_API_KEY for the real AI
python app.py                 # serves on http://127.0.0.1:5001
```

The database auto-creates and seeds demo users on first run.

**Demo logins (no password needed):**
- Parent → `/demo-login/parent`
- Principal → `/demo-login/principal`

## 🧪 Tests

```bash
python -m pytest tests/ -q    # 32 tests covering the commute/clustering engine
```

## ☁️ Deployment

### Option A — Hugging Face Spaces (free, no credit card)
This repo is Space-ready: the `Dockerfile` + the YAML header at the top of this
README configure it. Create a new **Space → SDK: Docker**, connect this GitHub
repo, add `DASHSCOPE_API_KEY` under *Space Settings → Variables and secrets*,
and it builds a free public URL.

### Option B — Render
`render.yaml` is a one-click Blueprint (`plan: free`). Connect the repo, add the
`DASHSCOPE_API_KEY` env var, deploy.

> **Note on free tiers:** the container filesystem is ephemeral, so the SQLite
> DB resets on restart (the app re-seeds automatically — fine for demos), and
> the service sleeps after ~15 min idle, so the first request may cold-start in
> ~30–60s. Open the URL once before presenting.

## 🔐 Environment variables

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Flask session signing (auto-generated on Render) |
| `DASHSCOPE_API_KEY` | Alibaba Qwen AI. When unset, the app falls back to the rule engine. |
| `FLASK_DEBUG` | `true` locally, `false` in production |
| `PORT` | Injected by the host platform (defaults to 7860 in Docker, 5001 locally) |

See `.env.example` for a full template.
