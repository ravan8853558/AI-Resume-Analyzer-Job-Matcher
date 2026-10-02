import io
import json
import os
import re
import uuid
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pypdf import PdfReader
from docx import Document

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://otfgssjyjjmpjcijcotw.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6-mini")
OPENAI_EMBEDDING_MODEL = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "10"))

# Hybrid scoring weights. Keyword/skill evidence remains deterministic; semantic
# similarity adds contextual matching without letting an LLM invent the score.
SEMANTIC_WEIGHT = 0.60
SKILL_WEIGHT = 0.40

app = FastAPI(title="AI Resume Analyzer API", version="0.2.0")

ALLOWED_ORIGINS = [
    x.strip()
    for x in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if x.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

SKILL_ALIASES = {
    "javascript": "JavaScript", "typescript": "TypeScript", "python": "Python",
    "java": "Java", "c++": "C++", "c#": "C#", "react": "React",
    "next.js": "Next.js", "nextjs": "Next.js", "node.js": "Node.js", "nodejs": "Node.js",
    "fastapi": "FastAPI", "django": "Django", "flask": "Flask", "sql": "SQL",
    "postgresql": "PostgreSQL", "postgres": "PostgreSQL", "mongodb": "MongoDB",
    "redis": "Redis", "docker": "Docker", "kubernetes": "Kubernetes", "aws": "AWS",
    "azure": "Azure", "gcp": "GCP", "git": "Git", "github": "GitHub",
    "machine learning": "Machine Learning", "deep learning": "Deep Learning",
    "artificial intelligence": "AI", "tensorflow": "TensorFlow", "pytorch": "PyTorch",
    "pandas": "Pandas", "numpy": "NumPy", "scikit-learn": "scikit-learn",
    "cybersecurity": "Cybersecurity", "linux": "Linux", "rest api": "REST API",
    "graphql": "GraphQL", "figma": "Figma", "tailwind": "Tailwind CSS",
}


def auth_headers(authorization: str | None) -> dict[str, str]:
    if not SUPABASE_KEY:
        raise HTTPException(500, "SUPABASE_PUBLISHABLE_KEY is not configured")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Authentication required")
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": authorization,
        "Content-Type": "application/json",
    }


async def current_user(authorization: str | None) -> dict[str, Any]:
    headers = auth_headers(authorization)
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(f"{SUPABASE_URL}/auth/v1/user", headers=headers)
    if r.status_code != 200:
        raise HTTPException(401, "Invalid or expired session")
    return r.json()


def extract_pdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages).strip()


def extract_docx(data: bytes) -> str:
    doc = Document(io.BytesIO(data))
    chunks = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            chunks.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(x for x in chunks if x.strip()).strip()


def normalize_skills(text: str) -> list[str]:
    lower = text.lower()
    found: set[str] = set()
    for needle, label in SKILL_ALIASES.items():
        if re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])", lower):
            found.add(label)
    return sorted(found)


def heuristic_analysis(text: str) -> dict[str, Any]:
    skills = normalize_skills(text)
    sections = {
        name: bool(re.search(rf"\b{name}\b", text, re.I))
        for name in ["experience", "education", "projects", "skills", "certifications"]
    }
    quantified = len(
        re.findall(
            r"\b\d+(?:\.\d+)?\s*(?:%|years?|months?|users?|projects?|clients?|revenue|ms|seconds?)\b",
            text,
            re.I,
        )
    )
    bullets = len(re.findall(r"(?:^|\n)\s*[•*-]\s+", text))
    word_count = len(re.findall(r"\b\w+\b", text))
    score = 45
    score += min(len(skills) * 3, 24)
    score += min(quantified * 3, 12)
    score += sum(5 for present in sections.values() if present)
    if bullets >= 5:
        score += 4
    if word_count < 250:
        score -= 10
    score = max(0, min(100, score))
    recommendations = []
    if not sections["experience"]:
        recommendations.append("Add a clear Experience section with role, company, dates, and outcomes.")
    if not sections["projects"]:
        recommendations.append("Add 2–4 relevant projects with your contribution and measurable results.")
    if quantified < 2:
        recommendations.append("Use measurable impact: percentages, scale, latency, users, revenue, or time saved.")
    if len(skills) < 6:
        recommendations.append("Make the technical skills section more explicit and align it with target roles.")
    if word_count < 250:
        recommendations.append("The resume appears short; add evidence of experience rather than filler text.")
    return {
        "resume_score": score,
        "skills": skills,
        "word_count": word_count,
        "sections": sections,
        "quantified_achievements": quantified,
        "recommendations": recommendations[:6],
    }


