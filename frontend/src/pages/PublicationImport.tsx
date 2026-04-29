import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  useApi,
  useApiKeyPrefix,
  type AcceptedLabState,
  type ApiError,
  type CapabilitySource,
  type Equipment,
  type Expertise,
  type ImportStatus,
  type LabStateImport,
  type Organism,
  type ProposedLabState,
  type Reagent,
  type Technique,
} from '../lib/api'
import { useLab, useLabState } from '../lib/queries'

const POLL_INTERVAL_MS = 1500
const ORCID_REGEX = /^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$/

type Phase =
  | { kind: 'input' }
  | { kind: 'progress'; importId: string; startedAt: number; detail: LabStateImport | null }
  | { kind: 'review'; detail: LabStateImport }
  | { kind: 'failed'; message: string }

interface SelectionState {
  equipment: Set<string>
  techniques: Set<string>
  expertise: Set<string>
  organisms: Set<string>
  reagents: Set<string>
}

function emptySelection(): SelectionState {
  return {
    equipment: new Set(),
    techniques: new Set(),
    expertise: new Set(),
    organisms: new Set(),
    reagents: new Set(),
  }
}

function ElapsedClock({ startedAt }: { startedAt: number }) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(t)
  }, [])
  return <span className="mono">{Math.round((now - startedAt) / 1000)}s</span>
}

function ProgressLine({ detail, startedAt }: { detail: LabStateImport | null; startedAt: number }) {
  const step = detail?.progress?.current_step ?? 'Starting…'
  const total = detail?.progress?.papers_total
  const done = detail?.progress?.papers_processed
  return (
    <div aria-live="polite">
      <span>{step}</span>
      {total != null && done != null && (
        <span className="muted" style={{ marginLeft: 12 }}>
          {done} of {total} papers
        </span>
      )}
      <span className="muted" style={{ marginLeft: 12 }}>
        <ElapsedClock startedAt={startedAt} />
      </span>
    </div>
  )
}

interface ReviewItemRowProps {
  id: string
  label: string
  meta?: string
  frequency: number
  sources: CapabilitySource[]
  alreadyPresent: boolean
  selected: boolean
  onToggle: () => void
}

function ReviewItemRow({
  id,
  label,
  meta,
  frequency,
  sources,
  alreadyPresent,
  selected,
  onToggle,
}: ReviewItemRowProps) {
  const checkboxId = `import-${id}`
  return (
    <li style={{ padding: '6px 0', borderBottom: '1px solid var(--rule)' }}>
      <div className="row" style={{ justifyContent: 'space-between', gap: 12 }}>
        <label
          htmlFor={checkboxId}
          className="row"
          style={{ gap: 10, cursor: alreadyPresent ? 'default' : 'pointer' }}
        >
          <input
            id={checkboxId}
            type="checkbox"
            checked={selected}
            disabled={alreadyPresent}
            onChange={onToggle}
          />
          <span>
            <strong>{label}</strong>
            {meta && <span className="muted"> — {meta}</span>}
          </span>
        </label>
        <span style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}>
          {alreadyPresent && <span className="tag">already in lab state</span>}
          <span className="mono muted" style={{ fontSize: 12 }}>
            {frequency} paper{frequency === 1 ? '' : 's'}
          </span>
        </span>
      </div>
      {sources.length > 0 && (
        <details style={{ marginTop: 4, marginLeft: 28 }}>
          <summary className="muted" style={{ fontSize: 12, cursor: 'pointer' }}>
            Source{sources.length === 1 ? '' : 's'}
          </summary>
          <ul style={{ margin: '6px 0 0 0', paddingLeft: 18, fontSize: 12, color: 'var(--ink-3)' }}>
            {sources.slice(0, 8).map((s) => (
              <li key={(s.pmid ?? s.doi ?? s.title) + ''}>
                {s.title}
                {s.year && <span className="muted"> · {s.year}</span>}
              </li>
            ))}
            {sources.length > 8 && (
              <li className="muted">+ {sources.length - 8} more</li>
            )}
          </ul>
        </details>
      )}
    </li>
  )
}

