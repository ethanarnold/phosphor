import { SignInButton, SignUpButton } from '@clerk/clerk-react'
import BrandMark from './BrandMark'

/**
 * Public-facing landing page rendered in <SignedOut>.
 * Editorial, not marketing — matches the Linear/Stripe-docs direction in CLAUDE.md.
 * Nothing decorative; structure comes from typography, hairlines, and whitespace.
 */
export default function Landing() {
  return (
    <div className="landing">
      <header className="landing-top">
        <div className="brand"><BrandMark size="sidebar" /></div>
        <nav className="landing-nav">
          <a href="#how" className="muted">How it works</a>
          <a href="#why" className="muted">Why</a>
          <SignInButton mode="modal">
            <button className="ghost">Sign in</button>
          </SignInButton>
          <SignUpButton mode="modal">
            <button>Get started</button>
          </SignUpButton>
        </nav>
      </header>

      <section className="landing-hero">
        <div className="kicker">Lab context for LLM agents</div>
        <h1>
          A research lab,<br />
          in 2,000 tokens.
        </h1>
        <p className="lede">
          Phosphor distills a lab&apos;s equipment, techniques, expertise, and
          experimental history into a compact representation an LLM agent can
          reason over in a single prompt. The first workflow it powers: a
          literature radar that surfaces only the research directions your
          lab could actually run this week. More agents to follow.
        </p>
        <div className="landing-cta">
          <SignUpButton mode="modal">
            <button>Get started</button>
          </SignUpButton>
          <SignInButton mode="modal">
            <button className="ghost">Sign in</button>
          </SignInButton>
          <span className="muted">Requires a lab organization.</span>
        </div>
      </section>

      <section id="how" className="landing-three">
        <div className="three-col">
          <article>
            <div className="kicker">The primitive</div>
            <h3>Compressed lab state</h3>
            <p>
              A lab is a messy object — years of instruments, protocols,
              failures, and tacit know-how. Phosphor continuously distills
              all of it into a structured ~2,000-token representation that
              a frontier model can hold in context at once.
            </p>
            <p className="muted">
              Validated by factual-QA evals: the compressed state must let
              an LLM answer ground-truth questions about the lab.
            </p>
          </article>
          <article>
            <div className="kicker">Today</div>
            <h3>A literature radar</h3>
            <p>
              The first agent built on top: a daily scan of PubMed and
              Semantic Scholar that extracts concrete research directions,
              scores each against the lab state for feasibility, and lists
              the gaps you&apos;d need to close to pursue them.
            </p>
            <p className="muted">
              High-match opportunities come with a protocol draft grounded
              in the lab&apos;s actual methods.
            </p>
          </article>
          <article>
            <div className="kicker">Tomorrow</div>
            <h3>Every other agent</h3>
            <p>
              Once a lab is readable, any workflow that needs to know what
              it can do becomes tractable — collaboration matching, grant
              fit analysis, onboarding new researchers, triaging reagent
              requests, planning equipment purchases.
            </p>
            <p className="muted">
              The hard part is the representation. The agents are the easy
              part.
            </p>
          </article>
        </div>
      </section>

      <section id="why" className="landing-why">
        <div className="section-head">
          <span className="label">Why this tool exists</span>
        </div>
        <div className="why-grid">
          <p className="lede">
            Frontier models can now reason about scientific work at the
            scale of an entire field. What they can&apos;t do — yet — is
            know what&apos;s in your freezer, which assays your postdoc is
            trained on, or which failures your lab has already logged.
            Phosphor closes that gap.
          </p>
          <dl className="meta-list why-facts">
            <div>
              <dt>Lab state size</dt>
              <dd><span className="mono">≈2,000 tokens</span></dd>
            </div>
            <div>
              <dt>Fidelity check</dt>
              <dd><span className="mono">Factual QA evals</span></dd>
            </div>
            <div>
              <dt>Tenant isolation</dt>
              <dd><span className="mono">Row-level, per lab</span></dd>
            </div>
            <div>
              <dt>Model routing</dt>
              <dd><span className="mono">Provider-agnostic (LiteLLM)</span></dd>
            </div>
          </dl>
        </div>
      </section>

      <footer className="landing-foot">
        <div className="muted">
          Phosphor is early-access. Lab data stays private to your
          organization; nothing is shared across tenants.
        </div>
        <div className="landing-cta">
          <SignUpButton mode="modal">
            <button>Get started</button>
          </SignUpButton>
          <SignInButton mode="modal">
            <button className="ghost">Sign in</button>
          </SignInButton>
        </div>
      </footer>
    </div>
  )
}
