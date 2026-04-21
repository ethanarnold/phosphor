export default function ScoreBar({ value, label }: { value: number; label: string }) {
  const pct = Math.max(0, Math.min(1, value)) * 100
  const color = pct > 66 ? '#22c55e' : pct > 33 ? '#eab308' : '#ef4444'
  return (
    <div className="score-row">
      <span className="lbl">{label}</span>
      <div className="bar">
        <div className="fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="val">{value.toFixed(2)}</span>
    </div>
  )
}