async def ai_analysis(text: str) -> dict[str, Any]:
    base = heuristic_analysis(text)
    if not OPENAI_API_KEY:
        return base
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You analyze resumes. Return JSON only with resume_score (0-100), "
                        "summary, strengths (array), weaknesses (array), recommendations (array), "
                        "skills (array), sections (object), quantified_achievements (number). "
                        "Do not invent facts."
                    ),
                },
                {"role": "user", "content": text[:30000]},
            ],
        )
        parsed = json.loads(response.choices[0].message.content or "{}")
        return {**base, **parsed, "skills": parsed.get("skills") or base["skills"]}
    except Exception:
        # Resume analysis must remain usable if the optional LLM analysis is
        # unavailable. Semantic embedding has its own explicit error path.
        return base


async def generate_embedding(text: str) -> list[float]:
    if not OPENAI_API_KEY:
        raise HTTPException(503, "OPENAI_API_KEY is not configured; semantic matching is unavailable")

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        response = await client.embeddings.create(
            model=OPENAI_EMBEDDING_MODEL,
            input=text[:30000],
        )
        embedding = response.data[0].embedding
        if len(embedding) != 1536:
            raise HTTPException(
                500,
                f"Embedding dimension mismatch: expected 1536, got {len(embedding)}",
            )
        return embedding
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            502,
            f"Embedding generation failed using {OPENAI_EMBEDDING_MODEL}: {exc}",
        )


async def supabase_insert(
    path: str,
    authorization: str,
    payload: Any,
    params: str = "",
):
    headers = auth_headers(authorization)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{SUPABASE_URL}/rest/v1/{path}{params}",
            headers={**headers, "Prefer": "return=representation"},
            json=payload,
        )
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text[:500])
    return r.json()


async def supabase_patch(
    path: str,
    authorization: str,
    payload: Any,
    params: str = "",
):
    headers = auth_headers(authorization)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.patch(
            f"{SUPABASE_URL}/rest/v1/{path}{params}",
            headers={**headers, "Prefer": "return=representation"},
            json=payload,
        )
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text[:500])
    return r.json()


async def rpc_single_job_similarity(
    authorization: str,
    query_embedding: list[float],
    job_id: str,
) -> float | None:
    headers = auth_headers(authorization)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/match_single_job_by_embedding",
            headers=headers,
            json={"query_embedding": query_embedding, "target_job_id": job_id},
        )
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text[:500])

    value = r.json()
    if value is None:
        return None
    return float(value)


async def get_resume(
    authorization: str,
    user_id: str,
    resume_id: str,
) -> dict[str, Any]:
    headers = auth_headers(authorization)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{SUPABASE_URL}/rest/v1/resumes"
            f"?select=id,raw_text,parsed_data,embedding"
            f"&user_id=eq.{user_id}&id=eq.{resume_id}",
            headers=headers,
        )
    if r.status_code >= 400 or not r.json():
        raise HTTPException(404, "Resume not found")
    return r.json()[0]


async def ensure_resume_embedding(
    authorization: str,
    resume: dict[str, Any],
) -> list[float]:
    # Existing resumes from the pre-semantic MVP have null embeddings.
    # Backfill them lazily when the user first uses that resume for matching.
    if resume.get("embedding") is not None:
        return resume["embedding"]

    embedding = await generate_embedding(resume.get("raw_text") or "")
    await supabase_patch(
        "resumes",
        authorization,
        {"embedding": embedding},
        f"?id=eq.{resume['id']}",
    )
    return embedding


class MatchRequest(BaseModel):
    resume_id: str
    job_title: str = "Target job"
    company: str | None = None
    description: str


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "semantic_matching": bool(OPENAI_API_KEY),
        "embedding_model": OPENAI_EMBEDDING_MODEL,
    }


@app.post("/api/resumes/analyze")
async def analyze_resume(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
):
    user = await current_user(authorization)
    filename = file.filename or "resume"
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext not in {"pdf", "docx"}:
        raise HTTPException(400, "Only PDF and DOCX resumes are supported")

    data = await file.read()
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {MAX_UPLOAD_MB} MB limit")

    try:
        text = extract_pdf(data) if ext == "pdf" else extract_docx(data)
    except Exception as exc:
        raise HTTPException(400, f"Could not parse resume: {exc}")
    if len(text.strip()) < 80:
        raise HTTPException(400, "Could not extract enough text from this resume")

    uid = user["id"]
    resume_id = str(uuid.uuid4())
    safe_filename = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._") or "resume"
    storage_path = f"{uid}/{resume_id}/{safe_filename}"
    headers = auth_headers(authorization)

    async with httpx.AsyncClient(timeout=60) as client:
        upload = await client.post(
            f"{SUPABASE_URL}/storage/v1/object/resumes/{storage_path}",
            headers={
                **headers,
                "Content-Type": file.content_type or "application/octet-stream",
                "x-upsert": "false",
            },
            content=data,
        )
    if upload.status_code >= 400:
        raise HTTPException(
            upload.status_code,
            f"Storage upload failed: {upload.text[:300]}",
        )

    analysis = await ai_analysis(text)

    # Generate the semantic vector during upload. This is deliberately
    # independent of LLM resume scoring, so scoring remains deterministic.
    embedding = await generate_embedding(text)
    analysis["semantic_embedding_model"] = OPENAI_EMBEDDING_MODEL
    analysis["semantic_embedding_ready"] = True

    resume_row = {
        "id": resume_id,
        "user_id": uid,
        "file_name": filename,
        "file_path": storage_path,
        "file_type": ext,
        "raw_text": text,
        "parsed_data": analysis,
        "embedding": embedding,
    }

    rows = await supabase_insert("resumes", authorization, resume_row)
    await supabase_insert(
        "resume_analyses",
        authorization,
        {
            "resume_id": resume_id,
            "user_id": uid,
            "ats_score": analysis.get("resume_score"),
            "analysis": analysis,
        },
    )
    return {"resume": rows[0], "analysis": analysis}


