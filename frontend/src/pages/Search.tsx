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
      <header>
        <div>
          <div className="kicker">Hybrid keyword + embedding</div>
          <h1>Search</h1>
        </div>
      </header>

      <form onSubmit={submit} style={{ marginBottom: 32 }}>
        <p className="muted" style={{ marginBottom: 12, maxWidth: '62ch' }}>
          Search across your signals and ingested papers.
        </p>
        <div className="row">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="e.g. CRISPR knockout failures in HEK293"
            autoFocus
            style={{ flex: 1 }}
          />
          <button type="submit" disabled={busy || !q.trim()}>
            {busy ? 'Searching…' : 'Search'}
          </button>
        </div>
        {error && <div className="error" style={{ marginTop: 12 }}>{error}</div>}
      </form>

      {results && (
        <section className="section">
          <div className="section-head">
            <div className="label">
              {results.total} result{results.total === 1 ? '' : 's'}
            </div>
          </div>
          {results.hits.length === 0 ? (
            <p className="muted">Nothing matched. Try different terms.</p>
          ) : (
            <div className="list">
              {results.hits.map((h) => (
                <div
                  key={`${h.kind}-${h.id}`}
                  className="row-item"
                  style={{ gridTemplateColumns: '1fr', alignItems: 'start' }}
                >
                  <div>
                    <div
                      className="row"
                      style={{ justifyContent: 'space-between', marginBottom: 4 }}
                    >
                      <strong style={{ fontSize: 14 }}>
                        {h.title ?? `${h.kind}${h.signal_type ? `: ${h.signal_type}` : ''}`}
                      </strong>
                      <span className="mono" style={{ fontSize: 11, color: 'var(--ink-3)' }}>
                        {h.kind} · {h.matched_by} · {h.score.toFixed(2)}
                      </span>
                    </div>
                    <div style={{ color: 'var(--ink-2)', marginBottom: 4 }}>{h.snippet}</div>
                    <div className="mono" style={{ fontSize: 11, color: 'var(--ink-3)' }}>
                      {new Date(h.created_at).toLocaleString()}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </>
  )
}
