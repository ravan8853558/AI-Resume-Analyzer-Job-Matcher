'use client'
import { useState } from 'react'
import { createClient } from '@/lib/supabase/client'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function JobMatcher({ resumes }: { resumes: any[] }) {
  const [resumeId, setResumeId] = useState(resumes[0]?.id || '')
  const [title, setTitle] = useState('')
  const [company, setCompany] = useState('')
  const [description, setDescription] = useState('')
  const [result, setResult] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const supabase = createClient()

  async function run() {
    if (!resumeId || !description.trim()) return
    setBusy(true); setError(''); setResult(null)
    try {
      const { data: { session } } = await supabase.auth.getSession()
      const r = await fetch(`${API}/api/jobs/match`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session?.access_token}`
        },
        body: JSON.stringify({
          resume_id: resumeId,
          job_title: title || 'Target job',
          company: company || null,
          description
        })
      })
      const data = await r.json()
      if (!r.ok) throw new Error(data.detail || 'Matching failed')
      setResult(data.match)
    } catch (e:any) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="mt-10 rounded-2xl border border-zinc-800 bg-zinc-950 p-6">
      <div>
        <p className="text-sm text-zinc-500">Job matcher</p>
        <h2 className="mt-1 text-2xl font-bold">Compare your resume with a job</h2>
        <p className="mt-2 text-xs text-zinc-500">
          Hybrid matching uses deterministic skill overlap plus semantic similarity.
        </p>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-3">
        <select value={resumeId} onChange={e=>setResumeId(e.target.value)} className="rounded-lg border border-zinc-800 bg-zinc-900 p-3 text-sm">
          {resumes.map(r=><option key={r.id} value={r.id}>{r.file_name}</option>)}
        </select>
        <input value={title} onChange={e=>setTitle(e.target.value)} placeholder="Job title" className="rounded-lg border border-zinc-800 bg-zinc-900 p-3 text-sm"/>
        <input value={company} onChange={e=>setCompany(e.target.value)} placeholder="Company (optional)" className="rounded-lg border border-zinc-800 bg-zinc-900 p-3 text-sm"/>
      </div>

      <textarea value={description} onChange={e=>setDescription(e.target.value)} placeholder="Paste the complete job description here…" rows={8} className="mt-3 w-full rounded-lg border border-zinc-800 bg-zinc-900 p-3 text-sm outline-none"/>

      <button onClick={run} disabled={busy || !resumeId || !description.trim()} className="mt-3 rounded-lg bg-white px-5 py-3 text-sm font-semibold text-black disabled:opacity-40">
        {busy?'Matching…':'Match job'}
      </button>

      {error&&<p className="mt-3 text-sm text-red-400">{error}</p>}

      {result&&<div className="mt-6 grid gap-4 md:grid-cols-4">
        <div className="rounded-xl border border-zinc-800 p-4">
          <p className="text-sm text-zinc-500">Final match</p>
          <p className="mt-1 text-3xl font-bold">{Math.round(result.match_score)}%</p>
        </div>
        <div className="rounded-xl border border-zinc-800 p-4">
          <p className="text-sm text-zinc-500">Skill match</p>
          <p className="mt-1 text-2xl font-bold">{result.skill_match_score != null ? Math.round(result.skill_match_score) : '—'}%</p>
        </div>
        <div className="rounded-xl border border-zinc-800 p-4">
          <p className="text-sm text-zinc-500">Semantic match</p>
          <p className="mt-1 text-2xl font-bold">{result.semantic_score != null ? Math.round(result.semantic_score) : '—'}%</p>
        </div>
        <div className="rounded-xl border border-zinc-800 p-4">
          <p className="text-sm text-zinc-500">Scoring</p>
          <p className="mt-2 text-sm text-zinc-300">{result.scoring_version === 'hybrid-v1' ? 'Hybrid v1' : 'Skill-only fallback'}</p>
        </div>
        <div className="rounded-xl border border-zinc-800 p-4 md:col-span-2">
          <p className="text-sm text-zinc-500">Matched skills</p>
          <p className="mt-2 text-sm text-zinc-300">{result.matched_skills?.join(', ') || 'None detected'}</p>
        </div>
        <div className="rounded-xl border border-zinc-800 p-4 md:col-span-2">
          <p className="text-sm text-zinc-500">Missing skills</p>
          <p className="mt-2 text-sm text-zinc-300">{result.missing_skills?.join(', ') || 'None detected'}</p>
        </div>
        {result.explanation && <p className="text-xs text-zinc-500 md:col-span-4">{result.explanation}</p>}
      </div>}
    </section>
  )
}
