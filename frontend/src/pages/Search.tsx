import { useState, type FormEvent } from 'react'
import { useApi, type SearchResponse } from '../lib/api'
import { useLab } from '../lib/queries'

export default function Search() {
  const api = useApi()
  const { data: lab } = useLab()
  const [q, setQ] = useState('')
  const [results, setResults] = useState<SearchResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!lab || !q.trim()) return
    setBusy(true)
    setError(null)
    try {
      const res = await api<SearchResponse>(
        `/api/v1/labs/${lab.id}/search?q=${encodeURIComponent(q)}&limit=25`,
      )
      setResults(res)
    } catch (err) {
      const e = err as { detail?: string }
      setError(e.detail ?? 'Search failed')
    } finally {
      setBusy(false)
    }
  }

  if (!lab) return null

  return (
    <>
      <header><h1>Search</h1></header>
      <form className="card" onSubmit={submit}>
        <p className="muted">
          Hybrid keyword + embedding search over your signals and ingested papers.
        </p>
        <div className="row">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="e.g. CRISPR knockout failures in HEK293"
            autoFocus
          />
          <button type="submit" disabled={busy || !q.trim()}>
            {busy ? 'Searching…' : 'Search'}
          </button>
        </div>
        {error && <div className="error" style={{ marginTop: 8 }}>{error}</div>}
      </form>

      {results && (
        <div className="card">
          <h2>{results.total} result{results.total === 1 ? '' : 's'}</h2>
          {results.hits.length === 0 ? (
            <p className="muted">Nothing matched. Try different terms.</p>
          ) : (
            <ul style={{ paddingLeft: 0, listStyle: 'none' }}>
              {results.hits.map((h) => (
                <li
                  key={`${h.kind}-${h.id}`}
                  style={{
                    padding: '0.5rem 0',
                    borderBottom: '1px solid var(--border)',
                  }}
                >
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <strong>
                      {h.title ?? `${h.kind}${h.signal_type ? `: ${h.signal_type}` : ''}`}
                    </strong>
                    <span className="muted">
                      {h.kind} · {h.matched_by} · {h.score.toFixed(2)}
                    </span>
                  </div>
                  <div>{h.snippet}</div>
                  <div className="muted" style={{ fontSize: 11 }}>
                    {new Date(h.created_at).toLocaleString()}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </>
  )
}
