import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import ScoreBar from '../components/ScoreBar'
import {
  useApi,
  useApiKeyPrefix,
  type FeedbackResponse,
  type GapAnalysis,
  type Opportunity,
  type Protocol,
  type RankedOpportunity,
  type RankedOpportunityList,
} from '../lib/api'
import { downloadMarkdown } from '../lib/protocolMarkdown'
import { useLab } from '../lib/queries'

function GapList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null
  return (
    <div>
      <div className="kicker" style={{ marginBottom: 6 }}>{title}</div>
      <div className="row" style={{ gap: 4 }}>
        {items.map((i) => (
          <span key={i} className="tag">{i}</span>
        ))}
      </div>
    </div>
  )
}

function ProtocolView({ protocol }: { protocol: Protocol }) {
  return (
    <div className="protocol">
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline' }}>
        <h3>{protocol.title}</h3>
        <button onClick={() => downloadMarkdown(protocol)} className="ghost">
          Export Markdown
        </button>
      </div>
      <div className="muted" style={{ marginBottom: 16 }}>
        Lab state v{protocol.lab_state_version} · {protocol.llm_model} · prompt {protocol.prompt_version}
      </div>

      {protocol.content.flagged_gaps.length > 0 && (
        <div className="warning" style={{ marginBottom: 16 }}>
          <strong>Flagged gaps:</strong> {protocol.content.flagged_gaps.join(', ')}
        </div>
      )}

      {protocol.content.materials.length > 0 && (
        <>
          <h4>Materials</h4>
          <ul>
            {protocol.content.materials.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </>
      )}

      {protocol.content.phases.map((phase, i) => (
        <div key={i} style={{ marginBottom: 16 }}>
          <h4>
            Phase {i + 1} · {phase.name}
            {phase.duration_estimate ? ` — ${phase.duration_estimate}` : ''}
          </h4>
          <ol>
            {phase.steps.map((step, j) => (
              <li key={j}>{step}</li>
            ))}
          </ol>
          {phase.materials_used.length > 0 && (
            <p className="muted">Materials: {phase.materials_used.join(', ')}</p>
          )}
        </div>
      ))}

      <h4>Expected outcomes</h4>
      <ul className="outcomes">
        {protocol.content.expected_outcomes.map((o, i) => (
          <li key={i}>{o}</li>
        ))}
      </ul>

      {protocol.content.citations.length > 0 && (
        <>
          <h4>Citations</h4>
          <ul className="citations">
            {protocol.content.citations.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

export default function OpportunityDetail() {
  const { opportunityId } = useParams<{ opportunityId: string }>()
  const api = useApi()
  const qc = useQueryClient()
  const keyPrefix = useApiKeyPrefix()
  const { data: lab } = useLab()
  const [protocol, setProtocol] = useState<Protocol | null>(null)
  const [genError, setGenError] = useState<string | null>(null)
  const [genBusy, setGenBusy] = useState(false)

  const { data: opp } = useQuery<Opportunity>({
    queryKey: [keyPrefix, 'opp', lab?.id, opportunityId],
    enabled: !!lab && !!opportunityId,
    queryFn: () =>
      api<Opportunity>(`/api/v1/labs/${lab!.id}/opportunities/${opportunityId}`),
  })

  const { data: ranked } = useQuery<RankedOpportunity | undefined>({
    queryKey: [keyPrefix, 'ranked-one', lab?.id, opportunityId],
    enabled: !!lab && !!opportunityId,
    queryFn: async () => {
      const list = await api<RankedOpportunityList>(
        `/api/v1/labs/${lab!.id}/opportunities/ranked?limit=200`,
      )
      return list.items.find((r) => r.opportunity.id === opportunityId)
    },
  })

  const { data: gaps, error: gapsError } = useQuery<GapAnalysis>({
    queryKey: [keyPrefix, 'gaps', lab?.id, opportunityId],
    enabled: !!lab && !!opportunityId,
    queryFn: () =>
      api<GapAnalysis>(
        `/api/v1/labs/${lab!.id}/opportunities/${opportunityId}/gaps`,
      ),
  })

  const decide = useMutation({
    mutationFn: (decision: 'accept' | 'reject') =>
      api<FeedbackResponse>(
        `/api/v1/labs/${lab!.id}/feedback/opportunities/${opportunityId}`,
        { method: 'POST', body: { decision } },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [keyPrefix, 'opp', lab?.id, opportunityId] })
      qc.invalidateQueries({ queryKey: [keyPrefix, 'ranked-all', lab?.id] })
      qc.invalidateQueries({ queryKey: [keyPrefix, 'ranked-top', lab?.id] })
    },
  })

  const generate = async () => {
    if (!lab || !opportunityId) return
    setGenBusy(true)
    setGenError(null)
    try {
      const p = await api<Protocol>(
        `/api/v1/labs/${lab.id}/opportunities/${opportunityId}/protocol`,
        { method: 'POST', body: {} },
      )
      setProtocol(p)
    } catch (e) {
      const err = e as { detail?: string }
      setGenError(err.detail ?? 'Protocol generation failed')
    } finally {
      setGenBusy(false)
    }
  }

  if (!lab || !opportunityId) return null

  if (!opp) {
    return <p className="muted">Loading…</p>
  }

  const composite = ranked?.score.composite
  const compositeHigh = composite != null && composite >= 0.85

  return (
    <>
      <header>
        <div>
          <Link to="/opportunities" className="muted">← All opportunities</Link>
        </div>
      </header>

      <div className="editorial">
        <article>
          <div className="kicker">Opportunity</div>
          <h1>{opp.description}</h1>

          <div className="row" style={{ marginTop: 0, marginBottom: 24, gap: 6 }}>
            <span className={`tag complexity-${opp.estimated_complexity}`}>
              {opp.estimated_complexity}
            </span>
            <span className="tag">{opp.status}</span>
            {opp.quality_score != null && (
              <span className="tag">quality {opp.quality_score.toFixed(2)}</span>
            )}
          </div>

          <div className="row" style={{ marginTop: 16, marginBottom: 32 }}>
            <button
              onClick={() => decide.mutate('accept')}
              disabled={decide.isPending || opp.status === 'accepted'}
            >
              {opp.status === 'accepted' ? 'Accepted' : 'Accept'}
            </button>
            <button
              className="ghost"
              onClick={() => decide.mutate('reject')}
              disabled={decide.isPending || opp.status === 'dismissed'}
            >
              {opp.status === 'dismissed' ? 'Dismissed' : 'Dismiss'}
            </button>
            {decide.error && (
              <span className="error">
                {(decide.error as { detail?: string }).detail ?? 'Feedback failed'}
              </span>
            )}
          </div>

          <section className="section" style={{ paddingTop: 0 }}>
            <div className="section-head">
              <div className="label">Requirements</div>
            </div>
            <div className="stack">
              {opp.required_equipment.length > 0 && (
                <div>
                  <div className="kicker" style={{ marginBottom: 6 }}>Equipment</div>
                  <div className="row" style={{ gap: 4 }}>
                    {opp.required_equipment.map((x) => (
                      <span key={x} className="tag">{x}</span>
                    ))}
                  </div>
                </div>
              )}
              {opp.required_techniques.length > 0 && (
                <div>
                  <div className="kicker" style={{ marginBottom: 6 }}>Techniques</div>
                  <div className="row" style={{ gap: 4 }}>
                    {opp.required_techniques.map((x) => (
                      <span key={x} className="tag">{x}</span>
                    ))}
                  </div>
                </div>
              )}
              {opp.required_expertise.length > 0 && (
                <div>
                  <div className="kicker" style={{ marginBottom: 6 }}>Expertise</div>
                  <div className="row" style={{ gap: 4 }}>
                    {opp.required_expertise.map((x) => (
                      <span key={x} className="tag">{x}</span>
                    ))}
                  </div>
                </div>
              )}
              {opp.required_equipment.length === 0 &&
                opp.required_techniques.length === 0 &&
                opp.required_expertise.length === 0 && (
                  <p className="muted">No explicit requirements extracted.</p>
                )}
            </div>
          </section>

          <section className="section">
            <div className="section-head">
              <div className="label">Gap analysis</div>
            </div>
            {gapsError ? (
              <div className="error">
                {(gapsError as { detail?: string }).detail ?? 'Failed to load gaps'}
              </div>
            ) : !gaps ? (
              <p className="muted">Loading gaps…</p>
            ) : (
              <div className="stack" style={{ gap: 16 }}>
                <div>
                  <span className="kicker">Estimated effort</span>{' '}
                  <strong style={{ textTransform: 'uppercase', marginLeft: 8 }}>
                    {gaps.estimated_effort}
                  </strong>
                </div>
                <GapList title="Missing equipment" items={gaps.missing_equipment} />
                <GapList title="Equipment to acquire" items={gaps.acquirable_equipment} />
                <GapList title="Skill gaps" items={gaps.skill_gaps} />
                <GapList title="Skills to learn" items={gaps.learnable_skills} />
                <GapList title="Expertise gaps" items={gaps.expertise_gaps} />
                <GapList title="Close via collaboration" items={gaps.closable_via_collaboration} />
              </div>
            )}
          </section>

          <section className="section">
            <div className="section-head">
              <div className="label">Protocol</div>
              {!protocol && (
                <button onClick={generate} disabled={genBusy}>
                  {genBusy ? 'Generating…' : 'Generate protocol'}
                </button>
              )}
            </div>
            {genError && <div className="error">{genError}</div>}
            {protocol && <ProtocolView protocol={protocol} />}
          </section>
        </article>

        <aside>
          <dl className="meta-list">
            {composite != null && (
              <div>
                <dt>Composite</dt>
                <dd>
                  <span className={`big${compositeHigh ? ' high' : ''}`}>
                    {composite.toFixed(2)}
                  </span>
                </dd>
              </div>
            )}
            {ranked && (
              <>
                <div>
                  <dt>Feasibility</dt>
                  <dd>
                    <ScoreBar label="feasibility" value={ranked.score.feasibility} />
                  </dd>
                </div>
                <div>
                  <dt>Alignment</dt>
                  <dd>
                    <ScoreBar label="alignment" value={ranked.score.alignment} />
                  </dd>
                </div>
              </>
            )}
            <div>
              <dt>Complexity</dt>
              <dd>
                <span className={`tag complexity-${opp.estimated_complexity}`}>
                  {opp.estimated_complexity}
                </span>
              </dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>{opp.status}</dd>
            </div>
            {opp.quality_score != null && (
              <div>
                <dt>Quality</dt>
                <dd>
                  <span className="mono">{opp.quality_score.toFixed(2)}</span>
                </dd>
              </div>
            )}
          </dl>
        </aside>
      </div>
    </>
  )
}
