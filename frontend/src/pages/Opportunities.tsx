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
        <h1>Opportunities</h1>
        <Link to="/literature"><button className="ghost">Run scan</button></Link>
      </header>

      <div className="card">
        <div className="row">
          <label style={{ margin: 0 }}>Complexity</label>
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
            Ranked by composite match · Click a row to inspect
          </div>
        </div>
      </div>

      {error ? (
        <div className="card">
          <div className="error">
            {(error as { detail?: string }).detail ?? 'Failed to load opportunities'}
          </div>
        </div>
      ) : isLoading ? (
        <div className="card">Loading…</div>
      ) : filtered.length === 0 ? (
        <Empty
          title="No opportunities yet"
          body="Run a literature scan to extract opportunities from PubMed and Semantic Scholar."
          cta={<Link to="/literature"><button>Run literature scan</button></Link>}
        />
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th style={{ width: 32 }}>#</th>
                <th>Opportunity</th>
                <th style={{ width: 110 }}>Complexity</th>
                <th style={{ width: 80 }}>Status</th>
                <th style={{ width: 220 }}>Composite</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r, i) => (
                <tr key={r.opportunity.id} className="clickable">
                  <td>{i + 1}</td>
                  <td>
                    <Link to={`/opportunities/${r.opportunity.id}`}>
                      {r.opportunity.description.slice(0, 180)}
                      {r.opportunity.description.length > 180 ? '…' : ''}
                    </Link>
                  </td>
                  <td>
                    <span className={`tag complexity-${r.opportunity.estimated_complexity}`}>
                      {r.opportunity.estimated_complexity}
                    </span>
                  </td>
                  <td><span className="tag">{r.opportunity.status}</span></td>
                  <td><ScoreBar value={r.score.composite} label="composite" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