interface ReviewSectionProps<TItem extends { name?: string; domain?: string }> {
  title: string
  items: (TItem & { sources: CapabilitySource[]; frequency: number })[]
  keyOf: (item: TItem) => string
  metaOf?: (item: TItem) => string | undefined
  isPresent: (key: string) => boolean
  selected: Set<string>
  onToggle: (key: string) => void
}

function ReviewSection<TItem extends { name?: string; domain?: string }>({
  title,
  items,
  keyOf,
  metaOf,
  isPresent,
  selected,
  onToggle,
}: ReviewSectionProps<TItem>) {
  if (items.length === 0) {
    return (
      <div className="card">
        <h3>{title}</h3>
        <p className="muted">No items found in this category.</p>
      </div>
    )
  }
  return (
    <div className="card">
      <h3>{title}</h3>
      <ul style={{ paddingLeft: 0, listStyle: 'none', margin: 0 }}>
        {items.map((item) => {
          const key = keyOf(item)
          const present = isPresent(key)
          return (
            <ReviewItemRow
              key={key}
              id={`${title}-${key}`}
              label={item.name ?? item.domain ?? key}
              meta={metaOf?.(item)}
              frequency={item.frequency}
              sources={item.sources}
              alreadyPresent={present}
              selected={selected.has(key) && !present}
              onToggle={() => onToggle(key)}
            />
          )
        })}
      </ul>
    </div>
  )
}

function buildAccepted(
  proposed: ProposedLabState,
  selection: SelectionState,
  alreadyPresent: {
    equipment: Set<string>
    techniques: Set<string>
    expertise: Set<string>
    organisms: Set<string>
    reagents: Set<string>
  },
): AcceptedLabState {
  const pickEquip = (k: string): Equipment | null => {
    if (alreadyPresent.equipment.has(k) || !selection.equipment.has(k)) return null
    const item = proposed.equipment.find((e) => norm(e.name) === k)
    if (!item) return null
    return { name: item.name, capabilities: item.capabilities, limitations: item.limitations }
  }
  const pickTech = (k: string): Technique | null => {
    if (alreadyPresent.techniques.has(k) || !selection.techniques.has(k)) return null
    const item = proposed.techniques.find((t) => norm(t.name) === k)
    if (!item) return null
    return { name: item.name, proficiency: item.proficiency, notes: item.notes }
  }
  const pickExp = (k: string): Expertise | null => {
    if (alreadyPresent.expertise.has(k) || !selection.expertise.has(k)) return null
    const item = proposed.expertise.find((e) => norm(e.domain) === k)
    if (!item) return null
    return { domain: item.domain, confidence: item.confidence }
  }
  const pickOrg = (k: string): Organism | null => {
    if (alreadyPresent.organisms.has(k) || !selection.organisms.has(k)) return null
    const item = proposed.organisms.find((o) => norm(o.name) === k)
    if (!item) return null
    return { name: item.name, strains: item.strains, notes: item.notes }
  }
  const pickReag = (k: string): Reagent | null => {
    if (alreadyPresent.reagents.has(k) || !selection.reagents.has(k)) return null
    const item = proposed.reagents.find((r) => norm(r.name) === k)
    if (!item) return null
    return { name: item.name, quantity: item.quantity, notes: item.notes }
  }

  const equipment = [...selection.equipment].map(pickEquip).filter((x): x is Equipment => x != null)
  const techniques = [...selection.techniques].map(pickTech).filter((x): x is Technique => x != null)
  const expertise = [...selection.expertise].map(pickExp).filter((x): x is Expertise => x != null)
  const organisms = [...selection.organisms].map(pickOrg).filter((x): x is Organism => x != null)
  const reagents = [...selection.reagents].map(pickReag).filter((x): x is Reagent => x != null)

  return { equipment, techniques, expertise, organisms, reagents }
}

function norm(s: string | undefined): string {
  return (s ?? '').trim().toLowerCase().replace(/\s+/g, ' ')
}

