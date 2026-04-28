import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import {
  useApi,
  type AgentCreateResponse,
  type AgentDetail,
  type AgentMessageView,
} from '../lib/api'
import { useLab } from '../lib/queries'

type PaneState =
  | { kind: 'idle' }
  | { kind: 'running'; sessionId: string; startedAt: number; detail: AgentDetail | null }
  | { kind: 'complete'; detail: AgentDetail }
  | { kind: 'error'; detail: AgentDetail | null; message: string }

const POLL_INTERVAL_MS = 1500

export type AgentRunnerProps = {
  purpose: 'reviewer' | 'directions' | 'strengthen'
  kicker: string
  title: string
  description: string
  inputLabel: string
  inputPlaceholder: string
  inputMinLength: number
  inputMaxLength: number
  /** When false, an empty submit is allowed (the directions agent). */
  inputRequired: boolean
  submitLabel: string
  runningLabel: string
  newRunLabel: string
  idleHint: string
  /** Builds the post-run heading; receives the model's turn count. */
  resultKicker: (turns: number) => string
}

function ElapsedClock({ startedAt }: { startedAt: number }) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(t)
  }, [])
  return <span className="mono">{Math.round((now - startedAt) / 1000)}s</span>
}

function toolCallsFromMessages(messages: AgentMessageView[]): AgentMessageView[] {
  return messages.filter((m) => m.tool_name !== null)
}

function activeToolName(messages: AgentMessageView[]): string | null {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i]
    if (m.role === 'assistant' && m.tool_name) {
      const resolved = messages
        .slice(i + 1)
        .some((n) => n.role === 'tool' && n.tool_name === m.tool_name)
      if (!resolved) return m.tool_name
    }
  }
  return null
}

