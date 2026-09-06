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

# 🚌 Safar-e-Taleem
### AI-Powered Safe Mobility & Education Continuity for Pakistan

> **Because the journey should never become the cost of an education.**

Safar-e-Taleem is a connected decision-support platform for Pakistani families and schools facing rising commute costs, student-safety concerns, limited connectivity and unequal device access. Instead of treating transport, safety and remote learning as separate problems, the prototype connects them into one continuity workflow.

## 🚀 Live Prototype

**Live app:** https://eemanefatimaawan.pythonanywhere.com/

| Demo | Direct access |
|---|---|
| 👨‍👩‍👧 Parent | https://eemanefatimaawan.pythonanywhere.com/demo-login/parent |
| 🏫 Principal | https://eemanefatimaawan.pythonanywhere.com/demo-login/principal |

No installation is required to explore the deployed hackathon prototype.

---

## 🎯 The Challenge

For many families, education access depends on more than the classroom. A student must first be able to **afford and safely complete the journey to school**. When fuel prices rise, daily transport becomes harder to sustain. Moving learning online does not fully solve the problem either: some households have limited internet access, basic phones, or one shared device.

Safar-e-Taleem therefore addresses the whole chain:

**Can the student reach school affordably? → Can the journey be made safer? → If regular travel becomes difficult, how can learning continue?**

---

# 🔄 How Safar-e-Taleem Works

```text
                    ⛽ FUEL / COMMUTE PRESSURE
                              │
                              ▼
                  🧠 PRINCIPAL DECISION CENTER
                              │
                 ┌────────────┴────────────┐
                 │                         │
                 ▼                         ▼
       🚶 MOBILITY OPTIMIZATION     🏫 HYBRID SHIFT
       Walking School Bus           3 Physical Days
       + Shared Carpool             + 2 Remote Days
                 │                         │
                 │                         ▼
                 │              📱 LOW-TECH LEARNING
                 │              WhatsApp • SMS • IVR
                 │                         │
                 │                         ▼
                 │              🏘️ MOHALLAH STUDY PODS
                 │              Shared device access
                 │                         │
                 └────────────┬────────────┘
                              ▼
                    🛡️ LIVE STUDENT SAFETY
                  Location Sharing • SOS
                              │
                              ▼
                     📊 PROJECTED IMPACT
```

### The connected response

1. **Detect commute pressure** — the principal can explore changing fuel-cost scenarios through the Hybrid Shift Predictor and clearly labelled demo simulation controls.
2. **Optimize physical journeys** — DBSCAN groups nearby same-school families for Walking School Buses or shared carpools.
3. **Recommend a school response** — when commute pressure is high, the prototype can recommend a **3-day physical / 2-day remote** schedule.
4. **Keep remote days accessible** — lightweight lessons can be delivered through simulated WhatsApp, SMS and IVR channels.
5. **Support students without devices** — Mohallah Study Pods connect nearby students to shared device access.
6. **Protect students who still travel** — live commute sharing, a principal safety map and SOS alerts keep active journeys visible.
7. **Summarize projected impact** — the Continuity Plan brings mobility, remote learning, Study Pods and safety information together for the principal.

> **Prototype impact note:** shifting from five physical school days to three represents a potential **~40% reduction in weekly physical commute frequency**. This is a scenario estimate, not a validated real-world cost reduction.

---

## 👨‍👩‍👧 Parent Experience

### 🧭 Smart Parent Recommendation
The parent does not need to interpret raw clustering results. **Recommended for Your Family** uses existing distance, school, DBSCAN cluster and savings information to surface an appropriate walking/carpool option.

### 🚶 Safe Walking & Carpool Groups
Nearby families whose children attend the same school can be grouped into a **Walking School Bus** or shared transport arrangement. Estimated transport savings and route information help make the recommendation understandable.

### 📍 Live Commute + SOS
A parent can start/stop commute sharing during the school journey. Live location status is surfaced to the principal, and an SOS can raise an emergency state with the student's last known location.

### 🎙️ Ask Ammi/Abba
A Roman-Urdu/English assistant makes the platform more accessible to parents. The project integrates with **Alibaba Cloud DashScope (Qwen)** when configured and retains a fallback path when the external AI service is unavailable. Voice input/output uses browser capabilities where supported.

### 🏘️ Mohallah Study Pods
Families with device access can support nearby students who do not have reliable access to a smartphone or learning device.

---

## 🏫 Principal Experience

### 🧠 Today's Decision Center
The principal gets actionable summaries instead of having to interpret every dashboard metric independently:

- commute pressure and Hybrid Shift recommendation;
- walking/carpool opportunities;
- device-access support through Study Pods;
- live student-safety/SOS status.

### 🔄 Education Continuity Workflow
**Generate Continuity Plan** connects existing systems into one coordinated response:

**Fuel Pressure → Hybrid Schedule → Mobility → Low-Tech Learning → Study Pods → Live Protection → Projected Impact**

### 🎮 Demo Scenario Simulator
For reliable hackathon demonstrations, clearly labelled simulation controls can demonstrate **Normal Day**, **Fuel Crisis** and **Student SOS** scenarios without pretending simulated events are real-world data.

