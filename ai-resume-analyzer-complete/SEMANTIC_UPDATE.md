# Semantic matching update

This build adds hybrid job matching:
- OpenAI `text-embedding-3-small` embeddings (1536 dimensions)
- resume and job vectors stored in Supabase pgvector
- cosine similarity through a Supabase RPC
- deterministic skill score + semantic score -> hybrid final score
- lazy backfill for older resumes that have no embedding
- UI shows final, skill, and semantic scores

## Local setup

Keep your existing `api/.env` and `.env.local` files; this source package intentionally does not contain secrets.

In `api`:
```bash
pip install -r requirements.txt
```

Add to `api/.env` if not already present:
```env
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

The database migration for the extra job-match score fields is already applied to the configured Supabase project. The SQL is also included under `supabase/migrations/`.

Restart FastAPI and Next.js, then upload a fresh resume or run Job Matcher. Existing resumes are lazily embedded the first time they are used by Job Matcher.
