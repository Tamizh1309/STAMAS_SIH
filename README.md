# STAMAS — Smart Tender Analysis & Management Assessment System

**AI-powered integrated bid compliance verification** for GeM public procurement, built for **Ministry of Petroleum & Natural Gas / Chennai Petroleum Corporation Limited (CPCL)** use cases (refinery equipment, technical bid evaluation, vigilance, and Make-in-India compliance).

STAMAS parses multi-vendor technical submissions against tender requirements, scores clause-level compliance, flags collusion risk, generates clarification notices, and exposes analytics for Smart India Hackathon (PS **26100**) style impact reporting.

---

## Features

| Module | Description |
|--------|-------------|
| **Tender Cockpit** | Dashboard for active tenders, bidder cards, compliance scores, and quick navigation into deep evaluation. |
| **Clause AI Scanner** | Clause-by-clause audit (technical, statutory, commercial) with filters, search, and live **Gemini** verification. |
| **TCS Matrix & Collusion Radar** | Technical Comparative Statement views, cartel/anomaly detection (IP metadata, mirror pricing), export workflows. |
| **Bidder Diagnostic Sandbox** | Paste sample bid text; run local rule checks before formal submission. |
| **SIH Impact & Analytics** | Before/after metrics (scrutiny time, accuracy, dispute reduction) from the evaluation pipeline. |
| **PS Brief (PS 26100)** | Problem statement, solution narrative, and target user personas for hackathon / stakeholder briefings. |
| **AI Copilot** | Chat assistant grounded in GFR 2017, CVC guidelines, GeM rules, MII/MSE policy, and oil & gas standards. |

### Backend capabilities

- **In-memory tender store** with mock CPCL/GeM data (ready to swap for PostgreSQL or Firestore).
- **Google Gemini** (`GEMINI_MODEL`, default `gemini-2.5-flash`) for bid verification, CSQ/clarification notices, and copilot replies.
- **Rule-engine fallback** when `GEMINI_API_KEY` is not set (local demo mode).

---

## Tech stack

- **Frontend:** React 19, TypeScript, Vite 8, Tailwind CSS 4, Recharts, Motion, Lucide icons  
- **Backend:** Python 3.11+ with FastAPI (Uvicorn ASGI server), Pydantic validation, modular service layer  
- **AI:** `google-genai` Python SDK (server-side only; API key never exposed to the browser)

---

## Project structure

```
STAMAS---Smart-Tender-Analysis-Management-Assessment-System-main/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app, CORS, routers, error format
│   │   ├── api/                  # thin handlers: tenders.py, gemini.py, system.py
│   │   ├── services/             # gemini_service.py, tender_service.py,
│   │   │                         # compliance_service.py (rule engine), cartel_service.py
│   │   ├── db/                   # database.py, models.py, repositories.py (Neon PostgreSQL)
│   │   ├── schemas/              # Pydantic models: tender, bidder, gemini, analytics
│   │   ├── models/               # lightweight domain metadata
│   │   └── core/                 # config.py, errors.py
│   ├── alembic/                # DB migrations (alembic upgrade head)
│   ├── requirements.txt
│   ├── .env.example            # includes DATABASE_URL template (real value in backend/.env only)
│   └── README.md
└── frontend/
    ├── src/
    │   ├── App.tsx             # Main UI (tabs, modals, charts)
    │   ├── data/tenderData.ts  # Types, mock tenders, SIH metrics (UI demo data)
    │   └── services/api.ts     # Fetch wrappers for the FastAPI REST API
    ├── package.json
    └── .env.example            # VITE_API_BASE_URL=http://localhost:8000
```

**Communication:** `React → HTTP REST → FastAPI → services → in-memory DB / Gemini`.
The frontend never imports backend files, and the backend key (`GEMINI_API_KEY`)
lives only in `backend/.env` (server-side). The legacy Node/Express files under
`backend/` (`server.ts`, `app.ts`, `routes/`, …) are superseded by `backend/app/`
and are no longer started by any npm script.

---

## Prerequisites

