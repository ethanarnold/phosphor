# Frontend redesign brief

You are redesigning the Phosphor frontend end-to-end. The current UI works but looks like a generic AI-generated SaaS dashboard (indigo on cold-white, system-font stack, bordered cards stacked vertically, uniform padding everywhere). We want the opposite of that.

Read `CLAUDE.md` in full before starting — the "UI Design System" section is the source of truth for tokens, fonts, components, and the don't-do list. Then open `.claude/design-showcase.html` in a browser — it's a faithful render of the direction with every token, type specimen, and component pattern you'll implement. Everything in this brief is scaffolding; the showcase is the target.

## Direction in one sentence

Linear-style restraint applied to a biochemist's working tool: ink on warm paper, Fraunces for voice, Inter Tight for interface, JetBrains Mono for data, hairline rules instead of cards, one signal hue reserved for the composite-score numeral when it clears 0.85.

The `frontend-design` skill is available and will auto-trigger. Use its guidance — but note this project deliberately aims for refined-minimal rather than maximalist. Boldness here lives in typography, scale, and whitespace, not in color or ornament.

## Before you touch any code

1. **Cut a feature branch.** The repo's convention is feature branch + PR to main, never direct commits to main. Suggested name: `feat/ui-redesign-linear-direction`.
2. **Start the dev server** (`cd frontend && npm run dev`) and the backend if needed. Keep it running throughout.
3. **Connect Chrome DevTools MCP.** The `mcp__chrome-devtools__*` tools are configured in `.mcp.json` at project scope. Use `navigate_page`, `take_screenshot`, `take_snapshot`, `resize_page`, `list_console_messages` to verify each page as you change it. Screenshot at `1440x900` (desktop) and `768x1024` (tablet). Don't ship a page without visually confirming it.
4. **Don't migrate to Tailwind / CSS-in-JS / shadcn.** The stack stays plain CSS + CSS variables in `frontend/src/styles.css`. That's a hard constraint.

## Dependencies you will add

Only add a package when a component genuinely needs it. Expected additions:

- **Fonts:** no package — load Fraunces, Inter Tight, JetBrains Mono via a `<link>` in `frontend/index.html` (Google Fonts). The exact URL is in `.claude/design-showcase.html` — copy it.
- **Radix primitives** (install only as each gets introduced):
  - `@radix-ui/react-tabs` — the Experiments page mode switcher, if you rebuild it as a proper tab component (optional; the current three-button switcher is acceptable restyled)
  - `@radix-ui/react-dialog` — if any modal is needed (current code has none; skip for now)
  - `@radix-ui/react-tooltip` — if hover explanations become useful on score bars (optional)

Do **not** install a framework-level package (shadcn, Mantine, Chakra, Tailwind, Framer Motion). Motion, if needed, is CSS-only.

## Scope, in priority order

Do these in order. Commit at each checkpoint so the diff is readable.

### Checkpoint 1 — Foundation

Files:
- `frontend/index.html` — add Google Fonts `<link>` for Fraunces (opsz 9..144, weights 300–600), Inter Tight (400/500/600), JetBrains Mono (400/500). Set `<html lang>` and a neutral title if missing.
- `frontend/src/styles.css` — full rewrite of `:root` tokens and base styles. Replace the indigo palette with the ink/paper tokens from CLAUDE.md. Replace system-font stack with the three faces. Rework `button`, `input`, `select`, `textarea`, `h1–h4`, `.card`, `.tag`, `.dropzone`, `.score-row`, table styles, sidebar styles. Remove the old `.complexity-low/medium/high` fills — tags are outlined with colored text/border per the showcase. Keep the `.muted`, `.error`, `.success`, `.warning` utility classes but restyle them as hairline-ruled text blocks rather than filled pastel boxes.
- `frontend/src/components/Layout.tsx` — widen sidebar to 240px; add a Fraunces wordmark; treat nav as a quiet column with a hairline divider under the brand. Sidebar footer (OrganizationSwitcher + UserButton) stays but tighten spacing.

Verify with DevTools MCP: navigate to `/`, screenshot. Compare to the showcase's masthead + hero feel.

### Checkpoint 2 — Primary reading/ranking surfaces

Files:
- `frontend/src/pages/Dashboard.tsx`
  - H1 in Fraunces, 44px weight 400, with a mono-caps kicker above it (`"Lab dashboard"` → the kicker; lab name is the H1).
  - Replace the bordered-card tile grid with a hairline-ruled metric row (see showcase section 05 pattern for rule usage).
  - Replace the top-opportunities `<table>` inside a `.card` with the hairline list pattern from the showcase (grid rows separated by `var(--rule)`, no outer card, `hover: var(--surface-2)`).
  - Apply the `--signal` color to the composite numeral *only* when it's ≥ 0.85.
- `frontend/src/pages/Opportunities.tsx`
  - Same hairline-list pattern. Drop the outer card. The complexity filter becomes a slim control bar above the list, not a card.