function formatJson(value: Record<string, unknown> | null): string {
  if (value == null) return ''
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function ToolTrace({ messages }: { messages: AgentMessageView[] }) {
  const rows = toolCallsFromMessages(messages)
  if (rows.length === 0) return null
  type Pair = { call: AgentMessageView; result: AgentMessageView | null }
  const pairs: Pair[] = []
  let pending: AgentMessageView | null = null
  for (const m of rows) {
    if (m.role === 'assistant') {
      if (pending) pairs.push({ call: pending, result: null })
      pending = m
    } else if (m.role === 'tool') {
      if (pending) {
        pairs.push({ call: pending, result: m })
        pending = null
      } else {
        pairs.push({ call: m, result: m })
      }
    }
  }
  if (pending) pairs.push({ call: pending, result: null })

  return (
    <details className="tool-trace">
      <summary>
        <span className="kicker" style={{ margin: 0 }}>
          Tool trace — {pairs.length} call{pairs.length === 1 ? '' : 's'}
        </span>
      </summary>
      <div className="list" style={{ marginTop: 12 }}>
        {pairs.map((p, i) => (
          <div key={p.call.id} className="row-item" style={{ gridTemplateColumns: '32px 1fr' }}>
            <div className="idx">{String(i + 1).padStart(2, '0')}</div>
            <div className="stack" style={{ gap: 6 }}>
              <div className="mono" style={{ fontSize: 13 }}>
                {p.call.tool_name}
                <span className="muted" style={{ marginLeft: 8 }}>
                  {Object.keys(p.call.tool_args_json ?? {}).length > 0
                    ? formatJson(p.call.tool_args_json).replace(/\s+/g, ' ').slice(0, 120)
                    : '{}'}
                </span>
              </div>
              {p.result ? (
                <pre
                  className="mono"
                  style={{
                    margin: 0,
                    padding: 8,
                    border: '1px solid var(--rule)',
                    borderRadius: 2,
                    fontSize: 11,
                    lineHeight: 1.45,
                    color: 'var(--ink-2)',
                    maxHeight: 200,
                    overflow: 'auto',
                    whiteSpace: 'pre-wrap',
                  }}
                >
                  {formatJson(p.result.tool_result_json).slice(0, 2000)}
                </pre>
              ) : (
                <span className="muted">running…</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </details>
  )
}

function ResultPane({
  state,
  idleHint,
  resultKicker,
}: {
  state: PaneState
  idleHint: string
  resultKicker: (turns: number) => string
}) {
  if (state.kind === 'idle') {
    return (
      <div className="muted" style={{ padding: 'var(--s-5) 0' }}>
        {idleHint}
      </div>
    )
  }

  if (state.kind === 'running') {
    const tool = state.detail ? activeToolName(state.detail.messages) : null
    return (
      <div className="stack" style={{ gap: 16 }}>
        <div className="kicker" style={{ margin: 0 }}>Running</div>
        <div>
          Thinking… <ElapsedClock startedAt={state.startedAt} />
          {tool && (
            <span className="muted" style={{ marginLeft: 12 }}>
              calling <span className="mono">{tool}</span>
            </span>
          )}
        </div>
        {state.detail && <ToolTrace messages={state.detail.messages} />}
      </div>
    )
  }

  if (state.kind === 'error') {
    return (
      <div className="stack" style={{ gap: 12 }}>
        <div className="error">{state.message}</div>
        {state.detail && <ToolTrace messages={state.detail.messages} />}
      </div>
    )
  }

  return (
    <div className="stack" style={{ gap: 16 }}>
      <div className="kicker" style={{ margin: 0 }}>
        {resultKicker(state.detail.turn_count)}
        {state.detail.model && <span className="muted"> · {state.detail.model}</span>}
      </div>
      <article
        style={{
          fontSize: 16,
          lineHeight: 1.65,
          color: 'var(--ink-2)',
          maxWidth: '62ch',
          whiteSpace: 'pre-wrap',
        }}
      >
        {state.detail.final_answer}
      </article>
      <ToolTrace messages={state.detail.messages} />
    </div>
  )
}

export default function AgentRunner({
  purpose,
  kicker,
  title,
  description,
  inputLabel,
  inputPlaceholder,
  inputMinLength,
  inputMaxLength,
  inputRequired,
  submitLabel,
  runningLabel,
  newRunLabel,
  idleHint,
  resultKicker,
}: AgentRunnerProps) {
  const api = useApi()
  const { data: lab } = useLab()
  const [input, setInput] = useState('')
  const [state, setState] = useState<PaneState>({ kind: 'idle' })
  const [submitting, setSubmitting] = useState(false)
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

  const poll = useCallback(
    async (labId: string, sessionId: string, startedAt: number) => {
      try {
        const detail = await api<AgentDetail>(
          `/api/v1/labs/${labId}/${purpose}/${sessionId}`,
        )
        if (detail.status === 'complete') {
          setState({ kind: 'complete', detail })
          return
        }
        if (detail.status === 'error') {
          setState({
            kind: 'error',
            detail,
            message: detail.error ?? `${title} run failed.`,
          })
          return
        }
        setState({ kind: 'running', sessionId, startedAt, detail })
        pollTimer.current = window.setTimeout(
          () => poll(labId, sessionId, startedAt),
          POLL_INTERVAL_MS,
        )
      } catch (err) {
        const e = err as { detail?: string; status?: number }
        setState({
          kind: 'error',
          detail: null,
          message: e.detail ?? `Poll failed (HTTP ${e.status ?? '?'}).`,
        })
      }
    },
    [api, purpose, title],
  )

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!lab) return
    const text = input.trim()
    if (inputRequired && text.length < inputMinLength) return
    if (text.length > inputMaxLength) return
    stopPolling()
    setSubmitting(true)
    setState({ kind: 'running', sessionId: '', startedAt: Date.now(), detail: null })
    try {
      const res = await api<AgentCreateResponse>(
        `/api/v1/labs/${lab.id}/${purpose}`,
        { method: 'POST', body: { input_text: text } },
      )
      const startedAt = Date.now()
      setState({ kind: 'running', sessionId: res.session_id, startedAt, detail: null })
      pollTimer.current = window.setTimeout(
        () => poll(lab.id, res.session_id, startedAt),
        POLL_INTERVAL_MS,
      )
    } catch (err) {
      const e = err as { detail?: string; status?: number }
      setState({
        kind: 'error',
        detail: null,
        message: e.detail ?? `Could not start ${title.toLowerCase()} (HTTP ${e.status ?? '?'}).`,
      })
    } finally {
      setSubmitting(false)
    }
  }

  if (!lab) return null

  const inputLen = input.trim().length
  const tooShort = inputRequired && inputLen > 0 && inputLen < inputMinLength
  const tooLong = inputLen > inputMaxLength
  const disabled =
    submitting ||
    state.kind === 'running' ||
    (inputRequired && inputLen < inputMinLength) ||
    tooLong

  const lengthHint = inputRequired
    ? `${inputMinLength}–${inputMaxLength} characters.`
    : `Optional. Up to ${inputMaxLength} characters.`

  return (
    <>
      <header>
        <div>
          <div className="kicker">{kicker}</div>
          <h1>{title}</h1>
        </div>
      </header>

      <p className="muted" style={{ marginTop: 0, maxWidth: '62ch' }}>
        {description}
      </p>

      <div className="review-grid">
        <form className="stack" onSubmit={submit} style={{ gap: 16 }}>
          <div>
            <label htmlFor="agent-input">{inputLabel}</label>
            <textarea
              id="agent-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={inputPlaceholder}
              rows={14}
              maxLength={inputMaxLength + 100}
              disabled={state.kind === 'running'}
            />
            <div
              className="muted"
              style={{ marginTop: 6, display: 'flex', justifyContent: 'space-between' }}
            >
              <span>
                {tooShort && `At least ${inputMinLength} characters. `}
                {tooLong && `Must be ${inputMaxLength} characters or fewer. `}
                {!tooShort && !tooLong && lengthHint}
              </span>
              <span className="mono">{inputLen}</span>
            </div>
          </div>
          <div className="row">
            <button type="submit" disabled={disabled}>
              {state.kind === 'running' ? runningLabel : submitLabel}
            </button>
            {state.kind !== 'idle' && state.kind !== 'running' && (
              <button
                type="button"
                className="ghost"
                onClick={() => {
                  stopPolling()
                  setState({ kind: 'idle' })
                }}
              >
                {newRunLabel}
              </button>
            )}
          </div>
        </form>

        <div className="review-result">
          <ResultPane state={state} idleHint={idleHint} resultKicker={resultKicker} />
        </div>
      </div>
    </>
  )
}