function selectionCount(s: SelectionState, alreadyPresent: ReturnType<typeof buildAlreadyPresent>): number {
  const minus = (set: Set<string>, present: Set<string>) => {
    let n = 0
    set.forEach((k) => {
      if (!present.has(k)) n++
    })
    return n
  }
  return (
    minus(s.equipment, alreadyPresent.equipment) +
    minus(s.techniques, alreadyPresent.techniques) +
    minus(s.expertise, alreadyPresent.expertise) +
    minus(s.organisms, alreadyPresent.organisms) +
    minus(s.reagents, alreadyPresent.reagents)
  )
}

function buildAlreadyPresent(state: ReturnType<typeof useLabState>['data']) {
  if (!state) {
    return {
      equipment: new Set<string>(),
      techniques: new Set<string>(),
      expertise: new Set<string>(),
      organisms: new Set<string>(),
      reagents: new Set<string>(),
    }
  }
  const s = state.state
  return {
    equipment: new Set(s.equipment.map((e) => norm(e.name))),
    techniques: new Set(s.techniques.map((t) => norm(t.name))),
    expertise: new Set(s.expertise.map((e) => norm(e.domain))),
    organisms: new Set(s.organisms.map((o) => norm(o.name))),
    reagents: new Set(s.reagents.map((r) => norm(r.name))),
  }
}

function defaultSelectionFor(
  proposed: ProposedLabState,
  alreadyPresent: ReturnType<typeof buildAlreadyPresent>,
): SelectionState {
  // Default-on for every novel item; default-off for items already in state.
  const fill = (
    items: { name?: string; domain?: string }[],
    present: Set<string>,
  ): Set<string> => {
    const out = new Set<string>()
    for (const it of items) {
      const key = norm(it.name ?? it.domain)
      if (!key || present.has(key)) continue
      out.add(key)
    }
    return out
  }
  return {
    equipment: fill(proposed.equipment, alreadyPresent.equipment),
    techniques: fill(proposed.techniques, alreadyPresent.techniques),
    expertise: fill(proposed.expertise, alreadyPresent.expertise),
    organisms: fill(proposed.organisms, alreadyPresent.organisms),
    reagents: fill(proposed.reagents, alreadyPresent.reagents),
  }
}

