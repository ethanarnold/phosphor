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

function Metric({ num, label }: { num: number | string; label: string }) {
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
          <div className="kicker">Lab dashboard</div>
          <h1>{lab.name}</h1>
        </div>
      </header>

      {stateLoading ? (
        <p className="muted">Loading state…</p>
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
        <section className="section">
          <div className="section-head">
            <div>
              <div className="label">01 / Lab state</div>
              <h2>Compressed capability</h2>
            </div>
            <Link to="/state" className="muted">
              v{state.version} · {state.token_count ?? '—'} tokens →
            </Link>
          </div>
          <div className="tile-grid">
            <Metric num={state.state.equipment.length} label="Equipment" />
            <Metric num={state.state.techniques.length} label="Techniques" />
            <Metric num={state.state.expertise.length} label="Expertise" />
            <Metric num={state.state.organisms.length} label="Organisms" />
            <Metric num={state.state.reagents.length} label="Reagents" />
            <Metric num={state.state.experimental_history.length} label="Experiments" />
          </div>
        </section>
      )}

      <section className="section">
        <div className="section-head">
          <div>
            <div className="label">02 / Top opportunities</div>
            <h2>Ranked against your lab</h2>
          </div>
          <Link to="/opportunities" className="muted">View all →</Link>
        </div>
        {!ranked || ranked.items.length === 0 ? (
          <p className="muted">
            No ranked opportunities yet.{' '}
            <Link to="/literature">Run a literature scan</Link> to populate.
          </p>
        ) : (
          <div className="list">
            {ranked.items.map((r, i) => (
              <Link
                key={r.opportunity.id}
                to={`/opportunities/${r.opportunity.id}`}
                className="row-item"
                style={{ gridTemplateColumns: '28px 1fr 100px 240px' }}
              >
                <div className="idx">{String(i + 1).padStart(2, '0')}</div>
                <div className="title">
                  {r.opportunity.description.slice(0, 140)}
                  {r.opportunity.description.length > 140 ? '…' : ''}
                </div>
                <div>
                  <span className={`tag complexity-${r.opportunity.estimated_complexity}`}>
                    {r.opportunity.estimated_complexity}
                  </span>
                </div>
                <ScoreBar value={r.score.composite} label="Composite" />
              </Link>
            ))}
          </div>
        )}
      </section>

      <section className="section">
        <div className="section-head">
          <div>
            <div className="label">03 / Activity · last 7 days</div>
            <h2>Input signals</h2>
          </div>
          <Link to="/literature" className="muted">Literature →</Link>
        </div>
        <div className="tile-grid">
          <Metric num={metrics?.total_events ?? 0} label="Input events" />
          <Metric
            num={
              metrics?.by_type.find((t) => t.event_type.startsWith('experiment'))?.count ?? 0
            }
            label="Experiments logged"
          />
          <Metric
            num={
              metrics?.by_type.find((t) => t.event_type === 'document.upload')?.count ?? 0
            }
            label="Documents uploaded"
          />
          <Metric num={scans?.scans.length ?? 0} label="Recent scans" />
        </div>
        {(!metrics || metrics.total_events === 0) && (
          <p className="warning" style={{ marginTop: 16 }}>
            Compressor starvation warning: no input signals in 7 days.
          </p>
        )}
      </section>
    </>
  )
}
