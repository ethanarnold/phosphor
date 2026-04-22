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
      <strong>{title}:</strong>{' '}
      {items.map((i) => (
        <span key={i} className="tag">{i}</span>
      ))}
    </div>
  )
}

function ProtocolView({ protocol }: { protocol: Protocol }) {
  return (
    <div>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h3>{protocol.title}</h3>
        <button onClick={() => downloadMarkdown(protocol)} className="ghost">
          Export Markdown
        </button>
      </div>
      <div className="muted" style={{ marginBottom: 8 }}>
        Lab state v{protocol.lab_state_version} · {protocol.llm_model} · prompt {protocol.prompt_version}
      </div>

      {protocol.content.flagged_gaps.length > 0 && (
        <div className="warning" style={{ marginBottom: 12 }}>
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
        <div key={i} style={{ marginBottom: 12 }}>
          <h4>
            Phase {i + 1}: {phase.name}
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
      <ul>
        {protocol.content.expected_outcomes.map((o, i) => (
          <li key={i}>{o}</li>
        ))}
      </ul>

      {protocol.content.citations.length > 0 && (
        <>
          <h4>Citations</h4>
          <ul>
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
    return <div className="card">Loading…</div>
  }

  return (
    <>
      <header>
        <div>
          <Link to="/opportunities" className="muted">← All opportunities</Link>
          <h1 style={{ marginTop: 4 }}>Opportunity</h1>
        </div>
      </header>

      <div className="card">
        <p style={{ fontSize: 15 }}>{opp.description}</p>
        <div className="row" style={{ marginTop: 8 }}>
          <span className={`tag complexity-${opp.estimated_complexity}`}>
            {opp.estimated_complexity}
          </span>
          <span className="tag">status: {opp.status}</span>
          {opp.quality_score != null && (
            <span className="tag">quality {opp.quality_score.toFixed(2)}</span>
          )}
        </div>

        {ranked && (
          <div className="stack" style={{ marginTop: 12 }}>
            <ScoreBar value={ranked.score.composite} label="Composite" />
            <ScoreBar value={ranked.score.feasibility} label="Feasibility" />
            <ScoreBar value={ranked.score.alignment} label="Alignment" />
          </div>
        )}

        <div className="row" style={{ marginTop: 12 }}>
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
      </div>

      <div className="card">
        <h2>Requirements</h2>
        {opp.required_equipment.length > 0 && (
          <p>
            <strong>Equipment:</strong>{' '}
            {opp.required_equipment.map((x) => (
              <span key={x} className="tag">{x}</span>
            ))}
          </p>
        )}
        {opp.required_techniques.length > 0 && (
          <p>
            <strong>Techniques:</strong>{' '}
            {opp.required_techniques.map((x) => (
              <span key={x} className="tag">{x}</span>
            ))}
          </p>
        )}
        {opp.required_expertise.length > 0 && (
          <p>
            <strong>Expertise:</strong>{' '}
            {opp.required_expertise.map((x) => (
              <span key={x} className="tag">{x}</span>
            ))}
          </p>
        )}
      </div>

      <div className="card">
        <h2>Gap analysis</h2>
        {gapsError ? (
          <div className="error">
            {(gapsError as { detail?: string }).detail ?? 'Failed to load gaps'}
          </div>
        ) : !gaps ? (
          <p className="muted">Loading gaps…</p>
        ) : (
          <div className="stack">
            <div>
              Estimated effort:{' '}
              <strong style={{ textTransform: 'uppercase' }}>{gaps.estimated_effort}</strong>
            </div>
            <GapList title="Missing equipment" items={gaps.missing_equipment} />
            <GapList title="Equipment to acquire" items={gaps.acquirable_equipment} />
            <GapList title="Skill gaps" items={gaps.skill_gaps} />
            <GapList title="Skills to learn" items={gaps.learnable_skills} />
            <GapList title="Expertise gaps" items={gaps.expertise_gaps} />
            <GapList title="Close via collaboration" items={gaps.closable_via_collaboration} />
          </div>
        )}
      </div>

      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <h2>Protocol</h2>
          {!protocol && (
            <button onClick={generate} disabled={genBusy}>
              {genBusy ? 'Generating…' : 'Generate protocol'}
            </button>
          )}
        </div>
        {genError && <div className="error">{genError}</div>}
        {protocol && <ProtocolView protocol={protocol} />}
      </div>
    </>
  )
}
