import type { ReactNode } from 'react'

export default function Empty({
  title,
  body,
  cta,
}: {
  title: string
  body?: ReactNode
  cta?: ReactNode
}) {
  return (
    <div className="card" style={{ textAlign: 'center', padding: '2rem 1rem' }}>
      <h3>{title}</h3>
      {body && <div className="muted" style={{ marginBottom: cta ? 12 : 0 }}>{body}</div>}
      {cta}
    </div>
  )
}
