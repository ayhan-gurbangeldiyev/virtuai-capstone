<p align="center">
  <img src="mascot/maskot_nobg.png" alt="TypeHype Mascot" width="160" />
</p>

<h1 align="center">TypeHype — ContentFactory</h1>

<!-- SİSTEM KILAVUZU: tüm sistemin ne/nerede/nasıl çalıştığı (mimari, flow, ajanlar,
     LLM kullanım haritası, LangGraph, servisler, şema) → SYSTEM_GUIDE.md. Repo analizi/
     raporu için ÖNCE bunu oku. Ölü modüller → docs/DEPRECATED_MODULES.md. -->
<p align="center"><strong>📘 Sistem kılavuzu (ne/nerede/nasıl çalışıyor): <a href="SYSTEM_GUIDE.md">SYSTEM_GUIDE.md</a></strong> — mimari, içerik akışı, ajanlar, LLM kullanım haritası, LangGraph, servisler, Supabase şema. <em>Repo analizi/raporu için önce bunu oku.</em></p>
<p align="center"><em>Ölü/kullanılmayan modüller → <a href="docs/DEPRECATED_MODULES.md">docs/DEPRECATED_MODULES.md</a> — @deprecated işaretli dosyalar aktif akışın parçası DEĞİL.</em></p>

<p align="center">
  <strong>AI-Powered Content Intelligence Platform</strong><br/>
  Real-time trend detection, AI content generation, and social media optimization — all in one platform.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/React_19-61DAFB?style=flat-square&logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/Supabase-3FCF8E?style=flat-square&logo=supabase&logoColor=white" />
  <img src="https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white" />
  <img src="https://img.shields.io/badge/Vercel-000000?style=flat-square&logo=vercel&logoColor=white" />
  <img src="https://img.shields.io/badge/GPT--4o-412991?style=flat-square&logo=openai&logoColor=white" />
</p>

---

## What is TypeHype?

TypeHype is a full-stack AI content platform that:

1. **Detects trends** — Monitors 55+ RSS feeds and Twitter/X accounts using a 2-layer pipeline (GitHub Actions + FastAPI)
2. **Analyzes with AI** — GPT-4o-mini scores, clusters, and categorizes signals into actionable trends
3. **Generates content** — Produces platform-optimized content (tweets, threads, LinkedIn posts, blog drafts) with style fingerprinting
4. **Optimizes for engagement** — X/Twitter algorithm scoring, A/B variant generation, and competitor analysis via Xquik API
5. **Exposes via MCP** — 14-tool MCP server for AI agent integration (Claude, etc.)

---

## Architecture

```
                    ┌──────────────────────────────────────────────┐
                    │              TypeHype Platform               │
                    └──────────────────────────────────────────────┘

  ┌─────────────────────┐        ┌──────────────────────────────────────┐
  │  GitHub Actions      │        │  FastAPI Backend (Hetzner VPS)       │
  │  (6x/day cron)       │        │                                      │
  │                      │        │  24 route modules · 32 prompt        │
  │  RSS Fetcher         │        │  builders · 10-layer security        │
  │  55+ feeds ──────────│──>     │                                      │
  │  Parse · Normalize   │  raw   │  Trend Engine ──> AI Analysis        │
  │  Batch INSERT        │ signals│  Twitter Fetch ──> Scoring           │
  │  Feed health check   │        │  Content Gen  ──> Style Lab          │
  └─────────────────────┘        │                                      │
                                  │  MCP Server (14 tools, JSON-RPC 2.0) │
  ┌─────────────────────┐        │  REST API (135+ endpoints)           │
  │  Scheduled Cron      │        └───────────────┬──────────────────────┘
  │  (5x/day)            │──> POST /auto-refresh   │
  └─────────────────────┘                          │
                                                    │
  ┌─────────────────────┐        ┌─────────────────┴────────────────────┐
  │  React 19 Frontend   │<──────│  Supabase (PostgreSQL + pgvector)    │
  │  Vercel · Tailwind   │       │  20 tables · RLS · Real-time         │
  │  Radix UI · i18n     │       │  Auth · Storage                      │
  │  24 pages            │       └──────────────────────────────────────┘
  └─────────────────────┘
```

---

## Features

| Module | Description |
|--------|-------------|
| **Trend Dashboard** | Real-time AI trend feed with category filters, scores, and sources |
| **Content Studio** | AI-powered tweet/thread/post generator with tone & style controls |
| **Style Lab** | 50+ dimension style fingerprinting with DNA analysis |
| **Creator Hub** | Multi-platform content management with draft/publish workflow |
| **AI Coach** | Personalized content strategy recommendations |
| **X Analytics** | Account analysis, engagement metrics, viral pattern detection |
| **MCP Server** | 14 tools for AI agent integration (trends, scoring, generation) |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19, Tailwind CSS, Radix UI, Framer Motion, Recharts, i18next |
| **Backend** | Python, FastAPI, Uvicorn |
| **Database** | Supabase (PostgreSQL + pgvector), Row Level Security |
| **AI Models** | GPT-4o (content), GPT-4o-mini (analysis), GPT-4.1-nano (fallback) |
| **APIs** | Xquik (Twitter/X data), YouTube Data API |
| **Hosting** | Vercel (frontend), Hetzner VPS (backend), GitHub Actions (RSS) |
| **Auth** | Supabase Auth with email whitelist |

