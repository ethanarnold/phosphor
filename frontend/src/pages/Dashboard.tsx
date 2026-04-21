import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import Empty from '../components/Empty'
import ScoreBar from '../components/ScoreBar'
import {
  useApi,
  useApiKeyPrefix,
  type AdoptionMetrics,
  type RankedOpportunityList,
  type ScanList,
} from '../lib/api'
import { useLab, useLabState } from '../lib/queries'

function Tile({ num, label }: { num: number | string; label: string }) {
  return (
    <div className="tile">
      <div className="num">{num}</div>
      <div className="lbl">{label}</div>
    </div>
  )
}

export default function Dashboard() {
  const api = useApi()
  const keyPrefix = useApiKeyPrefix()
  const { data: lab } = useLab()
  const { data: state, isLoading: stateLoading } = useLabState(lab?.id)

  const { data: ranked } = useQuery<RankedOpportunityList | null>({
    queryKey: [keyPrefix, 'ranked-top', lab?.id],
    enabled: !!lab && !!state,
    queryFn: async () => {
      try {
        return await api<RankedOpportunityList>(
          `/api/v1/labs/${lab!.id}/opportunities/ranked?limit=5`,
        )
      } catch (e) {
        const err = e as { status?: number }
        if (err.status === 404) return null
        throw e
      }
    },
  })

  const { data: scans } = useQuery<ScanList>({
    queryKey: [keyPrefix, 'scans-recent', lab?.id],
    enabled: !!lab,
    queryFn: () => api<ScanList>(`/api/v1/labs/${lab!.id}/literature/scans?limit=5`),
  })

  const { data: metrics } = useQuery<AdoptionMetrics>({
    queryKey: [keyPrefix, 'metrics-7d', lab?.id],
    enabled: !!lab,
    queryFn: () =>
      api<AdoptionMetrics>(`/api/v1/labs/${lab!.id}/metrics/adoption?window_days=7`),
  })

  if (!lab) return null

  return (
    <>
      <header>
        <div>
          <h1>{lab.name}</h1>
          <div className="muted">Lab dashboard</div>
        </div>
      </header>

      {stateLoading ? (
        <div className="card">Loading state…</div>
      ) : !state ? (
        <Empty
          title="No lab state yet"
          body="Log an experiment or upload a document to seed the compressor."
          cta={
            <div className="row" style={{ justifyContent: 'center' }}>
              <Link to="/experiments"><button>Log experiment</button></Link>
              <Link to="/documents"><button className="ghost">Upload document</button></Link>
            </div>
          }
        />
      ) : (
        <div className="card">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <h2>Lab state</h2>
            <Link to="/state" className="muted">
              v{state.version} · {state.token_count ?? '—'} tokens →
            </Link>
          </div>
          <div className="tile-grid">
            <Tile num={state.state.equipment.length} label="Equipment" />
            <Tile num={state.state.techniques.length} label="Techniques" />
            <Tile num={state.state.expertise.length} label="Expertise" />
            <Tile num={state.state.organisms.length} label="Organisms" />
            <Tile num={state.state.reagents.length} label="Reagents" />
            <Tile num={state.state.experimental_history.length} label="Experiments" />
          </div>
        </div>
      )}

      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <h2>Top opportunities</h2>
          <Link to="/opportunities" className="muted">View all →</Link>
        </div>
        {!ranked || ranked.items.length === 0 ? (
          <p className="muted">
            No ranked opportunities yet.{' '}
            <Link to="/literature">Run a literature scan</Link> to populate.
          </p>
        ) : (
          <table>
            <thead>
              <tr>
                <th style={{ width: 28 }}>#</th>
                <th>Opportunity</th>
                <th style={{ width: 100 }}>Complexity</th>
                <th style={{ width: 200 }}>Match</th>
              </tr>
            </thead>
            <tbody>
              {ranked.items.map((r, i) => (
                <tr key={r.opportunity.id}>
                  <td>{i + 1}</td>
                  <td>
                    <Link to={`/opportunities/${r.opportunity.id}`}>
                      {r.opportunity.description.slice(0, 120)}
                      {r.opportunity.description.length > 120 ? '…' : ''}
                    </Link>
                  </td>
                  <td>
                    <span className={`tag complexity-${r.opportunity.estimated_complexity}`}>
                      {r.opportunity.estimated_complexity}
                    </span>
                  </td>
                  <td>
                    <ScoreBar value={r.score.composite} label="composite" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <h2>Activity (last 7 days)</h2>
          <Link to="/literature" className="muted">Literature →</Link>
        </div>
        <div className="tile-grid">
          <Tile num={metrics?.total_events ?? 0} label="Input events" />
          <Tile
            num={
              metrics?.by_type.find((t) => t.event_type.startsWith('experiment'))?.count ?? 0
            }
            label="Experiments logged"
          />
          <Tile
            num={
              metrics?.by_type.find((t) => t.event_type === 'document.upload')?.count ?? 0
            }
            label="Documents uploaded"
          />
          <Tile num={scans?.scans.length ?? 0} label="Recent scans" />
        </div>
        {(!metrics || metrics.total_events === 0) && (
          <p className="warning" style={{ marginTop: 12 }}>
            Compressor starvation warning: no input signals in 7 days.
          </p>
        )}
      </div>
    </>
  )
}