### 🚨 Emergency/SOS Detail
When an SOS is active, the principal can see the relevant journey status, last known location/update information and navigate to the live safety map. The feature is a school/parent prototype alert system; it does not claim direct emergency-service integration.

---

## 📸 Prototype Screenshots

### Landing Page
![Safar-e-Taleem landing page](docs/images/landing-page.png)

### Parent Mobility Dashboard
![Parent dashboard with map](docs/images/parent-dashboard-map.png)

### Principal Decision Dashboard
![Principal dashboard](docs/images/principal-dashboard.png)

### Live Student Safety Map
![Principal live safety map](docs/images/principal-live-safety-map.png)

### Registration & Address Lookup
![Registration address lookup](docs/images/register-address-lookup.png)

---

## ✨ Feature Map

| Layer | Feature | Purpose |
|---|---|---|
| **Mobility** | DBSCAN Walking/Carpool Groups | Match nearby same-school families |
| **Decision Support** | Smart Parent Recommendation | Convert cluster/distance data into a clear family recommendation |
| **School Planning** | Hybrid Shift Predictor | Explore a 3-physical / 2-remote-day response to commute pressure |
| **Orchestration** | Education Continuity Workflow | Connect mobility, remote learning, device access and safety |
| **Principal UX** | Decision Center | Surface important actions and alerts in one place |
| **Safety** | Live Commute + Safety Map + SOS | Keep active student journeys visible |
| **Accessibility** | Ask Ammi/Abba | Roman-Urdu/English assistance with Qwen integration |
| **Learning** | WhatsApp / SMS / IVR | Low-data learning-delivery prototype |
| **Device Access** | Mohallah Study Pods | Support students through community device sharing |
| **Resilience** | PWA + fallback modes | Improve usability under unreliable connectivity |
| **Demo** | Scenario Simulator | Reliably demonstrate fuel-crisis and SOS flows |

---

## 🧠 AI & Decision Intelligence

Safar-e-Taleem uses different techniques for different problems rather than using an LLM for everything:

- **DBSCAN (scikit-learn)** — geographic clustering of nearby same-school families without requiring a predefined number of clusters.
- **Alibaba Cloud DashScope / Qwen** — Roman-Urdu and English assistance through Ask Ammi/Abba when external AI configuration is available.
- **Deterministic recommendation logic** — converts existing distance, cluster and savings data into parent recommendations.
- **Fuel-aware decision logic** — supports the Hybrid Shift Predictor and Principal Decision Center.
- **Real-time journey state** — connects live location/SOS information with the principal safety experience.

---

## 🛠 Technology Stack

| Area | Technology |
|---|---|
| Backend | Python, Flask, Flask-SQLAlchemy, SQLite |
| AI | Alibaba Cloud DashScope (Qwen), OpenAI-compatible SDK |
| ML | scikit-learn DBSCAN, NumPy, pandas |
| Maps | Leaflet + OpenStreetMap |
| Real-time | Server-Sent Events (SSE) + polling fallback |
| Frontend | Jinja2, HTML, CSS, vanilla JavaScript, Chart.js |
| Voice | Web Speech API |
| Low-tech delivery | WhatsApp/SMS integrations + simulation mode |
| Offline support | Progressive Web App + service worker |
| Deployment | PythonAnywhere |

---

## 📊 What the Prototype Demonstrates

Safar-e-Taleem is designed to demonstrate the potential to:

- reduce unnecessary individual school trips through shared mobility;
- give parents a clear transport recommendation rather than raw map data;
- help principals respond systematically to commute-cost pressure;
- maintain learning access during reduced physical attendance;
- support students with limited device/connectivity access;
- improve visibility of active student journeys and SOS states;
- make assistance accessible through Roman-Urdu/English interaction.

**All financial savings, projected impact figures and the ~40% commute-frequency figure should be interpreted as prototype estimates unless explicitly backed by measured data.**

---

## 🧪 Run & Test Locally

```bash
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Run the automated tests with:

```bash
python -m pytest tests/ -q
```

Dedicated demo routes are available for the hackathon:

```text
/demo-login/parent
/demo-login/principal
```

For Qwen, add your own `DASHSCOPE_API_KEY` to a private `.env` file. **Never commit credentials.**

---

## 🔐 Security & Demo Transparency

- Real API keys, passwords and tokens belong in `.env`, never in Git.
- `.env.example` contains placeholders only.
- WhatsApp/SMS/IVR can operate in simulation mode when external providers are not configured.
- Demo fuel/SOS scenario controls are explicitly simulation tools.
- Prototype projections are labelled as estimates rather than validated real-world outcomes.

---

## 🏆 Hackathon Vision

Safar-e-Taleem is **not just a transport app and not just an online-learning app**.

It treats mobility, affordability, student safety, connectivity and device access as parts of the same education-access problem.

```text
If a child CAN reach school
        ↓
Make the journey safer + more affordable

If reaching school becomes difficult
        ↓
Adapt the schedule + keep learning accessible

If the child lacks a device
        ↓
Connect them to community support

Throughout the journey
        ↓
Keep student safety visible
```

> ## **Because the journey should never become the cost of an education.**
