# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Phosphor is an AI research tool for labs. It maintains a compressed representation of a lab's capabilities and matches it against research opportunities from scientific literature.

**Core architecture (two inputs, one output):**
- **Input 1 - Lab State:** A continuously-distilled summary of lab capabilities (equipment, techniques, expertise, organisms, reagents, experimental history, constraints). Must compress to ~2K tokens while remaining LLM-interpretable.
- **Input 2 - Research Directions:** Actionable opportunities extracted from PubMed and Semantic Scholar (not vague "more research needed" — concrete with resource requirements).
- **Output - The Match:** Opportunities ranked by feasibility and alignment, with gap analysis and protocol generation.

## Tech Stack

- **Backend:** Python 3.12, FastAPI, Celery + Redis, PostgreSQL 16 + pgvector
- **Frontend:** React 18 + TypeScript + Vite
- **Auth:** Clerk (lab-level multi-tenancy)
- **LLM:** LiteLLM (provider-agnostic)
- **Document Parsing:** Unstructured.io
- **Storage:** S3/GCS
- **Infra:** Docker, Cloud Run or ECS

## Project Structure

```
/backend     # Python FastAPI application
/frontend    # React TypeScript application
/evals       # Evaluation harnesses for LLM prompts
```

## Development Standards

- TDD with 80% minimum coverage
- Conventional commits, feature branches, PR to main
- CI gates: lint (ruff), type check (mypy), test, SAST scanning, dependency audit
- Eval harness required for all LLM-facing prompts — prompt changes require eval approval before merge

## Security Requirements (Non-Negotiable)

Security is the highest priority. Lab data is proprietary and pre-publication.

- All API endpoints require authentication (except health checks)
- Row-level security on all tables for tenant isolation
- Pydantic strict mode for input validation
- Audit logging on all write operations
- No secrets in code or logs
- TLS 1.3 everywhere

## Key Design Constraints

1. **Lab state compression must maintain fidelity** — validate with factual QA evals that LLM can reason accurately over the compressed state
2. **Opportunity extraction must be concrete** — reject vague future directions, require identifiable resource requirements
3. **Input friction must be minimal** — target 30 seconds to log an experiment, or adoption fails

## UI Design System

Live reference: [`.claude/design-showcase.html`](.claude/design-showcase.html) (open in browser).

### Aesthetic direction

Linear-style restraint. Ink on warm paper with one functional accent. Boldness comes from typography and whitespace, **not** color or decoration. Audience is biochemists reading scientific literature — editorial where reading happens, dense where data lives. Nothing decorative.

### Design tokens

All tokens live as CSS custom properties in `frontend/src/styles.css`. Do not inline color values; always reference a token.

**Color**

| Token | Hex | Role |
|---|---|---|
| `--paper` | `#FAFAF7` | App background (warm off-white, never cold) |
| `--surface` | `#FFFFFF` | Cards, dialogs |
| `--surface-2` | `#F2F0E8` | Hover, inset |
| `--rule` | `#E4E2DA` | Hairline borders |
| `--rule-strong` | `#CAC7BB` | Dividers, input borders |
| `--ink` | `#0A0A0A` | Primary text |
| `--ink-2` | `#3D3D3A` | Secondary text |
| `--ink-3` | `#6B6B66` | Muted, metadata |
| `--accent` | `#2B2A28` | Primary CTA (warm near-black) |
| `--focus` | `#8B8680` | Focus ring (warm neutral, not blue) |
| `--signal` | `#C8441F` | Oxidized red — **high-score numerals only** (composite ≥ 0.85) |
| `--ok` | `#4C6B3C` | Success text |
| `--warn` | `#A67A2E` | Warning text |
| `--danger` | `#8B2420` | Danger / error text |

**Typography** — load via Google Fonts in `frontend/index.html`:
- Display / headings: **Fraunces** (variable, opsz axis), weights 400–500, letter-spacing −0.01 to −0.02em
- UI / body: **Inter Tight**, weights 400 / 500 / 600 only
- Data / metadata: **JetBrains Mono**, 400 / 500, tabular numerals (`font-feature-settings: "zero"`)
- Size scale (px): `11 · 12 · 13 · 14 · 16 · 20 · 22 · 28 · 32 · 44 · 56+`
- Line-height: `1.3` data · `1.5` UI · `1.55–1.65` reading

**Spacing** — 4px base: `4 · 8 · 12 · 16 · 24 · 32 · 48 · 64 · 96`

**Radius** — `2px` inputs · `4px` buttons, tags · `6px` cards, dialogs · `999px` for avatars only (never for general "pill" buttons)

**Elevation** — hairline borders preferred over shadows. One shadow token only: `0 1px 2px rgba(10, 10, 10, 0.04)` on popovers / dialogs.

### Component library

- **Primitives:** `@radix-ui/react-*` for Dialog, DropdownMenu, Popover, Tooltip, Tabs, Toast. Install packages **only** when a component needs them — do not preemptively add.
- **Styling:** plain CSS + CSS variables in `frontend/src/styles.css`. **No Tailwind, no CSS-in-JS, no shadcn.**
- **Don't reinvent rule:** before creating a component, grep `frontend/src/components/` and `frontend/src/styles.css`. Extend what exists; do not create a parallel version.

### Don't-do list

1. No purple, indigo, or violet. No gradients. No glow or blur effects.
2. No emoji in UI copy, headers, button labels, or status strings.
3. No icons unless they carry information the label cannot. No decorative icons.
4. No rounded-full pill buttons for actions — pills are for tags / status only.
5. No skeleton shimmer for sub-500ms loads — plain "Loading…" text is fine.
6. No drop-shadow + border on the same element — pick one (prefer border).
7. No uppercase tracking on everything; reserve small-caps mono style for tiny metadata (≤12px) only.
8. No stock illustrations, no dashed rainbow borders, no "AI" glow halos.
9. No more than one accent hue on screen at a time.
10. No hero sections or marketing patterns — this is an internal tool.
11. Color must encode meaning, never decoration.
12. No oversized rounded cards with heavy shadows — Linear-style cards are barely cards.
13. No system-font fallback shipping as final design — wait for the loaded font (`font-display: swap` with conscious FOUT is acceptable).

### Reference targets

Linear · Stripe docs · Are.na · Bear / iA Writer · Nature / Science article pages.

## What's Explicitly Out of Scope

- Separate vector databases (use pgvector only)
- GraphRAG / knowledge graphs
- Custom ML models
- Microservices architecture
- Faceted filter systems
