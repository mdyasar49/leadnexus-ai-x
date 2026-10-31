# LeadNexus AI X — Hyper-Scale Enterprise Lead Intelligence Platform

LeadNexus AI X is an enterprise-grade autonomous intelligence and public data verification platform designed to identify, verify, score, and monitor B2B technology leads across Australian enterprise domains.

> **Zero CRM Invariant**: LeadNexus AI X is purely an intelligence, discovery, and verification engine. It has zero sales pipelines, deal stages, quotas, automated cold emails, cold calling, or unsolicited outreach mechanisms. Unverified claims remain strictly `UNKNOWN`.

---

## 1. Quick Start: How to Run the Code

### Prerequisites
- Python 3.11+ / 3.12
- Node.js v18+ / v20+ & npm
- PostgreSQL 15+ (or built-in SQLite for local development)

### Step 1: Backend Server (FastAPI)
```bash
# Navigate to the API application
cd apps/api

# Install dependencies
pip install -r ../../requirements.txt

# Run the FastAPI server with hot-reload
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- API Base URL: `http://localhost:8000`
- Interactive OpenAPI Docs: `http://localhost:8000/docs`
- Health Endpoint: `http://localhost:8000/health` (Returns `200 OK`)

### Step 2: Frontend Enterprise Workspaces (React + Vite + MUI)
```bash
# Navigate to the Web application
cd apps/web

# Install frontend dependencies
npm install

# Run the Vite development server
npm run dev
```
- Frontend UI: `http://localhost:3000`

### Step 3: Run Full Test Suite (Phases 1–33)
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```
- Status: **349 / 349 tests passing** in ~12 seconds.

---

## 2. How Search Works (`epti search panrathu`)

LeadNexus AI X implements a **3-tiered search and discovery architecture**:

```
[ Natural Language Query / UI Search ]
                 │
                 ├──► 1. Universal Discovery Engine (/api/v1/discovery)
                 │    Public web SERP scrapers (DuckDuckGo, Brave, Google public search),
                 │    GitHub public commit/repo searches, and job board scrapers.
                 │
                 ├──► 2. Enterprise DSL & Keyset Search (/api/v1/search/leads)
                 │    Sub-millisecond AST parser converting text into structured filters:
                 │    "Find Australian retail companies using Odoo" ──►
                 │    `country = 'Australia' AND technology CONTAINS 'odoo'`.
                 │    Uses base64 URL-safe zero-offset Keyset Pagination (O(1) latency).
                 │
                 └──► 3. Semantic Vector RAG & Knowledge Graph (/api/v1/knowledge-retrieval)
                      Dense vector similarity + Graph traversal across:
                      Company ──(OPERATES_IN)──► Industry ──(USES)──► Tech Stack.
```

### Key Search Endpoints:
1. **Natural Language Query**:
   ```http
   POST /api/v1/search/natural-language
   Content-Type: application/json
   Authorization: Bearer <token>

   {
     "query": "Find Australian companies using Odoo with high intent"
   }
   ```
2. **Structured Lead Search**:
   ```http
   POST /api/v1/search/leads
   Content-Type: application/json
   Authorization: Bearer <token>

   {
     "query": "Pacific",
     "filters": { "country": "Australia", "priority_tier": "TIER_1_ENTERPRISE" },
     "limit": 25
   }
   ```
3. **Global Multi-Facet Search**:
   ```http
   GET /api/v1/search/global?q=Apex
   ```

---

## 3. Where Data is Stored (`enga store aagum`)

All data is stored following strict enterprise tiered storage principles:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PostgreSQL Database                             │
│                  (Canonical Single Source of Truth)                    │
│                                                                        │
│  HOT STORAGE (0–30 Days)                                               │
│  ├── companies                      (Canonical organization records)   │
│  ├── contacts                       (Verified decision-makers)         │
│  ├── lead_scores                    (Deterministic ICP & Intent)       │
│  ├── evidence_claims                (Grounded URL & snippet proofs)    │
│  └── governance_policies            (RBAC, ABAC & data contracts)      │
│                                                                        │
│  WARM STORAGE (30–90 Days)                                             │
│  ├── ontology_nodes & edges         (Semantic knowledge graph)         │
│  ├── signal_observations            (Raw web discovery signals)        │
│  └── audit_logs                     (Tamper-evident system events)     │
│                                                                        │
│  COLD STORAGE / ARCHIVE (> 90 Days)                                    │
│  ├── archive_tombstones             (Tombstone pointers in DB)         │
│  └── S3 / GCS / Local Encrypted     (Gzip-compressed cold packages)    │
│      storage/archives/{tenant_id}/{package_id}.json.gz                 │
└────────────────────────────────────────────────────────────────────────┘
```

