import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import Empty from '../components/Empty'
import ScoreBar from '../components/ScoreBar'
import {
  useApi,
  useApiKeyPrefix,
  type RankedOpportunityList,
} from '../lib/api'
import { useLab } from '../lib/queries'

type Complexity = '' | 'low' | 'medium' | 'high'

export default function Opportunities() {
  const api = useApi()
  const keyPrefix = useApiKeyPrefix()
  const { data: lab } = useLab()
  const [complexity, setComplexity] = useState<Complexity>('')

  const { data, isLoading, error } = useQuery<RankedOpportunityList>({
    queryKey: [keyPrefix, 'ranked-all', lab?.id],
    enabled: !!lab,
    queryFn: () =>
      api<RankedOpportunityList>(
        `/api/v1/labs/${lab!.id}/opportunities/ranked?limit=100`,
      ),
  })

  const filtered =
    data?.items.filter((r) =>
      complexity ? r.opportunity.estimated_complexity === complexity : true,
    ) ?? []

  if (!lab) return null

  return (
    <>
      <header>
        <div>
          <div className="kicker">Research opportunities</div>
          <h1>Ranked by composite match</h1>
        </div>
        <Link to="/literature"><button className="ghost">Run scan</button></Link>
      </header>

      <div className="controls">
        <label>Complexity</label>
        <select
          value={complexity}
          onChange={(e) => setComplexity(e.target.value as Complexity)}
          style={{ width: 160 }}
        >
          <option value="">All</option>
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
        </select>
        <div className="muted" style={{ marginLeft: 'auto' }}>
          {filtered.length} {filtered.length === 1 ? 'opportunity' : 'opportunities'} · click a row to inspect
        </div>
      </div>

      {error ? (
        <div className="error">
          {(error as { detail?: string }).detail ?? 'Failed to load opportunities'}
        </div>
      ) : isLoading ? (
        <p className="muted">Loading…</p>
      ) : filtered.length === 0 ? (
        <Empty
          title="No opportunities yet"
          body="Run a literature scan to extract opportunities from PubMed and Semantic Scholar."
          cta={<Link to="/literature"><button>Run literature scan</button></Link>}
        />
      ) : (
        <div className="list">
          {filtered.map((r, i) => (
            <Link
              key={r.opportunity.id}
              to={`/opportunities/${r.opportunity.id}`}
              className="row-item"
              style={{ gridTemplateColumns: '32px 1fr 110px 80px 240px' }}
            >
              <div className="idx">{String(i + 1).padStart(2, '0')}</div>
              <div className="title">
                {r.opportunity.description.slice(0, 180)}
                {r.opportunity.description.length > 180 ? '…' : ''}
              </div>
              <div>
                <span className={`tag complexity-${r.opportunity.estimated_complexity}`}>
                  {r.opportunity.estimated_complexity}
                </span>
              </div>
              <div>
                <span className="tag">{r.opportunity.status}</span>
              </div>
              <ScoreBar value={r.score.composite} label="Composite" />
            </Link>
          ))}
        </div>
      )}
    </>
  )
}
