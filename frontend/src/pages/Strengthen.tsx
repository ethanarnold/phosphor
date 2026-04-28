import AgentRunner from '../components/AgentRunner'

export default function Strengthen() {
  return (
    <AgentRunner
      purpose="strengthen"
      kicker="Agent"
      title="Strengthen"
      description="Describe an in-progress project — goal, current state, what's stuck. The agent recommends 2–3 next experiments that would move it forward, grounded in the lab's actual capabilities."
      inputLabel="Project description"
      inputPlaceholder="We're characterizing a candidate TREM2 ligand in primary microglia. We have phagocytosis assay data showing a modest effect, but reviewers asked for orthogonal evidence and a dose-response. Stuck on what to run next given a 3-week timeline."
      inputMinLength={40}
      inputMaxLength={4000}
      inputRequired
      submitLabel="Find next steps"
      runningLabel="Working…"
      newRunLabel="New project"
      idleHint="Describe an in-progress project on the left. Be specific: what are you trying to show, what have you already collected, and what's blocking the next step?"
      resultKicker={(turns) => `Recommendations · ${turns} turn${turns === 1 ? '' : 's'}`}
    />
  )
}