- **Local SQLite (Development)**: `leadnexus.db` (seeded with 118 verified enterprise Australian companies).
- **Production Storage**: PostgreSQL with connection pooling (`pool_size=20`, `max_overflow=10`).
- **Cache Tier**: Redis 7.0 for rate limiting, distributed leases, and session tokens.

---

## 4. How to View and Inspect Leads (`epti atha pakkurathunu`)

### Option A: Via React Web UI Workspaces
1. Open `http://localhost:3000` in your browser.
2. Select workspaces from the top navigation bar:
   - **Autonomous Research**: View live research loops (Discover ➔ Enrich ➔ Verify ➔ Score).
   - **RAG Retrieval**: Ask grounded questions like *"Why is this company high priority?"* and inspect citations.
   - **Semantic Ontology**: Explore concepts, entities, and Odoo ERP domain models.
   - **Governance & SLA**: Inspect field masking, PII suppression, and legal holds.
   - **Resilience & DR**: Monitor circuit breakers, leases, and dead-letter queues.
   - **Zero-Downtime Migration**: Monitor live schema expand/contract operations.

### Option B: Via REST API
```bash
# 1. Generate access token
TOKEN=$(python -c "
from app.db.session import SessionLocal; from app.models.user import User
from app.security.tokens import create_access_token
db = SessionLocal(); user = db.query(User).first()
print(create_access_token(user_id=str(user.id)))
")

# 2. View Lead Details with Evidence Dossier
curl -X GET "http://localhost:8000/api/v1/companies/{company_id}" \
     -H "Authorization: Bearer $TOKEN"
```

---

## 5. Cloudflare Deployment Guide

### Frontend on Cloudflare Pages
The frontend is pre-configured with `apps/web/wrangler.toml` and `_headers`:
```bash
cd apps/web
npm run build
npx wrangler pages deploy dist --project-name=leadnexus-ai-x
```
Or connect your GitHub repository `https://github.com/mdyasar49/leadnexus-ai-x` directly in the [Cloudflare Pages Dashboard](https://dash.cloudflare.com/):
- **Build command**: `npm run build`
- **Build output directory**: `dist`
- **Root directory**: `apps/web`

### Backend on Cloudflare Workers / Cloudflare Tunnel
For the Python FastAPI backend, use **Cloudflare Tunnel (cloudflared)** to securely route traffic from Cloudflare Edge to the FastAPI service without exposing public ports:
```bash
cloudflared tunnel create leadnexus-api
cloudflared tunnel route dns leadnexus-api api.leadnexus.infogenx.com
cloudflared tunnel run leadnexus-api
```

---

## 6. Architecture & Platform Summary

| Metric | LeadNexus AI X Enterprise Spec |
| :--- | :--- |
| **Phases Implemented** | **All 33 Phases Complete** |
| **Active FastAPI Endpoints** | **746 registered endpoints** |
| **Automated Test Suite** | **349 / 349 Tests Passing** |
| **Canonical Truth Tier** | PostgreSQL (Zero data loss, Legal holds, Tombstones) |
| **Security & Privacy** | AES-256-GCM, HMAC-SHA256, SSRF IP-blocker, Prompt Sanitization |
| **Repository** | `https://github.com/mdyasar49/leadnexus-ai-x` |
| **Maintainer** | `@mdyasar49` |

