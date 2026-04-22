import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import {
  useApi,
  useApiKeyPrefix,
  type CorrectionField,
  type CorrectionType,
  type FeedbackResponse,
  type StateCorrection,
} from '../lib/api'
import { useLab, useLabState } from '../lib/queries'

interface CorrectionDraft {
  field: CorrectionField
  item_name: string
  type: CorrectionType
}

function CorrectionDialog({
  draft,
  onSubmit,
  onCancel,
  busy,
}: {
  draft: CorrectionDraft
  onSubmit: (reason: string) => void
  onCancel: () => void
  busy: boolean
}) {
  const [reason, setReason] = useState('')
  return (
    <div
      className="card"
      style={{ borderLeft: '2px solid var(--warn)', background: 'var(--surface)' }}
    >
      <h3>
        Correct {draft.field}: {draft.item_name}
      </h3>
      <p className="muted">
        {draft.type === 'remove'
          ? `Tell the compressor we don't have "${draft.item_name}". This becomes a signal on the next distillation pass.`
          : `Update the entry for "${draft.item_name}".`}
      </p>
      <label>Reason (optional)</label>
      <textarea
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        rows={2}
        placeholder="Why is this wrong?"
      />
      <div className="row" style={{ marginTop: 8 }}>
        <button disabled={busy} onClick={() => onSubmit(reason)}>
          {busy ? 'Submitting…' : 'Submit correction'}
        </button>
        <button className="ghost" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
      </div>
    </div>
  )
}

interface ItemRowProps {
  name: string
  meta?: string
  field: CorrectionField
  onCorrect: (draft: CorrectionDraft) => void
}

function ItemRow({ name, meta, field, onCorrect }: ItemRowProps) {
  return (
    <li
      className="row"
      style={{ justifyContent: 'space-between', padding: '4px 0' }}
    >
      <span>
        <strong>{name}</strong>
        {meta && <span className="muted"> — {meta}</span>}
      </span>
      <button
        className="ghost"
        style={{ padding: '2px 8px', fontSize: 12 }}
        onClick={() => onCorrect({ field, item_name: name, type: 'remove' })}
      >
        We don&apos;t have this
      </button>
    </li>
  )
}

function Section({
  title,
  children,
  empty,
}: {
  title: string
  children: React.ReactNode
  empty: boolean
}) {
  return (
    <div className="card">
      <h3>{title}</h3>
      {empty ? <p className="muted">No entries yet.</p> : <ul style={{ paddingLeft: 0, listStyle: 'none' }}>{children}</ul>}
    </div>
  )
}

