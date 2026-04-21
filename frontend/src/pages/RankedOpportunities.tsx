import { useEffect, useState } from 'react'
import {
  type GapAnalysis,
  type Lab,
  type Protocol,
  type RankedOpportunity,
  type RankedOpportunityList,
  useApi,
} from '../lib/api'

function ScoreBar({ value, label }: { value: number; label: string }) {
  const pct = Math.max(0, Math.min(1, value)) * 100
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ width: 84, fontSize: 12, color: '#555' }}>{label}</span>
      <div
        style={{
          flex: 1,
          height: 8,
          background: '#eee',
          borderRadius: 4,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            background: pct > 66 ? '#22c55e' : pct > 33 ? '#eab308' : '#ef4444',
          }}
        />
      </div>
      <span style={{ width: 48, textAlign: 'right', fontSize: 12 }}>
        {value.toFixed(2)}
      </span>
    </div>
  )
}

function GapPanel({
  lab,
  ranked,
}: {
  lab: Lab
  ranked: RankedOpportunity
}) {
  const apiFetch = useApi()
  const [gaps, setGaps] = useState<GapAnalysis | null>(null)
  const [protocol, setProtocol] = useState<Protocol | null>(null)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setGaps(null)
    setProtocol(null)
    setError(null)
    apiFetch<GapAnalysis>(
      `/api/v1/labs/${lab.id}/opportunities/${ranked.opportunity.id}/gaps`,
    )
      .then(setGaps)
      .catch((e) => setError(e.detail ?? 'Failed to load gaps'))
  }, [apiFetch, lab.id, ranked.opportunity.id])

  const handleGenerate = async () => {
    setGenerating(true)
    setError(null)
    try {
      const p = await apiFetch<Protocol>(
        `/api/v1/labs/${lab.id}/opportunities/${ranked.opportunity.id}/protocol`,
        { method: 'POST', body: '{}' },
      )
      setProtocol(p)
    } catch (e) {
      const err = e as { detail?: string }
      setError(err.detail ?? 'Protocol generation failed')
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3>{ranked.opportunity.description}</h3>
      <div style={{ display: 'grid', gap: 6, marginBottom: 12 }}>
        <ScoreBar value={ranked.score.composite} label="Composite" />
        <ScoreBar value={ranked.score.feasibility} label="Feasibility" />
        <ScoreBar value={ranked.score.alignment} label="Alignment" />
      </div>

      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}

      {gaps && (
        <div style={{ display: 'grid', gap: 8 }}>
          <h4 style={{ margin: '8px 0' }}>
            Gap analysis — effort:{' '}
            <span style={{ textTransform: 'uppercase' }}>
              {gaps.estimated_effort}
            </span>
          </h4>
          <GapList title="Missing equipment" items={gaps.missing_equipment} />
          <GapList
            title="Equipment to acquire"
            items={gaps.acquirable_equipment}
          />
          <GapList title="Skill gaps" items={gaps.skill_gaps} />
          <GapList title="Skills to learn" items={gaps.learnable_skills} />
          <GapList title="Expertise gaps" items={gaps.expertise_gaps} />
          <GapList
            title="Close via collaboration"
            items={gaps.closable_via_collaboration}
          />
        </div>
      )}

      <div style={{ marginTop: 12 }}>
        <button onClick={handleGenerate} disabled={generating}>
          {generating ? 'Generating protocol…' : 'Generate protocol'}
        </button>
      </div>

      {protocol && (
        <div style={{ marginTop: 16 }}>
          <h3>{protocol.title}</h3>
          {protocol.content.flagged_gaps.length > 0 && (
            <div
              style={{
                border: '1px solid #fbbf24',
                background: '#fef3c7',
                padding: 8,
                borderRadius: 4,
                marginBottom: 12,
              }}
            >
              <strong>Flagged gaps:</strong> {protocol.content.flagged_gaps.join(', ')}
            </div>
          )}
          {protocol.content.phases.map((phase, i) => (
            <div key={i} style={{ marginBottom: 12 }}>
              <h4 style={{ margin: '8px 0 4px' }}>
                Phase {i + 1}: {phase.name}
                {phase.duration_estimate ? ` — ${phase.duration_estimate}` : ''}
              </h4>
              <ol>
                {phase.steps.map((step, j) => (
                  <li key={j}>{step}</li>
                ))}
              </ol>
              {phase.materials_used.length > 0 && (
                <p style={{ fontSize: 12, color: '#555' }}>
                  Materials: {phase.materials_used.join(', ')}
                </p>
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
            <p style={{ fontSize: 12, color: '#555' }}>
              Citations: {protocol.content.citations.join(', ')}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

function GapList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null
  return (
    <div>
      <strong>{title}:</strong> {items.join(', ')}
    </div>
  )
}

export default function RankedOpportunities() {
  const apiFetch = useApi()
  const [lab, setLab] = useState<Lab | null>(null)
  const [ranked, setRanked] = useState<RankedOpportunityList | null>(null)
  const [selected, setSelected] = useState<RankedOpportunity | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<Lab>(`/api/v1/labs`)
      .then(setLab)
      .catch((e) => setError(e.detail ?? 'Failed to load lab'))
  }, [apiFetch])

  useEffect(() => {
    if (!lab) return
    apiFetch<RankedOpportunityList>(
      `/api/v1/labs/${lab.id}/opportunities/ranked?limit=25`,
    )
      .then(setRanked)
      .catch((e) => setError(e.detail ?? 'Failed to load ranked opportunities'))
  }, [apiFetch, lab])

  if (error) {
    return (
      <div className="card">
        <p style={{ color: '#b91c1c' }}>{error}</p>
      </div>
    )
  }

  if (!lab || !ranked) {
    return (
      <div className="card">
        <p>Loading…</p>
      </div>
    )
  }

  return (
    <>
      <div className="card">
        <h2>Ranked opportunities — {lab.name}</h2>
        {ranked.items.length === 0 ? (
          <p>No ranked opportunities yet. Run a literature scan first.</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ textAlign: 'left', borderBottom: '1px solid #ddd' }}>
                <th style={{ padding: 6 }}>#</th>
                <th style={{ padding: 6 }}>Opportunity</th>
                <th style={{ padding: 6 }}>Complexity</th>
                <th style={{ padding: 6, width: 180 }}>Score</th>
              </tr>
            </thead>
            <tbody>
              {ranked.items.map((item, i) => (
                <tr
                  key={item.opportunity.id}
                  onClick={() => setSelected(item)}
                  style={{
                    cursor: 'pointer',
                    borderBottom: '1px solid #f0f0f0',
                    background:
                      selected?.opportunity.id === item.opportunity.id
                        ? '#eef2ff'
                        : undefined,
                  }}
                >
                  <td style={{ padding: 6 }}>{i + 1}</td>
                  <td style={{ padding: 6 }}>
                    {item.opportunity.description.slice(0, 140)}
                    {item.opportunity.description.length > 140 ? '…' : ''}
                  </td>
                  <td style={{ padding: 6 }}>
                    {item.opportunity.estimated_complexity}
                  </td>
                  <td style={{ padding: 6 }}>
                    <ScoreBar
                      value={item.score.composite}
                      label={`#${i + 1}`}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {selected && <GapPanel lab={lab} ranked={selected} />}
    </>
  )
}
