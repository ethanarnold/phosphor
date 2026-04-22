import { useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import {
  useApi,
  useApiKeyPrefix,
  type BulkExperimentResponse,
  type ExperimentCreateResponse,
  type ExperimentEntry,
  type Outcome,
} from '../lib/api'
import { useLab } from '../lib/queries'

type Mode = 'quick' | 'structured' | 'bulk'

const OUTCOME_TONE: Record<Outcome, 'ok' | 'warn' | 'danger'> = {
  success: 'ok',
  partial: 'warn',
  failed: 'danger',
}

const OUTCOME_LABEL: Record<Outcome, string> = {
  success: 'Worked',
  partial: 'Partial',
  failed: 'Failed',
}

function OutcomeButtons({
  value,
  onChange,
}: {
  value: Outcome | null
  onChange: (o: Outcome) => void
}) {
  return (
    <div className="outcome-group" role="radiogroup" aria-label="Outcome">
      {(['success', 'partial', 'failed'] as Outcome[]).map((o) => {
        const active = value === o
        return (
          <button
            key={o}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o)}
            className={`outcome-btn ${OUTCOME_TONE[o]}`}
          >
            {OUTCOME_LABEL[o]}
          </button>
        )
      })}
    </div>
  )
}

function ChipInput({
  label,
  values,
  onChange,
  placeholder,
}: {
  label: string
  values: string[]
  onChange: (next: string[]) => void
  placeholder?: string
}) {
  const [draft, setDraft] = useState('')
  const add = () => {
    const v = draft.trim()
    if (!v) return
    if (!values.includes(v)) onChange([...values, v])
    setDraft('')
  }
  return (
    <div>
      <label>{label}</label>
      <div className="row">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ',') {
              e.preventDefault()
              add()
            }
          }}
          placeholder={placeholder ?? 'Type and press Enter'}
        />
        <button type="button" className="ghost" onClick={add}>
          Add
        </button>
      </div>
      {values.length > 0 && (
        <div style={{ marginTop: 8 }}>
          {values.map((v) => (
            <span key={v} className="chip">
              {v}
              <button
                type="button"
                aria-label={`Remove ${v}`}
                onClick={() => onChange(values.filter((x) => x !== v))}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function QuickLog({ labId }: { labId: string }) {
  const api = useApi()
  const qc = useQueryClient()
  const keyPrefix = useApiKeyPrefix()
  const [text, setText] = useState('')
  const [hint, setHint] = useState<Outcome | null>(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<ExperimentCreateResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!text.trim()) return
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const res = await api<ExperimentCreateResponse>(
        `/api/v1/labs/${labId}/experiments/quick`,
        {
          method: 'POST',
          body: { text, outcome_hint: hint },
        },
      )
      setResult(res)
      setText('')
      setHint(null)
      qc.invalidateQueries({ queryKey: [keyPrefix, 'lab-state', labId] })
    } catch (err) {
      const e = err as { detail?: string }
      setError(e.detail ?? 'Quick-log failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="stack" style={{ gap: 16 }}>
      <div>
        <label>Description</label>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Tried Western blot for HSP90 in HEK293, no signal. Probably bad antibody — switching vendor next time."
          rows={4}
          autoFocus
        />
        <p className="muted" style={{ marginTop: 4 }}>
          Single text field — LLM parses technique, equipment, and outcome.
        </p>
      </div>
      <div>
        <label>Outcome hint (optional)</label>
        <OutcomeButtons value={hint} onChange={setHint} />
      </div>
      <div className="row">
        <button type="submit" disabled={busy || !text.trim()}>
          {busy ? 'Logging…' : 'Log experiment'}
        </button>
        {result && (
          <span className="success">
            Logged in {result.elapsed_ms ?? '?'}ms — {result.experiment.technique}
          </span>
        )}
      </div>
      {error && <div className="error">{error}</div>}
    </form>
  )
}

const EMPTY_ENTRY: ExperimentEntry = {
  technique: '',
  outcome: 'success',
  notes: '',
  equipment_used: [],
  organisms_used: [],
  reagents_used: [],
}

function StructuredEntry({ labId }: { labId: string }) {
  const api = useApi()
  const qc = useQueryClient()
  const keyPrefix = useApiKeyPrefix()
  const [entry, setEntry] = useState<ExperimentEntry>({ ...EMPTY_ENTRY })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const set = <K extends keyof ExperimentEntry>(k: K, v: ExperimentEntry[K]) =>
    setEntry((prev) => ({ ...prev, [k]: v }))

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setSuccess(null)
    try {
      const res = await api<ExperimentCreateResponse>(
        `/api/v1/labs/${labId}/experiments`,
        { method: 'POST', body: entry },
      )
      setSuccess(`Logged in ${res.elapsed_ms ?? '?'}ms`)
      setEntry({ ...EMPTY_ENTRY })
      qc.invalidateQueries({ queryKey: [keyPrefix, 'lab-state', labId] })
    } catch (err) {
      const e = err as { detail?: string }
      setError(e.detail ?? 'Submit failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="stack" onSubmit={submit} style={{ gap: 16 }}>
      <div>
        <label>Technique</label>
        <input
          value={entry.technique}
          onChange={(e) => set('technique', e.target.value)}
          required
          maxLength={200}
        />
      </div>
      <div>
        <label>Outcome</label>
        <OutcomeButtons
          value={entry.outcome}
          onChange={(o) => set('outcome', o)}
        />
      </div>
      <div>
        <label>Notes</label>
        <textarea
          value={entry.notes}
          onChange={(e) => set('notes', e.target.value)}
          required
          maxLength={5000}
          rows={4}
        />
      </div>
      <ChipInput
        label="Equipment used"
        values={entry.equipment_used ?? []}
        onChange={(v) => set('equipment_used', v)}
      />
      <ChipInput
        label="Organisms used"
        values={entry.organisms_used ?? []}
        onChange={(v) => set('organisms_used', v)}
      />
      <ChipInput
        label="Reagents used"
        values={entry.reagents_used ?? []}
        onChange={(v) => set('reagents_used', v)}
      />
      <div className="row">
        <button type="submit" disabled={busy || !entry.technique || !entry.notes}>
          {busy ? 'Saving…' : 'Save experiment'}
        </button>
        {success && <span className="success">{success}</span>}
      </div>
      {error && <div className="error">{error}</div>}
    </form>
  )
}

// CSV parser: comma-separated, quote-aware. Header row required.
// Multi-value columns (equipment_used, organisms_used, reagents_used) use `;`.
function parseCsv(text: string): ExperimentEntry[] {
  const rows: string[][] = []
  let row: string[] = []
  let cell = ''
  let inQuotes = false
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (inQuotes) {
      if (c === '"' && text[i + 1] === '"') {
        cell += '"'
        i++
      } else if (c === '"') {
        inQuotes = false
      } else {
        cell += c
      }
    } else if (c === '"') {
      inQuotes = true
    } else if (c === ',') {
      row.push(cell)
      cell = ''
    } else if (c === '\n' || c === '\r') {
      if (cell || row.length) {
        row.push(cell)
        rows.push(row)
        row = []
        cell = ''
      }
      if (c === '\r' && text[i + 1] === '\n') i++
    } else {
      cell += c
    }
  }
  if (cell || row.length) {
    row.push(cell)
    rows.push(row)
  }
  if (rows.length < 2) return []
  const header = rows[0].map((h) => h.trim().toLowerCase())
  const idx = (k: string) => header.indexOf(k)
  const toList = (s: string) =>
    s.split(';').map((x) => x.trim()).filter(Boolean)

  return rows.slice(1).map((r) => ({
    technique: r[idx('technique')]?.trim() ?? '',
    outcome: ((r[idx('outcome')] ?? 'success').trim() as Outcome) || 'success',
    notes: r[idx('notes')]?.trim() ?? '',
    equipment_used: toList(r[idx('equipment_used')] ?? ''),
    organisms_used: toList(r[idx('organisms_used')] ?? ''),
    reagents_used: toList(r[idx('reagents_used')] ?? ''),
  }))
}

function BulkImport({ labId }: { labId: string }) {
  const api = useApi()
  const qc = useQueryClient()
  const keyPrefix = useApiKeyPrefix()
  const [csv, setCsv] = useState('')
  const [parsed, setParsed] = useState<ExperimentEntry[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<BulkExperimentResponse | null>(null)

  const onParse = () => {
    setError(null)
    try {
      const rows = parseCsv(csv)
      if (rows.length === 0) {
        setError('No data rows found.')
        return
      }
      setParsed(rows)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const onSubmit = async () => {
    if (!parsed.length) return
    setBusy(true)
    setError(null)
    try {
      const res = await api<BulkExperimentResponse>(
        `/api/v1/labs/${labId}/experiments/bulk`,
        { method: 'POST', body: { entries: parsed } },
      )
      setResult(res)
      qc.invalidateQueries({ queryKey: [keyPrefix, 'lab-state', labId] })
    } catch (err) {
      const e = err as { detail?: string }
      setError(e.detail ?? 'Bulk import failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack" style={{ gap: 16 }}>
      <p className="muted">
        CSV header: <code>technique,outcome,notes,equipment_used,organisms_used,reagents_used</code>.{' '}
        Multi-value columns use <code>;</code> as separator. Up to 500 rows per import.
      </p>
      <textarea
        className="mono"
        value={csv}
        onChange={(e) => setCsv(e.target.value)}
        rows={8}
        placeholder={`technique,outcome,notes,equipment_used,organisms_used,reagents_used\nWestern blot,success,Detected HSP90 cleanly,BioRad imager,HEK293,anti-HSP90`}
      />
      <div className="row">
        <button type="button" className="ghost" onClick={onParse} disabled={!csv.trim()}>
          Parse
        </button>
        <button type="button" onClick={onSubmit} disabled={busy || parsed.length === 0}>
          {busy ? 'Importing…' : `Import ${parsed.length} row${parsed.length === 1 ? '' : 's'}`}
        </button>
      </div>
      {error && <div className="error">{error}</div>}
      {parsed.length > 0 && !result && (
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Technique</th>
              <th>Outcome</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {parsed.slice(0, 5).map((p, i) => (
              <tr key={i}>
                <td>{i + 1}</td>
                <td>{p.technique}</td>
                <td>{p.outcome}</td>
                <td>{p.notes.slice(0, 80)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {result && (
        <div className={result.failed.length ? 'warning' : 'success'}>
          Created {result.created.length}, failed {result.failed.length}.
          {result.failed.length > 0 && (
            <ul>
              {result.failed.map((f) => (
                <li key={f.index}>row {f.index}: {f.error}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

const MODE_LABEL: Record<Mode, string> = {
  quick: 'Quick log',
  structured: 'Structured',
  bulk: 'Bulk import',
}

export default function Experiments() {
  const { data: lab } = useLab()
  const [mode, setMode] = useState<Mode>('quick')

  if (!lab) return null

  return (
    <>
      <header>
        <div>
          <div className="kicker">Experiment entry</div>
          <h1>Log experiment</h1>
        </div>
        <div className="segmented" role="tablist" aria-label="Entry mode">
          {(['quick', 'structured', 'bulk'] as Mode[]).map((m) => (
            <button
              key={m}
              role="tab"
              aria-pressed={mode === m}
              aria-selected={mode === m}
              onClick={() => setMode(m)}
            >
              {MODE_LABEL[m]}
            </button>
          ))}
        </div>
      </header>

      {mode === 'quick' && <QuickLog labId={lab.id} />}
      {mode === 'structured' && <StructuredEntry labId={lab.id} />}
      {mode === 'bulk' && <BulkImport labId={lab.id} />}
    </>
  )
}
