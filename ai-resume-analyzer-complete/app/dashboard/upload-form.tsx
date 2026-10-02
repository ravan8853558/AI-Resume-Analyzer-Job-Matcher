'use client'
import { useRef, useState } from 'react'
import { createClient } from '@/lib/supabase/client'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function UploadForm({ onComplete }: { onComplete: (result: any) => void }) {
  const input = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const supabase = createClient()

  async function upload() {
    const file = input.current?.files?.[0]
    if (!file) return
    setBusy(true); setError('')
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session?.access_token) throw new Error('Your session has expired. Please sign in again.')
      const body = new FormData(); body.append('file', file)
      const res = await fetch(`${API}/api/resumes/analyze`, { method: 'POST', headers: { Authorization: `Bearer ${session.access_token}` }, body })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Analysis failed')
      onComplete(data); if (input.current) input.current.value = ''
    } catch (e: any) { setError(e.message || 'Upload failed') }
    finally { setBusy(false) }
  }

  return <div className="rounded-2xl border border-dashed border-zinc-700 bg-zinc-950/60 p-8">
    <div className="text-center">
      <h2 className="text-xl font-semibold">Analyze a resume</h2>
      <p className="mt-2 text-sm text-zinc-400">PDF or DOCX · max 10 MB</p>
      <input ref={input} type="file" accept=".pdf,.docx" onChange={upload} disabled={busy} className="mt-6 block w-full text-sm text-zinc-400 file:mr-4 file:rounded-lg file:border-0 file:bg-white file:px-4 file:py-2 file:font-medium file:text-black" />
      {busy && <p className="mt-4 text-sm text-zinc-300">Parsing resume and generating analysis…</p>}
      {error && <p className="mt-4 text-sm text-red-400">{error}</p>}
    </div>
  </div>
}
