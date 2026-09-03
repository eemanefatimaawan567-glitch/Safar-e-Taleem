# Safar-e-Taleem — Architecture Understanding

> **Scope:** Current-state architecture model of the Safar-e-Taleem platform.
> **Evidence source:** Code analysis of `app.py`, `modules/*.py`, `requirements.txt`, `README.md`, templates, and static assets.
> **Generated using:** Architecture Visualization plugin (`system-modeler` → `c4model` + `graphviz`).

---

## System Boundary

Safar-e-Taleem ("Journey of Education") is a **monolithic Flask web application** that helps Pakistani families reduce school-transport costs through AI-powered walking-group clustering, fuel-aware hybrid scheduling, live commute safety tracking, and a Roman-Urdu voice assistant.

### Actors

| Actor | Role | Evidence |
|---|---|---|
| **Parent** | Registers family, views transport recommendations, shares live commute location, receives SOS/pod alerts, uses "Ask Ammi/Abba" AI assistant | `app.py` routes: `/parent`, `/api/location/*`, `/api/ask-ammi-abba` |
| **Principal** | Monitors fuel costs, toggles hybrid schedule, broadcasts curriculum, views all commute activity on a school-wide map | `app.py` routes: `/principal`, `/api/toggle-hybrid`, `/api/broadcast-curriculum` |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Safar-e-Taleem System                        │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │              Flask Web Application (Python 3.12)               │  │
│  │                                                               │  │
│  │  ┌──────────────┐  ┌──────────────────┐  ┌────────────────┐  │  │
│  │  │ Routes & Auth │  │  Commute Engine  │  │ Petrol Monitor │  │  │
│  │  │ (Flask)       │──│  (DBSCAN, numpy) │  │ (requests)     │  │  │
│  │  └──────┬───────┘  └──────────────────┘  └───────┬────────┘  │  │
│  │         │                                         │            │  │
│  │  ┌──────┴───────┐  ┌──────────────────┐  ┌───────┴────────┐  │  │
│  │  │ School       │  │  Geo Services    │  │ AI Assistant   │  │  │
│  │  │ Registry     │──│  (OSRM, Nominatim│  │ (Qwen/rules)   │  │  │
│  │  └──────────────┘  └──────────────────┘  └────────────────┘  │  │
│  │                                                               │  │
│  │  ┌──────────────┐  ┌──────────────────┐                      │  │
│  │  │ Notification │  │  Curriculum      │                      │  │
│  │  │ (WA/SMS/IVR) │  │  (PDF packs)     │                      │  │
│  │  └──────────────┘  └──────────────────┘                      │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                             │                                       │
│                    ┌────────┴────────┐                              │
│                    │ SQLite Database  │                              │
│                    └─────────────────┘                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Module Dependency Structure

The codebase is organized into **7 Python modules** under `modules/` plus the main `app.py` entry point. The dependency graph has a clear **three-layer structure**:

### Layer 1 — Core Modules (standalone, no internal dependencies)
| Module | Responsibility | Key Dependencies |
|---|---|---|
| `commute_engine.py` | DBSCAN clustering (scikit-learn), transport recommendation by distance, fuel cost & carpool saving calculations | numpy, pandas, math |
| `petrol_price.py` | Scrapes live Pakistani fuel prices from Shell Pakistan, tracks history, detects changes | requests |
| `notification.py` | WhatsApp Cloud API, Pakistani HTTP SMS gateway, IVR delivery. Zero-setup simulation mode when credentials absent | requests |
| `curriculum.py` | Offline learning PDF pack generation for primary/secondary levels | (stdlib only) |

### Layer 2 — Integration Modules (depend on core)
| Module | Depends On | Responsibility |
|---|---|---|
| `geo_services.py` | `commute_engine` (distance_km) | OSRM walking route extraction, Nominatim geocoding with 24h server cache |
| `schools.py` | `commute_engine` (distance_km), `geo_services` (geocode) | School registry lookup, home-to-school distance calculation |
| `ai_responses.py` | `commute_engine` (distance, cluster context) | Qwen (DashScope) chat + voice in Roman-Urdu, rule-based fallback |

### Layer 3 — Application Entry Point
| Module | Depends On | Responsibility |
|---|---|---|
| `app.py` | ALL modules | Flask routes, DB models (User, PetrolPrice, HybridSchedule, LocationShare, NotificationLog), auth, CSRF, rate limiting, SSE streams, APIs |

---

## External Integrations

| External System | Used By | Protocol | Purpose |
|---|---|---|---|
| **OSRM Demo Server** | geo_services | HTTP GET | Walking route geometry (waypoints, distance, duration) |
| **Nominatim (OpenStreetMap)** | geo_services, schools | HTTP GET | Free-text address → Pakistan coordinates |
| **Alibaba DashScope (Qwen)** | ai_responses | OpenAI-compatible SDK | Roman-Urdu + English AI chat responses |
| **Meta WhatsApp Cloud API** | notification | HTTPS POST | Curriculum delivery, pod alerts, SOS notifications |
| **Pakistani SMS Gateway** | notification | HTTPS POST | SMS curriculum delivery |
| **Shell Pakistan Fuel Prices** | petrol_price | HTTP GET (scraping) | Live petrol/diesel/kerosene/LPG prices |

---

## Data Model (SQLite)

| Table | Purpose | Key Fields |
|---|---|---|
| `User` | Parents and principals | name, email, role, cnic, phone, address, neighborhood, lat/lon, children_count, has_smart_device |
| `PetrolPrice` | Fuel price snapshots | price, source (live/demo-spike/demo-reset/seed), checked_at |
| `HybridSchedule` | Principal-triggered rotation | is_active, group_a_days, group_b_days, online_days, petrol_price_at_trigger |
| `LocationShare` | Live commute location per parent | user_id, lat/lon, is_active, is_sos, last_updated |
| `NotificationLog` | Curriculum/alert delivery log | recipient, channel (whatsapp/sms/ivr), content_preview, status |

---

## Key Architectural Patterns

1. **Monolith with module separation** — Single Flask process, but business logic is cleanly separated into domain modules.
2. **Graceful degradation** — Every external integration has a fallback: AI → rule engine, WhatsApp → simulation mode, OSRM → interpolated line, Nominatim → manual address.
3. **Offline-first PWA** — Service worker caches static assets and OSM tiles; the safety map renders without connectivity.
4. **Real-time via SSE** — Live commute locations pushed via Server-Sent Events with auto-reconnect cycling (default 50s).
5. **Demo-friendly** — One-click demo logins, fake petrol spike/reset endpoints, auto-seeded demo families.

---

## Artifacts Produced

| Artifact | Path | Format |
|---|---|---|
| C4 System Context + Container + Component | `docs/architecture/safar-e-taleem.structurizr.dsl` | Structurizr DSL |
| Module Dependency Graph | `docs/architecture/module-dependencies.dot` | Graphviz DOT |
| This document | `docs/architecture/architecture-understanding.md` | Markdown |

---

## Evidence & Confidence

- **High confidence:** All module boundaries, import relationships, external integrations, and data model structures are directly evidenced by code.
- **Assumed:** The SMS gateway provider is inferred from the code's generic HTTP gateway pattern — the actual provider (SMS4Connect, Jazz, Telenor) is configured at runtime.
- **Unknown:** Production deployment currently targets Hugging Face Spaces (Docker) and Render (gunicorn). The actual production database migration path from SQLite to PostgreSQL is configured via `DATABASE_URL` but the migration mechanism is not evidenced beyond the `psycopg2-binary` dependency.
