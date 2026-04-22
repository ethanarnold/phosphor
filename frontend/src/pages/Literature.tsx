import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import {
  useApi,
  useApiKeyPrefix,
  type LiteratureScan,
  type ScanList,
  type ScanRequest,
} from '../lib/api'
import { useLab } from '../lib/queries'

function StatusTag({ status }: { status: string }) {
  const cls =
    status === 'completed'
      ? 'complexity-low'
      : status === 'failed'
      ? 'complexity-high'
      : status === 'running' || status === 'pending'
      ? 'complexity-medium'
      : ''
  return <span className={`tag ${cls}`}>{status}</span>
}

export default function Literature() {
  const api = useApi()
  const qc = useQueryClient()
  const keyPrefix = useApiKeyPrefix()
  const { data: lab } = useLab()
  const [terms, setTerms] = useState('')
  const [field, setField] = useState('')
  const [maxResults, setMaxResults] = useState(50)

  const { data, isLoading } = useQuery<ScanList>({
    queryKey: [keyPrefix, 'scans', lab?.id],
    enabled: !!lab,
    queryFn: () => api<ScanList>(`/api/v1/labs/${lab!.id}/literature/scans?limit=20`),
    refetchInterval: (query) => {
      const list = query.state.data
      const inFlight = list?.scans.some(
        (s) => s.status === 'pending' || s.status === 'running',
      )
      return inFlight ? 4000 : false
    },
  })

  const trigger = useMutation({
    mutationFn: (req: ScanRequest) =>
      api<LiteratureScan>(`/api/v1/labs/${lab!.id}/literature/scan`, {
        method: 'POST',
        body: req,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [keyPrefix, 'scans', lab?.id] })
      setTerms('')
    },
  })

  if (!lab) return null

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const queryTerms = terms
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean)
    if (!queryTerms.length) return
    trigger.mutate({
      query_terms: queryTerms,
      field_of_study: field || null,
      max_results: maxResults,
      sources: ['pubmed', 'semantic_scholar'],
    })
  }

  return (
    <>
      <header>
        <div>
          <div className="kicker">PubMed + Semantic Scholar</div>
          <h1>Literature scans</h1>
        </div>
      </header>

      <section className="section">
        <div className="section-head">
          <div className="label">Run a scan</div>
        </div>
      <form className="stack" onSubmit={submit} style={{ gap: 16 }}>
        <div>
          <label>Query terms (comma-separated)</label>
          <input
            value={terms}
            onChange={(e) => setTerms(e.target.value)}
            placeholder="CRISPR base editing, in vivo delivery, AAV"
          />
        </div>
        <div className="row">
          <div style={{ flex: 1 }}>
            <label>Field of study (optional)</label>
            <input
              value={field}
              onChange={(e) => setField(e.target.value)}
              placeholder="e.g. molecular biology"
            />
          </div>
          <div style={{ width: 140 }}>
            <label>Max results</label>
            <input
              type="number"
              value={maxResults}
              min={1}
              max={500}
              onChange={(e) => setMaxResults(Number(e.target.value))}
            />
          </div>
        </div>
        <div className="row">
          <button type="submit" disabled={trigger.isPending || !terms.trim()}>
            {trigger.isPending ? 'Queuing…' : 'Run scan'}
          </button>
          <span className="muted">
            Pulls PubMed + Semantic Scholar, dedupes by DOI/PMID, extracts opportunities.
          </span>
        </div>
        {trigger.error && (
          <div className="error">
            {(trigger.error as { detail?: string }).detail ?? 'Could not queue scan'}
          </div>
        )}
      </form>
      </section>

      <section className="section">
        <div className="section-head">
          <div className="label">Recent scans</div>
        </div>
        {isLoading ? (
          <p className="muted">Loading…</p>
        ) : !data || data.scans.length === 0 ? (
          <p className="muted">No scans yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Query</th>
                <th>Status</th>
                <th>Papers</th>
                <th>New</th>
                <th>Opportunities</th>
                <th>Started</th>
              </tr>
            </thead>
            <tbody>
              {data.scans.map((s) => {
                const params = s.query_params as Record<string, unknown>
                const qTerms = Array.isArray(params.query_terms)
                  ? (params.query_terms as string[]).join(', ')
                  : '—'
                return (
                  <tr key={s.id}>
                    <td>{qTerms}</td>
                    <td>
                      <StatusTag status={s.status} />
                      {s.error_message && (
                        <div style={{ color: 'var(--danger)', fontSize: 12, marginTop: 4 }}>
                          {s.error_message}
                        </div>
                      )}
                    </td>
                    <td>{s.papers_found}</td>
                    <td>{s.papers_new}</td>
                    <td>{s.opportunities_extracted}</td>
                    <td className="muted">
                      {new Date(s.started_at).toLocaleString()}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </section>
    </>
  )
}