- `frontend/src/pages/OpportunityDetail.tsx`
  - **This is the editorial surface.** Two-column layout: main article column (max 62ch) on the left, 260px metadata rail on the right. On `<= 760px`, collapse to single column.
  - H1 for the opportunity description in Fraunces 32–36px, weight 400.
  - Metadata rail is a `<dl>` with mono-caps `<dt>` labels and `<dd>` values, separated by hairline rules (see showcase section 04).
  - Score bars become the hairline variant from the showcase (2px track, tabular numeral).
  - Gap analysis stays as a block, but tags go to the outlined-mono style.
  - Protocol view: when a protocol is generated, use Fraunces for phase headings (H4 → Fraunces 20px), serif body feel for expected outcomes / citations. Export button is a ghost button.

### Checkpoint 3 — Input surfaces

Files:
- `frontend/src/pages/Experiments.tsx`
  - Mode switcher (`quick / structured / bulk`) stays as three buttons, but styled as a segmented control: ghost buttons with one showing the filled-accent state. Optionally swap in `@radix-ui/react-tabs` for accessibility; not required.
  - `QuickLog` form: remove the `.card` outer chrome or keep it as a minimal hairline container. Outcome buttons (`worked / partial / failed`) keep their semantic colors — this is a case where color earns its keep, so don't strip it. But switch from saturated web greens/reds to the muted earth tones (`--ok`, `--warn`, `--danger`) for the outlined state, with fill on the active state.
  - `ChipInput`: tags become outlined mono per the token spec.
  - `BulkImport`: the CSV textarea uses JetBrains Mono.
- `frontend/src/pages/LabState.tsx`, `Documents.tsx`, `Literature.tsx`, `Search.tsx`
  - Apply tokens; no major structural change unless the existing layout has a clear AI-SaaS smell. Use your judgment against the showcase as the reference.

### Checkpoint 4 — Supporting components

- `frontend/src/components/ScoreBar.tsx` — rebuild as the hairline variant: 2px track in `--rule`, fill in `--ink` (or `--signal` when passed `variant="high"`), tabular mono numeral on the right. Take a `threshold` prop or infer: fill uses `--signal` iff value ≥ 0.85.
- `frontend/src/components/Empty.tsx` — quiet. Fraunces heading, Inter Tight body, centered but generous whitespace (min 120px vertical). No bordered card around it; just whitespace and a hairline above/below if the page needs visual containment.
- `frontend/src/components/AuthGate.tsx` — only change if it has visible UI. Most likely just colors.

## Verification protocol

For each checkpoint, before committing:

1. `cd frontend && npm run build` must succeed (typecheck + Vite build).
2. Use Chrome DevTools MCP:
   - `navigate_page` to each route
   - `take_screenshot` at 1440x900
   - `list_console_messages` — no errors, no font-loading failures
   - Spot-check one route at 768x1024 (tablet) — layout should hold up
3. Re-open `.claude/design-showcase.html` in a browser tab and sanity-check that the page you just built reads the same way: same font personality, same scale, same ink/paper feel, no stray indigo or purple.

## Definition of done

- All pages render using only tokens from CLAUDE.md. Grep `frontend/src/` for old hex values (`#4f46e5`, `#eef2ff`, `#22c55e`, `#eab308`, `#ef4444`, `#16a34a`, `#d97706`, `#dc2626`) — all gone.
- Fonts load (network tab shows Fraunces / Inter Tight / JetBrains Mono fetched). No `system-ui` fallback visible on a warm-cache reload.
- No violations of the don't-do list in CLAUDE.md.
- `npm run build` clean. No new ESLint/TS errors.
- Every route screenshot-verified via Chrome DevTools MCP.

## Out of scope for this PR

- Backend changes. This is frontend only.
- Dark mode. (Plan for it later by theming the CSS variables; don't implement now.)
- New features or reworked information architecture — pages keep their routes, data, and function. Only the shell and styling change.
- Icon library. If an icon is unavoidable later, we'll discuss — don't pull one in here.
- Animation libraries. CSS only.

## PR expectations

When the sweep is done:

1. Push the branch.
2. Open a PR titled `feat(frontend): redesign UI to Linear-style editorial direction` (or similar).
3. PR body: one-paragraph summary of the design direction (quote CLAUDE.md), a "Pages touched" bullet list, and 3–5 embedded screenshots (Dashboard, Opportunities list, Opportunity detail, Experiments quick-log) captured via Chrome DevTools MCP. Include a "Don't-do list audit" subsection confirming each rule was followed.
4. Do not merge; the user reviews and merges.

## Open questions / judgment calls you own

- Whether to adopt Radix Tabs for the Experiments mode switcher — your call. If you do, install `@radix-ui/react-tabs` and style it against the tokens. If you don't, restyle the existing buttons as a segmented control.
- Exact signal-score threshold — `≥ 0.85` is the default; if the data produces nothing above that in practice (check in DevTools), lower to `≥ 0.80` and note it in the PR body.
- Serif vs sans for protocol body copy — prototype both, pick the one that reads better against the rest of the page. Default guess: sans (Inter Tight) for protocol steps because they're procedural; serif (Fraunces) for expected outcomes and citations because they're discursive.

If anything in this brief contradicts CLAUDE.md, CLAUDE.md wins — surface the contradiction.
