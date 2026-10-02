# AI Resume Analyzer & Job Matcher

## Apps
- `app/` — Next.js frontend
- `api/` — FastAPI resume parsing + analysis API
- Supabase — Auth, Postgres, Storage, pgvector

## Local development

### Frontend
```bash
npm install
cp .env.example .env.local
npm install
npm run dev
```

### API
```bash
cd api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Set the Supabase URL/key in `.env.local` and `api/.env`. `OPENAI_API_KEY` is optional; without it the API uses deterministic resume heuristics. For browser-to-API local development, keep `ALLOWED_ORIGINS=http://localhost:3000`.

The current Supabase project is already configured with RLS, a private `resumes` storage bucket, and the core database tables.
