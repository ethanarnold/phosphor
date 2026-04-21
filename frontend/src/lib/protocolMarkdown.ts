import type { Protocol } from './api'

export function protocolToMarkdown(p: Protocol): string {
  const lines: string[] = []
  lines.push(`# ${p.title}`)
  lines.push('')
  lines.push(
    `_Generated against lab state v${p.lab_state_version} using ${p.llm_model} (prompt ${p.prompt_version})_`,
  )
  lines.push('')

  if (p.content.flagged_gaps.length > 0) {
    lines.push('## Flagged gaps')
    for (const g of p.content.flagged_gaps) lines.push(`- ${g}`)
    lines.push('')
  }

  if (p.content.materials.length > 0) {
    lines.push('## Materials')
    for (const m of p.content.materials) lines.push(`- ${m}`)
    lines.push('')
  }

  p.content.phases.forEach((phase, i) => {
    lines.push(
      `## Phase ${i + 1}: ${phase.name}${
        phase.duration_estimate ? ` _(${phase.duration_estimate})_` : ''
      }`,
    )
    phase.steps.forEach((s, j) => lines.push(`${j + 1}. ${s}`))
    if (phase.materials_used.length > 0) {
      lines.push('')
      lines.push(`_Materials: ${phase.materials_used.join(', ')}_`)
    }
    lines.push('')
  })

  lines.push('## Expected outcomes')
  for (const o of p.content.expected_outcomes) lines.push(`- ${o}`)

  if (p.content.citations.length > 0) {
    lines.push('')
    lines.push('## Citations')
    for (const c of p.content.citations) lines.push(`- ${c}`)
  }

  return lines.join('\n')
}

export function downloadMarkdown(p: Protocol): void {
  const md = protocolToMarkdown(p)
  const blob = new Blob([md], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const safeName = p.title.replace(/[^\w\s.-]/g, '').replace(/\s+/g, '_').slice(0, 80)
  a.download = `${safeName || 'protocol'}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