def skill_match(
    resume_skills: list[str],
    job_text: str,
) -> tuple[list[str], list[str], float]:
    job_skills = normalize_skills(job_text)
    resume_set = {x.lower(): x for x in resume_skills}
    job_set = {x.lower(): x for x in job_skills}
    matched = sorted(resume_set[k] for k in resume_set.keys() & job_set.keys())
    missing = sorted(job_set[k] for k in job_set.keys() - resume_set.keys())
    score = 0.0 if not job_set else round(len(matched) / len(job_set) * 100, 2)
    return matched, missing, score


@app.post("/api/jobs/match")
async def match_job(
    payload: MatchRequest,
    authorization: str | None = Header(default=None),
):
    user = await current_user(authorization)
    resume = await get_resume(authorization, user["id"], payload.resume_id)

    resume_skills = resume.get("parsed_data", {}).get("skills", [])
    matched, missing, skill_score = skill_match(resume_skills, payload.description)

    resume_embedding = await ensure_resume_embedding(authorization, resume)

    job_text = "\n".join(
        x for x in [payload.job_title, payload.company or "", payload.description] if x
    )
    job_embedding = await generate_embedding(job_text)

    job_rows = await supabase_insert(
        "jobs",
        authorization,
        {
            "user_id": user["id"],
            "title": payload.job_title,
            "company": payload.company,
            "description": payload.description,
            "requirements": {"skills": normalize_skills(payload.description)},
            "embedding": job_embedding,
        },
    )
    job = job_rows[0]
    job_id = job["id"]

    similarity = await rpc_single_job_similarity(
        authorization,
        resume_embedding,
        job_id,
    )

    if similarity is None:
        # This should only happen if the job vector was not stored.
        semantic_score = None
        final_score = skill_score
        scoring_version = "skill-only-fallback"
        explanation = (
            f"Skill match {skill_score:.1f}%. Semantic similarity was unavailable, "
            "so the final score uses deterministic skill overlap only."
        )
    else:
        semantic_score = round(max(0.0, min(1.0, similarity)) * 100, 2)
        final_score = round(
            skill_score * SKILL_WEIGHT + semantic_score * SEMANTIC_WEIGHT,
            2,
        )
        scoring_version = "hybrid-v1"
        explanation = (
            f"Hybrid score combines {SKILL_WEIGHT:.0%} deterministic skill overlap "
            f"({skill_score:.1f}%) and {SEMANTIC_WEIGHT:.0%} semantic similarity "
            f"({semantic_score:.1f}%)."
        )

    match_rows = await supabase_insert(
        "job_matches",
        authorization,
        {
            "resume_id": payload.resume_id,
            "job_id": job_id,
            "user_id": user["id"],
            "match_score": final_score,
            "skill_match_score": skill_score,
            "semantic_score": semantic_score,
            "scoring_version": scoring_version,
            "matched_skills": matched,
            "missing_skills": missing,
            "explanation": explanation,
        },
    )

    return {
        "job": job,
        "match": match_rows[0],
        "scoring": {
            "final_score": final_score,
            "skill_score": skill_score,
            "semantic_score": semantic_score,
            "semantic_model": OPENAI_EMBEDDING_MODEL,
            "version": scoring_version,
        },
    }


@app.get("/api/resumes")
async def list_resumes(authorization: str | None = Header(default=None)):
    user = await current_user(authorization)
    headers = auth_headers(authorization)
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            f"{SUPABASE_URL}/rest/v1/resumes"
            f"?select=id,file_name,file_type,parsed_data,created_at"
            f"&user_id=eq.{user['id']}&order=created_at.desc",
            headers=headers,
        )
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text[:300])
    return r.json()
