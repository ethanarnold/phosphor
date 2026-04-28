import AgentRunner from '../components/AgentRunner'

export default function Directions() {
  return (
    <AgentRunner
      purpose="directions"
      kicker="Agent"
      title="Directions"
      description="Surface novel research directions feasible for this lab. The agent reads your state and the literature you've ingested, and proposes 2–3 specific moves grounded in your actual capabilities."
      inputLabel="Focus area (optional)"
      inputPlaceholder="e.g. neurodegeneration, microglial heterogeneity, in-vivo CRISPR delivery — or leave blank to draw from the lab state's strongest themes."
      inputMinLength={0}
      inputMaxLength={2000}
      inputRequired={false}
      submitLabel="Find directions"
      runningLabel="Searching…"
      newRunLabel="New search"
      idleHint="Optional: paste a focus area on the left. The agent will combine your lab's strongest capabilities with what's emerging in your literature corpus to propose specific, feasible directions."
      resultKicker={(turns) => `Directions · ${turns} turn${turns === 1 ? '' : 's'}`}
    />
  )
}