export default function PublicationImport() {
  const api = useApi()
  const qc = useQueryClient()
  const keyPrefix = useApiKeyPrefix()
  const navigate = useNavigate()
  const { data: lab } = useLab()
  const { data: currentState } = useLabState(lab?.id)

  const [orcidId, setOrcidId] = useState('')
  const [phase, setPhase] = useState<Phase>({ kind: 'input' })
  const [submitting, setSubmitting] = useState(false)
  const [committing, setCommitting] = useState(false)
  const [selection, setSelection] = useState<SelectionState>(emptySelection)
  const [commitError, setCommitError] = useState<string | null>(null)
  const pollTimer = useRef<number | null>(null)

  const stopPolling = useCallback(() => {
    if (pollTimer.current !== null) {
      window.clearTimeout(pollTimer.current)
      pollTimer.current = null
    }
  }, [])

  useEffect(() => {
    return () => stopPolling()
  }, [stopPolling])

  const alreadyPresent = buildAlreadyPresent(currentState)

  const poll = useCallback(
    async (labId: string, importId: string, startedAt: number) => {
      try {
        const detail = await api<LabStateImport>(
          `/api/v1/labs/${labId}/imports/${importId}`,
        )
        if (detail.status === 'review') {
          if (detail.proposed_state) {
            setSelection(defaultSelectionFor(detail.proposed_state, alreadyPresent))
          }
          setPhase({ kind: 'review', detail })
          return
        }
        if (detail.status === 'failed' || detail.status === 'cancelled') {
          setPhase({
            kind: 'failed',
            message: detail.error ?? 'Import failed.',
          })
          return
        }
        setPhase({ kind: 'progress', importId, startedAt, detail })
        pollTimer.current = window.setTimeout(
          () => poll(labId, importId, startedAt),
          POLL_INTERVAL_MS,
        )
      } catch (err) {
        const e = err as ApiError
        setPhase({ kind: 'failed', message: e.detail ?? `Poll failed (HTTP ${e.status ?? '?'}).` })
      }
    },
    // alreadyPresent is derived from currentState; React Query keeps the
    // reference stable within a render so re-poll refs are fine.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [api, currentState],
  )

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!lab) return
    const trimmed = orcidId.trim()
    if (!ORCID_REGEX.test(trimmed)) return
    stopPolling()
    setSubmitting(true)
    setCommitError(null)
    try {
      const created = await api<LabStateImport>(
        `/api/v1/labs/${lab.id}/imports/orcid`,
        { method: 'POST', body: { orcid_id: trimmed } },
      )
      const startedAt = Date.now()
      setPhase({ kind: 'progress', importId: created.id, startedAt, detail: created })
      pollTimer.current = window.setTimeout(
        () => poll(lab.id, created.id, startedAt),
        POLL_INTERVAL_MS,
      )
    } catch (err) {
      const e = err as ApiError
      setPhase({ kind: 'failed', message: e.detail ?? `Could not start import (HTTP ${e.status ?? '?'}).` })
    } finally {
      setSubmitting(false)
    }
  }

  const cancel = async () => {
    if (phase.kind !== 'progress' || !lab) return
    stopPolling()
    try {
      await api<LabStateImport>(
        `/api/v1/labs/${lab.id}/imports/${phase.importId}`,
        { method: 'DELETE' },
      )
    } catch {
      /* best-effort */
    }
    setPhase({ kind: 'input' })
  }

  const restart = () => {
    stopPolling()
    setPhase({ kind: 'input' })
    setOrcidId('')
    setCommitError(null)
  }

  const toggle = (cat: keyof SelectionState, key: string) => {
    setSelection((prev) => {
      const next = { ...prev, [cat]: new Set(prev[cat]) }
      const set = next[cat] as Set<string>
      if (set.has(key)) set.delete(key)
      else set.add(key)
      return next
    })
  }

  const commit = async () => {
    if (phase.kind !== 'review' || !lab || !phase.detail.proposed_state) return
    setCommitting(true)
    setCommitError(null)
    try {
      const accepted = buildAccepted(phase.detail.proposed_state, selection, alreadyPresent)
      await api<LabStateImport>(
        `/api/v1/labs/${lab.id}/imports/${phase.detail.id}/commit`,
        { method: 'POST', body: { accepted } },
      )
      qc.invalidateQueries({ queryKey: [keyPrefix, 'lab-state', lab.id] })
      setPhase({ kind: 'input' })
      setOrcidId('')
      navigate('/state')
    } catch (err) {
      const e = err as ApiError
      setCommitError(e.detail ?? `Commit failed (HTTP ${e.status ?? '?'}).`)
    } finally {
      setCommitting(false)
    }
  }

  if (!lab) return null

  const trimmed = orcidId.trim()
  const orcidValid = ORCID_REGEX.test(trimmed)
  const orcidShowError = trimmed.length > 0 && !orcidValid

  return (
    <>
      <header>
        <div>
          <div className="kicker">Import</div>
          <h1>Lab state from publications</h1>
        </div>
      </header>

      <p className="muted" style={{ marginTop: 0, maxWidth: '62ch' }}>
        Paste your ORCID iD and we&apos;ll read your most recent 50 publications,
        extract the techniques, organisms, equipment, reagents, and expertise
        they demonstrate, and let you review before committing to lab state.
      </p>

      {phase.kind === 'input' && (
        <form className="stack" onSubmit={submit} style={{ gap: 16, maxWidth: 560 }}>
          <div>
            <label htmlFor="orcid-id">ORCID iD</label>
            <input
              id="orcid-id"
              value={orcidId}
              onChange={(e) => setOrcidId(e.target.value)}
              placeholder="0000-0002-1825-0097"
              autoComplete="off"
              spellCheck={false}
              pattern="\d{4}-\d{4}-\d{4}-\d{3}[\dX]"
              maxLength={19}
              disabled={submitting}
              style={{ fontFamily: 'var(--font-mono)' }}
            />
            <div className="muted" style={{ marginTop: 6 }}>
              {orcidShowError ? (
                <span style={{ color: 'var(--danger)' }}>
                  Format: NNNN-NNNN-NNNN-NNNN (16 digits + dashes).
                </span>
              ) : (
                <>
                  Don&apos;t have one?{' '}
                  <a
                    href="https://orcid.org/register"
                    target="_blank"
                    rel="noreferrer noopener"
                  >
                    Register at orcid.org
                  </a>
                  .
                </>
              )}
            </div>
          </div>
          <div className="row">
            <button type="submit" disabled={submitting || !orcidValid}>
              {submitting ? 'Starting…' : 'Import publications'}
            </button>
          </div>
        </form>
      )}

      {phase.kind === 'progress' && (
        <div className="card" style={{ maxWidth: 720 }}>
          <div className="kicker" style={{ margin: 0 }}>Running</div>
          <ProgressLine detail={phase.detail} startedAt={phase.startedAt} />
          <div className="row" style={{ marginTop: 16 }}>
            <button type="button" className="ghost" onClick={cancel}>
              Cancel import
            </button>
          </div>
        </div>
      )}

      {phase.kind === 'review' && phase.detail.proposed_state && (
        <>
          <div className="muted" style={{ margin: '8px 0 16px' }}>
            <span className="mono">{phase.detail.orcid_id}</span> ·{' '}
            {phase.detail.progress.papers_total ?? 0} papers analyzed
          </div>

          <ReviewSection<ProposedLabState['techniques'][number]>
            title="Techniques"
            items={phase.detail.proposed_state.techniques}
            keyOf={(t) => norm(t.name)}
            metaOf={(t) => t.proficiency}
            isPresent={(k) => alreadyPresent.techniques.has(k)}
            selected={selection.techniques}
            onToggle={(k) => toggle('techniques', k)}
          />
          <ReviewSection<ProposedLabState['organisms'][number]>
            title="Organisms"
            items={phase.detail.proposed_state.organisms}
            keyOf={(o) => norm(o.name)}
            isPresent={(k) => alreadyPresent.organisms.has(k)}
            selected={selection.organisms}
            onToggle={(k) => toggle('organisms', k)}
          />
          <ReviewSection<ProposedLabState['equipment'][number]>
            title="Equipment"
            items={phase.detail.proposed_state.equipment}
            keyOf={(e) => norm(e.name)}
            isPresent={(k) => alreadyPresent.equipment.has(k)}
            selected={selection.equipment}
            onToggle={(k) => toggle('equipment', k)}
          />
          <ReviewSection<ProposedLabState['reagents'][number]>
            title="Reagents"
            items={phase.detail.proposed_state.reagents}
            keyOf={(r) => norm(r.name)}
            isPresent={(k) => alreadyPresent.reagents.has(k)}
            selected={selection.reagents}
            onToggle={(k) => toggle('reagents', k)}
          />
          <ReviewSection<ProposedLabState['expertise'][number]>
            title="Expertise"
            items={phase.detail.proposed_state.expertise}
            keyOf={(e) => norm(e.domain)}
            metaOf={(e) => `confidence: ${e.confidence}`}
            isPresent={(k) => alreadyPresent.expertise.has(k)}
            selected={selection.expertise}
            onToggle={(k) => toggle('expertise', k)}
          />

          {commitError && <div className="error">{commitError}</div>}

          <div
            className="row"
            style={{
              position: 'sticky',
              bottom: 0,
              padding: '12px 0',
              background: 'var(--paper)',
              borderTop: '1px solid var(--rule)',
              justifyContent: 'space-between',
            }}
          >
            <button type="button" className="ghost" onClick={restart} disabled={committing}>
              Start over
            </button>
            <button
              type="button"
              onClick={commit}
              disabled={committing || selectionCount(selection, alreadyPresent) === 0}
            >
              {committing
                ? 'Committing…'
                : `Commit ${selectionCount(selection, alreadyPresent)} selected`}
            </button>
          </div>
        </>
      )}

      {phase.kind === 'failed' && (
        <div className="card" style={{ maxWidth: 720 }}>
          <div className="error">{phase.message}</div>
          <div className="row" style={{ marginTop: 16 }}>
            <button type="button" onClick={restart}>
              Try again
            </button>
          </div>
        </div>
      )}
    </>
  )
}

// Re-export the status type for any consumer that wants to narrow.
export type { ImportStatus }
