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
    <div
      style={{
        textAlign: 'center',
        padding: '120px 24px',
        borderTop: '1px solid var(--rule)',
        borderBottom: '1px solid var(--rule)',
        display: 'grid',
        gap: 12,
        placeItems: 'center',
      }}
    >
      <h2 style={{ margin: 0 }}>{title}</h2>
      {body && (
        <div
          style={{
            color: 'var(--ink-3)',
            fontSize: 14,
            maxWidth: '48ch',
            lineHeight: 1.55,
          }}
        >
          {body}
        </div>
      )}
      {cta && <div style={{ marginTop: 12 }}>{cta}</div>}
    </div>
  )
}