- **Node.js** 20+ for the React frontend (or **Bun** — lockfile `bun.lock` is included)
- **Python** 3.11+ for the FastAPI backend
- A **Gemini API key** ([Google AI Studio](https://aistudio.google.com/)) for full AI features (optional for demo fallback)

---

## Setup

1. **Backend** — create a venv and install dependencies:

   ```bash
   cd backend
   python -m venv .venv
   ```

   Windows:

   ```powershell
   .venv\Scripts\activate
   ```

   Then:

   ```bash
   pip install -r requirements.txt
   cp .env.example .env   # set GEMINI_API_KEY (optional)
   ```

2. **Frontend** — install dependencies:

   ```bash
   cd frontend
   npm install
   # or
   bun install
   ```

3. **Environment variables:**

   Backend (`backend/.env`):

   | Variable | Required | Description |
   |----------|----------|-------------|
   | `GEMINI_API_KEY` | Recommended | Server-side Gemini access for verify, notices, and copilot |
   | `GEMINI_MODEL` | Optional | Gemini model (default `gemini-2.5-flash`) |
   | `ALLOWED_ORIGINS` | Optional | CORS origins (default Vite `http://localhost:5173`) |
   | `PORT` | Optional | HTTP port (default `8000`) |

   Frontend (`frontend/.env`):

   | Variable | Required | Description |
   |----------|----------|-------------|
   | `VITE_API_BASE_URL` | Optional | FastAPI base URL (default `http://localhost:8000`) |

---

## Running the app

Backend (http://localhost:8000, Swagger at http://localhost:8000/api/docs):

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Frontend (http://localhost:5173):

```bash
cd frontend
npm run dev
```

Or run both together from the repo root:

```bash
npm run dev
```

| Command (repo root) | Purpose |
|---------|---------|
| `npm run dev` | Start FastAPI + Vite dev servers |
| `npm run build` | Build React app to `frontend/dist` |
| `npm run lint` | Typecheck the frontend via `tsc --noEmit` |

---

## API reference

Base URL: `http://localhost:8000`. Interactive docs: `/api/docs` (Swagger UI), `/api/redoc`.

### Tenders — `/api/tenders`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | List all tenders |
| `GET` | `/:id` | Get tender by ID |
| `POST` | `/` | Create tender (`title`, `tenderNo` required) |
| `POST` | `/:id/bids` | Ingest bidder; runs clause evaluation rules |

### Gemini — `/api/gemini`

| Method | Path | Body (summary) |
|--------|------|----------------|
| `POST` | `/verify-bid` | `tenderDetails`, `bidderDetails`, `clausesToVerify` |
| `POST` | `/generate-notice` | `tenderNo`, `tenderTitle`, `bidderName`, `deviations`, optional `contactOfficer` |
| `POST` | `/detect-cartel` | `tenderId` |
| `POST` | `/copilot-chat` | `message`, `tenderContext` |

### System — `/api/system`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Status, AI engine mode, DB connector info, uptime |
| `GET` | `/analytics` | SIH impact metrics and problem brief payload |

---

## Compliance & domain context

STAMAS is modeled around:

- **GFR 2017** and **CVC** procurement / vigilance guidelines  
- **GeM 4.0** technical evaluation workflows  
- **Make in India** (Class-I / Class-II local content) and **MSE** exemptions  
- Refinery standards (e.g. ASTM, API, NACE) in sample tender data  

Sample tenders and bidders in `frontend/src/data/tenderData.ts` are **demonstration data** for CPCL Manali Refinery scenarios—not live GeM integrations.

---

## Deployment notes

- Build the frontend with `npm run build` (`frontend/dist`) and host it as static
  files; run FastAPI behind a Python ASGI server (Uvicorn/Gunicorn) with the
  Gemini API.
- Set `GEMINI_API_KEY` in the host environment (never commit `.env`).
- JSON body handling supports large (10 MB scale) bid payloads.
- FastAPI listens on the configured `PORT` (default `8000`).

### Vercel (frontend + backend, one project)

1. `vercel import` this repo. Build settings are in `vercel.json` (frontend
   build → `frontend/dist`, `/api/*` → FastAPI serverless function).
2. In Vercel → Project Settings → Environment Variables, add:
   `GEMINI_API_KEY`, `GEMINI_MODEL`, `DATABASE_URL`
   (`postgresql+asyncpg://USER:PASSWORD@HOST/DATABASE?sslmode=require`),
   `DOCUMENT_STORAGE_PATH=/tmp/stamas-documents`.
3. Run migrations once from your machine against Neon:
   `cd backend && alembic upgrade head`.
4. Deploy. Frontend calls same-origin `/api/*`, so no CORS setup is needed.

Vercel limits to know: request bodies cap at ~4.5 MB on serverless
functions (uploads above that fail — move the backend to Render/Fly
for full 10 MB uploads), functions time out (Hobby 10s; analysis of
large packs can exceed it — retry), and `/tmp` files vanish between
invocations (extracted text/clauses stay safe in Neon).

---

## License

No license file is included in this repository. Add a `LICENSE` file or contact the project owners before redistribution.

---

## Acknowledgments

Built for **Smart India Hackathon** theme **Smart Automation** (Software Edition), targeting PSU procurement officers, tender committees, and Chief Vigilance Officers evaluating high-value GeM technical bids.