---

## Project Structure

```
ContentFactory/
├── backend/
│   ├── routes/           # 24 API route modules
│   ├── services/         # Business logic (trend engine, xquik client, etc.)
│   ├── middleware/        # 10-layer security stack
│   ├── prompts/          # 32 AI prompt builders
│   ├── migrations/       # SQL migration files
│   ├── config/           # RSS feeds config
│   ├── tests/            # Test suite
│   └── server.py         # FastAPI application entry point
├── frontend/
│   ├── src/
│   │   ├── pages/        # 24 page components
│   │   ├── components/   # Radix UI component library
│   │   ├── contexts/     # React context providers
│   │   ├── lib/          # API client, i18n, Supabase
│   │   ├── locales/      # EN/TR translations
│   │   └── config/       # Platform configurations
│   └── public/           # Static assets
├── docs/
│   ├── SYSTEM_DOCUMENTATION.md   # Full system documentation (TR)
│   ├── specs/                    # Feature specifications & plans
│   └── references/               # Research documents
├── .github/workflows/
│   ├── rss-fetcher.yml   # RSS pipeline (6x/day cron)
│   └── run.yml           # Manual trigger workflow
├── n8n/                  # Twitter Radar workflow (archived)
├── mascot/               # Brand mascot assets
└── memory/               # Product requirements (PRD)
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Supabase project ([supabase.com](https://supabase.com))

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r ../requirements.txt
cp .env.example .env          # Fill in your keys
uvicorn server:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env          # Fill in your keys
npm start                     # http://localhost:3000
```

---

## MCP Server

TypeHype exposes a **Model Context Protocol** server for AI agent integration.

**Endpoint:** `POST /api/mcp` (Streamable HTTP, JSON-RPC 2.0)

| Tool | Description |
|------|-------------|
| `get_today_trends` | Top trends (24h, category/score filter) |
| `get_day_recap` | Daily summary with stats |
| `get_trending_by_category` | Grouped by category |
| `search_trends` | Full-text search (7-30 day range) |
| `get_twitter_trends` | Live Twitter/X trends |
| `score_tweet` | Algorithm score (0-100) with tips |
| `refine_tweet` | AI improvement suggestions |
| `generate_tweet` | Generate variants with auto-scoring |
| `analyze_account` | Engagement stats & content analysis |
| `get_viral_patterns` | Top vs bottom performance comparison |
| `compare_accounts` | Side-by-side account analysis |
| `repurpose_content` | Cross-platform content adaptation |
| `get_pipeline_health` | System health check |
| `trigger_manual_run` | Manual pipeline refresh |

**Auth:** Bearer token in `Authorization` header.

---

## API Overview

The backend exposes **135+ REST endpoints** across 24 route modules:

| Module | Prefix | Key Endpoints |
|--------|--------|---------------|
| Trends | `/api/trends` | CRUD, auto-refresh, health, process-signals |
| Content | `/api/generate` | Tweet, thread, LinkedIn post generation |
| Style | `/api/style` | DNA analysis, fingerprinting, palette |
| Profile | `/api/profile` | User profile, settings, onboarding |
| Sources | `/api/sources` | RSS feeds, Twitter accounts management |
| Analytics | `/api/analytics` | Account analysis, viral patterns |
| MCP | `/api/mcp` | Model Context Protocol server |

Full API reference: [`docs/SYSTEM_DOCUMENTATION.md`](docs/SYSTEM_DOCUMENTATION.md)

---

## Security

The backend implements a **10-layer security middleware stack**:

1. Authentication (JWT + email whitelist)
2. CSRF Protection
3. Rate Limiting (per-endpoint)
4. Input Sanitization
5. Replay Attack Protection
6. Request Size Limiting
7. Security Headers (HSTS, CSP, X-Frame)
8. Suspicious UA Blocking
9. Token Usage Tracking
10. CORS Policy

---

## Environment Variables

See [`backend/.env.example`](backend/.env.example) and [`frontend/.env.example`](frontend/.env.example) for required configuration.

**GitHub Actions Secrets** (for RSS pipeline):
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

---

## Documentation

| Document | Description |
|----------|-------------|
| [`docs/SYSTEM_DOCUMENTATION.md`](docs/SYSTEM_DOCUMENTATION.md) | Complete system documentation (Turkish) |
| [`docs/specs/ROADMAP.md`](docs/specs/ROADMAP.md) | Product roadmap |
| [`docs/specs/`](docs/specs/) | Feature specifications and plans |
| [`docs/references/`](docs/references/) | Algorithm research and prompt guides |
| [`memory/PRD.md`](memory/PRD.md) | Product Requirements Document |

---

## License

Private project. All rights reserved.
