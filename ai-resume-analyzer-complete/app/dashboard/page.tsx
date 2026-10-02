'use client'
import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase/client'
import UploadForm from './upload-form'
import JobMatcher from './job-matcher'

export default function Dashboard() {
  const [email, setEmail] = useState('')
  const [resumes, setResumes] = useState<any[]>([])
  const [selected, setSelected] = useState<any>(null)
  const supabase = createClient()

  async function load() {
    const { data: { user } } = await supabase.auth.getUser()
    if (user) setEmail(user.email || '')
    const { data } = await supabase.from('resumes').select('id,file_name,file_type,parsed_data,created_at').order('created_at', { ascending: false })
    setResumes(data || [])
  }
  useEffect(() => { load() }, [])

  async function signOut() { await supabase.auth.signOut(); window.location.href = '/login' }

  return <main className="min-h-screen p-6 md:p-10"><div className="mx-auto max-w-6xl">
    <header className="flex items-start justify-between gap-4"><div><p className="text-sm text-zinc-500">AI Resume Analyzer</p><h1 className="mt-1 text-3xl font-bold">Career dashboard</h1><p className="mt-1 text-sm text-zinc-400">{email}</p></div><button onClick={signOut} className="rounded-lg border border-zinc-800 px-4 py-2 text-sm">Sign out</button></header>
    <section className="mt-8 grid gap-4 md:grid-cols-3"><Stat label="Resumes" value={resumes.length}/><Stat label="Latest score" value={resumes[0]?.parsed_data?.resume_score != null ? `${Math.round(resumes[0].parsed_data.resume_score)}/100` : '—'}/><Stat label="Skills detected" value={resumes[0]?.parsed_data?.skills?.length ?? '—'}/></section>
    <section className="mt-8"><UploadForm onComplete={(r) => { setSelected(r.analysis); load() }} /></section>
    {selected && <Analysis analysis={selected} />}
    {resumes.length > 0 && <JobMatcher resumes={resumes} />}
    <section className="mt-10"><h2 className="text-lg font-semibold">Resume history</h2><div className="mt-4 space-y-3">{resumes.length === 0 ? <p className="text-sm text-zinc-500">No resumes analyzed yet.</p> : resumes.map(r => <button key={r.id} onClick={() => setSelected(r.parsed_data)} className="w-full rounded-xl border border-zinc-800 bg-zinc-950 p-4 text-left hover:border-zinc-600"><div className="flex justify-between gap-4"><span className="font-medium">{r.file_name}</span><span className="text-sm text-zinc-400">{r.parsed_data?.resume_score ?? '—'}/100</span></div><p className="mt-1 text-xs text-zinc-500">{new Date(r.created_at).toLocaleString()}</p></button>)}</div></section>
  </div></main>
}
function Stat({label,value}:{label:string,value:any}) { return <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-5"><p className="text-sm text-zinc-500">{label}</p><p className="mt-2 text-3xl font-bold">{value}</p></div> }
function Analysis({analysis}:{analysis:any}) { return <section className="mt-8 rounded-2xl border border-zinc-800 bg-zinc-950 p-6"><div className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-sm text-zinc-500">Latest analysis</p><h2 className="mt-1 text-2xl font-bold">Resume score: {Math.round(analysis.resume_score || 0)}/100</h2></div><p className="text-sm text-zinc-400">{analysis.word_count || 0} words · {analysis.quantified_achievements || 0} quantified achievements</p></div><div className="mt-6"><p className="text-sm font-medium">Detected skills</p><div className="mt-3 flex flex-wrap gap-2">{(analysis.skills || []).map((s:string)=><span key={s} className="rounded-full border border-zinc-700 px-3 py-1 text-xs text-zinc-300">{s}</span>)}</div></div><div className="mt-6 grid gap-6 md:grid-cols-2"><div><p className="text-sm font-medium">Recommendations</p><ul className="mt-3 space-y-2 text-sm text-zinc-400">{(analysis.recommendations || []).map((x:string,i:number)=><li key={i}>• {x}</li>)}</ul></div><div><p className="text-sm font-medium">Sections detected</p><div className="mt-3 grid grid-cols-2 gap-2">{Object.entries(analysis.sections || {}).map(([k,v]:any)=><div key={k} className="rounded-lg bg-zinc-900 px-3 py-2 text-sm"><span className="capitalize">{k}</span><span className="float-right">{v ? '✓' : '—'}</span></div>)}</div></div></div></section> }
