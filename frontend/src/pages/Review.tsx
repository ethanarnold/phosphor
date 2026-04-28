import AgentRunner from '../components/AgentRunner'

export default function Review() {
  return (
    <AgentRunner
      purpose="reviewer"
      kicker="Agent"
      title="Reviewer"
      description="Paste a draft aim, abstract, or paragraph. The agent checks your lab state and experiment log, and returns a critique grounded in what the lab has actually done — with a concrete next step."
      inputLabel="Draft text"
      inputPlaceholder="Aim 2: We will optimize a CRISPR interference screen in primary human microglia to identify regulators of TREM2 expression, validating hits by immunocytochemistry and bulk RNA-seq."
      inputMinLength={20}
      inputMaxLength={4000}
      inputRequired
      submitLabel="Start review"
      runningLabel="Running…"
      newRunLabel="New review"
      idleHint="Paste a draft aim or abstract on the left. The reviewer will ground its critique in the lab's actual experiments and capabilities."
      resultKicker={(turns) => `Critique · ${turns} turn${turns === 1 ? '' : 's'}`}
    />
  )
}