export default function LabStatePage() {
  const api = useApi()
  const qc = useQueryClient()
  const keyPrefix = useApiKeyPrefix()
  const { data: lab } = useLab()
  const { data: state, isLoading } = useLabState(lab?.id)
  const [draft, setDraft] = useState<CorrectionDraft | null>(null)
  const [adding, setAdding] = useState<CorrectionField | null>(null)
  const [addName, setAddName] = useState('')

  const correct = useMutation({
    mutationFn: (correction: StateCorrection) =>
      api<FeedbackResponse>(`/api/v1/labs/${lab!.id}/feedback/state`, {
        method: 'POST',
        body: correction,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [keyPrefix, 'lab-state', lab?.id] })
      setDraft(null)
      setAdding(null)
      setAddName('')
    },
  })

  if (!lab) return null

  if (isLoading) return <p className="muted">Loading state…</p>

  if (!state) {
    return (
      <>
        <header>
          <div>
            <div className="kicker">Compressed capability</div>
            <h1>Lab state</h1>
          </div>
        </header>
        <p className="muted">No state yet — log experiments or upload documents to seed the compressor.</p>
      </>
    )
  }

  const { state: s } = state

  const submitRemove = (reason: string) => {
    if (!draft) return
    correct.mutate({
      correction_type: draft.type,
      field: draft.field,
      item_name: draft.item_name,
      reason: reason || null,
    })
  }

  const submitAdd = () => {
    if (!adding || !addName.trim()) return
    correct.mutate({
      correction_type: 'add',
      field: adding,
      item_name: addName.trim(),
    })
  }

  return (
    <>
      <header>
        <div>
          <div className="kicker">
            v{state.version} · {state.token_count ?? '—'} tokens · {s.signal_count} signals
          </div>
          <h1>Lab state</h1>
        </div>
      </header>

      <p className="muted" style={{ marginBottom: 24, maxWidth: '62ch' }}>
        Inline corrections become signals — they merge into the next distillation
        pass rather than overwriting state directly.
      </p>

      {draft && (
        <CorrectionDialog
          draft={draft}
          busy={correct.isPending}
          onCancel={() => setDraft(null)}
          onSubmit={submitRemove}
        />
      )}

      {(['equipment', 'techniques', 'expertise', 'organisms', 'reagents'] as CorrectionField[]).map(
        (field) => (
          <div key={field}>
            {(() => {
              if (field === 'equipment') {
                return (
                  <Section title="Equipment" empty={s.equipment.length === 0}>
                    {s.equipment.map((e) => (
                      <ItemRow
                        key={e.name}
                        name={e.name}
                        meta={e.capabilities.join(', ') || undefined}
                        field="equipment"
                        onCorrect={setDraft}
                      />
                    ))}
                  </Section>
                )
              }
              if (field === 'techniques') {
                return (
                  <Section title="Techniques" empty={s.techniques.length === 0}>
                    {s.techniques.map((t) => (
                      <ItemRow
                        key={t.name}
                        name={t.name}
                        meta={t.proficiency}
                        field="techniques"
                        onCorrect={setDraft}
                      />
                    ))}
                  </Section>
                )
              }
              if (field === 'expertise') {
                return (
                  <Section title="Expertise" empty={s.expertise.length === 0}>
                    {s.expertise.map((e) => (
                      <ItemRow
                        key={e.domain}
                        name={e.domain}
                        meta={`confidence: ${e.confidence}`}
                        field="expertise"
                        onCorrect={setDraft}
                      />
                    ))}
                  </Section>
                )
              }
              if (field === 'organisms') {
                return (
                  <Section title="Organisms" empty={s.organisms.length === 0}>
                    {s.organisms.map((o) => (
                      <ItemRow
                        key={o.name}
                        name={o.name}
                        meta={o.strains.join(', ') || undefined}
                        field="organisms"
                        onCorrect={setDraft}
                      />
                    ))}
                  </Section>
                )
              }
              return (
                <Section title="Reagents" empty={s.reagents.length === 0}>
                  {s.reagents.map((r) => (
                    <ItemRow
                      key={r.name}
                      name={r.name}
                      meta={r.quantity ?? undefined}
                      field="reagents"
                      onCorrect={setDraft}
                    />
                  ))}
                </Section>
              )
            })()}
            <div className="row" style={{ marginTop: -12, marginBottom: 16 }}>
              {adding === field ? (
                <>
                  <input
                    autoFocus
                    value={addName}
                    onChange={(e) => setAddName(e.target.value)}
                    placeholder={`Add ${field}…`}
                    onKeyDown={(e) => e.key === 'Enter' && submitAdd()}
                  />
                  <button onClick={submitAdd} disabled={correct.isPending || !addName.trim()}>
                    Add
                  </button>
                  <button className="ghost" onClick={() => setAdding(null)} disabled={correct.isPending}>
                    Cancel
                  </button>
                </>
              ) : (
                <button className="ghost" onClick={() => setAdding(field)}>
                  + We have {field === 'expertise' ? 'expertise in' : 'a'} {field.replace(/s$/, '')}
                </button>
              )}
            </div>
          </div>
        ),
      )}

      <div className="card">
        <h3>Recent experimental history</h3>
        {s.experimental_history.length === 0 ? (
          <p className="muted">No history compressed yet.</p>
        ) : (
          <ul>
            {s.experimental_history.map((h, i) => (
              <li key={i}>
                <strong>{h.technique}</strong> — <span style={{ color:
                  h.outcome === 'success' ? 'var(--ok)' :
                  h.outcome === 'partial' ? 'var(--warn)' : 'var(--danger)' }}>{h.outcome}</span>: {h.insight}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="card">
        <h3>Resource constraints</h3>
        {!s.resource_constraints.budget_notes &&
        !s.resource_constraints.time_constraints &&
        !s.resource_constraints.personnel_notes ? (
          <p className="muted">None recorded.</p>
        ) : (
          <ul>
            {s.resource_constraints.budget_notes && (
              <li><strong>Budget:</strong> {s.resource_constraints.budget_notes}</li>
            )}
            {s.resource_constraints.time_constraints && (
              <li><strong>Time:</strong> {s.resource_constraints.time_constraints}</li>
            )}
            {s.resource_constraints.personnel_notes && (
              <li><strong>Personnel:</strong> {s.resource_constraints.personnel_notes}</li>
            )}
          </ul>
        )}
      </div>

      {correct.error && (
        <div className="error">
          {(correct.error as { detail?: string }).detail ?? 'Correction failed'}
        </div>
      )}
    </>
  )
}
