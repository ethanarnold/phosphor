export default function ScoreBar({
  value,
  label,
  threshold = 0.85,
}: {
  value: number
  label: string
  threshold?: number
}) {
  const clamped = Math.max(0, Math.min(1, value))
  const pct = clamped * 100
  const high = clamped >= threshold
  return (
    <div className={`score-row${high ? ' high' : ''}`}>
      <span className="lbl">{label}</span>
      <div className="bar">
        <div
          className="fill"
          style={{ width: `${pct}%`, background: high ? 'var(--signal)' : 'var(--ink)' }}
        />
      </div>
      <span className="val">{value.toFixed(2)}</span>
    </div>
  )
}
