# STAMAS Backend — FastAPI (Python 3.11+)

React `frontend/` talks to this API over REST only. Gemini is accessed
server-side via the official `google-genai` SDK; the API key never reaches the browser.

## Quick start

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
cp .env.example .env   # set GEMINI_API_KEY (optional — rule engine fallback otherwise)
uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

## Environment

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Recommended | Server-side Gemini access; omit to run the Local Rule Engine |
| `GEMINI_MODEL` | Optional | Default `gemini-2.5-flash` |
| `ALLOWED_ORIGINS` | Optional | Comma-separated CORS origins (default Vite `http://localhost:5173`) |
| `PORT` | Optional | Default `8000` |

## Layout

```
app/
  main.py              # FastAPI app, CORS, routers, error format
  api/                 # thin route handlers: tenders.py, gemini.py, system.py
  services/            # gemini_service.py, tender_service.py, compliance_service.py, cartel_service.py
  db/                  # database.py (async engine/sessions), models.py (SQLAlchemy),
                       # repositories.py (data access), seed_data.py (static SIH analytics content only)
  schemas/             # Pydantic request/response models
  models/              # lightweight domain metadata
  core/                # config.py, errors.py
```

The legacy Node/Express files (`server.ts`, `app.ts`, `routes/`, `services/`,
`db/dbConnector.ts`, …) are superseded by `app/` and are no longer started by
any npm script. They remain on disk for reference only.
