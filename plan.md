# Phosphor — Implementation Plan

## Overview

This plan follows the two-input/one-output architecture with the lab state compressor as the central system. Development proceeds in five phases, each producing a working increment with its own eval harness.

**Security is the highest priority.** Lab data is proprietary and often pre-publication. Security is not a phase — it's a constraint on every phase. Every feature ships with its security controls or it doesn't ship.

---

## Cross-Cutting: Security Requirements

These requirements apply to ALL phases. No feature is complete until its security controls are implemented and tested.

### Authentication & Authorization
- Clerk integration from day one (not Phase 5)
- All API endpoints require authentication
- Lab-level tenant isolation enforced at database query level (row-level security)
- Role-based access control: admin, researcher, viewer
- API keys for programmatic access with scoped permissions

### Data Protection
- Encryption at rest: PostgreSQL with encrypted storage, S3/GCS server-side encryption
- Encryption in transit: TLS 1.3 everywhere, no exceptions
- Secrets management: environment variables via secret manager (not .env files in production)
- PII handling: lab member names, emails treated as sensitive

### Audit & Monitoring
- Audit log for all write operations: who, what, when, from where
- Failed auth attempts logged and alerted
- Anomaly detection on API usage patterns
- Log retention policy compliant with research data requirements

### Secure Development
- Dependency scanning in CI (Dependabot, Snyk)
- SAST scanning on every PR
- No secrets in code or logs
- Input validation on all endpoints (Pydantic strict mode)
- Rate limiting on all public endpoints
- CORS locked to known origins

### Infrastructure Security
- Network isolation: database not publicly accessible
- Principle of least privilege for service accounts
- Regular security reviews at phase boundaries
- Incident response plan before production launch

---

## Phase 1: Lab State Compressor + Eval Harness

**Goal:** Build the core distillation system that compresses lab capabilities into a minimal, high-fidelity representation an LLM can reason over.

### 1.1 Project Foundation
- Initialize monorepo structure: `/backend`, `/frontend`, `/evals`
- Set up Python 3.12 + Poetry, FastAPI skeleton, pytest with coverage enforcement
- PostgreSQL 16 + pgvector schema: `labs`, `lab_states`, `raw_signals`, `distillation_runs`
- **Row-level security policies on all tables from day one**
- Celery + Redis for async distillation jobs
- LiteLLM integration with provider config
- Docker Compose for local dev
- CI pipeline: lint (ruff), type check (mypy), test gates, **SAST scanning, dependency audit**

### 1.1.1 Security Foundation (ships with 1.1)
- Clerk integration: lab-level multi-tenancy, JWT validation middleware
- All endpoints authenticated by default (explicit opt-out for health checks only)
- Pydantic models with strict validation on all inputs
- Audit logging infrastructure: `audit_logs` table, write middleware
- Secrets management pattern established (no hardcoded secrets)
- HTTPS-only configuration, CORS policy

### 1.2 Lab State Data Model
Define the compressed representation schema:
```
- equipment: list of instruments with capabilities
- techniques: methods the lab can perform
- expertise: domain knowledge areas with confidence levels
- organisms: model systems available
- reagents: key materials on hand
- experimental_history: compressed outcomes (worked/failed/why)
- resource_constraints: budget, time, personnel limits
```
Target: single JSON blob that fits in ~2K tokens while remaining LLM-interpretable.

### 1.3 Distillation Engine
- **Signal ingestion API:** Accept raw signals (experiment logs, document chunks, user corrections) tagged by type
- **Incremental distillation:** On each new signal, re-run compression against current state
- **Compression prompts:** Design prompts that merge new information into existing state, prune redundancy, and maintain fidelity
- **Versioned states:** Every distillation produces a new immutable lab state version with diff tracking

### 1.4 Distillation Eval Harness
- **Synthetic lab fixtures:** Create 3-5 fake labs with known ground-truth capabilities
- **Signal injection tests:** Feed signals, verify state updates correctly
- **Fidelity tests:** Given a lab state, can an LLM answer factual questions about lab capabilities with high accuracy?
- **Compression ratio tracking:** Monitor token count vs. signal volume over time
- **Regression detection:** Alert if new prompts degrade eval scores

### 1.5 Deliverables
- `POST /labs/{lab_id}/signals` — ingest raw signal
- `GET /labs/{lab_id}/state` — retrieve current compressed state
- `GET /labs/{lab_id}/state/history` — audit trail of state versions
- Eval suite: `pytest evals/distillation/` with CI integration
- Staging deployment on Cloud Run

---

## Phase 2: Opportunity Extraction Pipeline

**Goal:** Pull research directions from literature APIs and extract concrete, actionable opportunities.

### 2.1 Literature Ingestion
- PubMed API client: query by MeSH terms, author affiliations, journal sets
- Semantic Scholar API client: query by field of study, citation graph expansion
- Rate limiting, caching, deduplication by DOI/PMID
- Store raw abstracts + metadata in `papers` table

### 2.2 Opportunity Extraction
- **Extraction prompts:** Identify future directions, emerging techniques, open problems from abstracts
- **Quality filter:** Reject vague "more research needed" — require concrete resource requirements
- **Structured output:** Each opportunity includes:
  - description (what to do)
  - required_equipment
  - required_techniques
  - required_expertise
  - estimated_complexity (low/medium/high)
  - source_papers (citations)
- Store in `opportunities` table with embeddings (pgvector)

### 2.3 Opportunity Extraction Eval Harness
- **Annotated abstract set:** 100+ abstracts with human-labeled opportunities (or "none")
- **Precision/recall metrics:** Does the system extract real opportunities? Does it miss any?
- **Quality scoring:** Rate extracted opportunities on concreteness, actionability
- **Field coverage tests:** Ensure extraction works across biology, chemistry, physics domains

### 2.4 Scheduled Ingestion
- Celery beat job: daily/weekly literature scan based on lab's configured field interests
- Background extraction pipeline
- Notification on new high-relevance opportunities

### 2.5 Deliverables
- `POST /labs/{lab_id}/literature/scan` — trigger manual scan
- `GET /labs/{lab_id}/opportunities` — list extracted opportunities
- Eval suite: `pytest evals/extraction/`
- Staging deployment

---

## Phase 3: Matching Engine + Protocol Generation

**Goal:** Rank opportunities against lab state and generate actionable protocols.

### 3.1 Matching Algorithm
- **Feasibility scoring:** Compare opportunity requirements against lab state capabilities
  - Equipment match (have it / can acquire / cannot acquire)
  - Technique match (practiced / learnable / outside expertise)
  - Expertise alignment (strong / adjacent / gap)
- **Alignment scoring:** Semantic similarity between opportunity and lab's research focus (embedding-based)
- **Composite ranking:** Weighted combination, configurable per lab

### 3.2 Gap Analysis
- For each opportunity, identify:
  - Missing equipment
  - Skill gaps requiring training or collaboration
  - Reagent/organism acquisition needs
- Estimate effort to close gaps

### 3.3 Protocol Generation
- Given: matched opportunity + lab state
- Generate: step-by-step experimental protocol grounded in lab's actual resources
- Flag: where protocol relies on resources the lab doesn't have
- Output: structured protocol with phases, materials, expected outcomes

### 3.4 Matching Eval Harness
- **Synthetic scenarios:** Known lab state + known opportunities with human-annotated rankings
- **Ranking correlation:** Spearman/Kendall correlation between system and human rankings
- **Protocol quality:** Domain expert review of generated protocols (manual, sampled)

### 3.5 Deliverables
- `GET /labs/{lab_id}/opportunities/ranked` — opportunities ranked by match score
- `GET /labs/{lab_id}/opportunities/{opp_id}/gaps` — gap analysis
- `POST /labs/{lab_id}/opportunities/{opp_id}/protocol` — generate protocol
- Eval suite: `pytest evals/matching/`
- Staging deployment

---

## Phase 4: Input Surfaces + Feedback Loop

**Goal:** Build low-friction interfaces that feed signals into the lab state compressor.

**Critical constraint:** The compressor is worthless if starved of data. If data entry takes more than 30 seconds, adoption will fail. Every design decision optimizes for minimal friction.

### 4.1 Experiment Entry — Designed for Speed
- **Minimal required fields:** Date auto-filled, outcome (3 buttons: worked/partial/failed), free-text notes
- **Smart defaults:** Pre-populate technique/equipment based on recent entries
- **Quick-log mode:** Single-field entry that LLM parses into structured format
- **Bulk entry:** Paste spreadsheet data, import from CSV
- **Voice notes:** Audio upload → transcription → structured signal (stretch goal)
- **Templates:** Lab-specific templates for common experiment types (PCR, Western, transfection, etc.)
- Parse to signal format, feed to distillation engine

### 4.2 Document Ingestion — Zero-Effort Capture
- **Drag-and-drop upload** for PDFs, protocols, papers
- **Bulk upload:** Folder upload, zip archives
- **Cloud integrations:** Google Drive, Dropbox, Box folder sync (auto-ingest new files)
- **ELN integrations:** Benchling, LabArchives, Notion API connectors (where available)
- **Email forwarding:** Forward papers/protocols to lab-specific email address for ingestion
- Unstructured.io parsing to extract text chunks
- Classify chunks by type (methods, results, equipment mentions)
- Feed classified chunks as signals to distillation engine
- **Progress visibility:** Show what was extracted, let user correct misclassifications

### 4.3 User Feedback Loop — One-Click Corrections
- Accept/reject buttons on suggested opportunities (single click)
- **Inline corrections:** Click on lab state item → edit directly
- Quick-add: "We have X" / "We don't have Y" buttons
- Feedback signals feed back into distillation engine
- Track feedback for prompt refinement
- **Feedback impact visibility:** Show user how their correction changed the lab state

### 4.4 Search Over Past Work
- Hybrid search: keyword + embedding similarity over raw document chunks
- Filter by date, experiment type, outcome
- Results augmented with relevant lab state context

### 4.5 Mobile-Friendly Capture
- Responsive design for core input flows (experiment logging, document photo upload)
- Camera capture: photo of notebook page → OCR → signal
- Works on phone browser, no app install required

### 4.6 Adoption Metrics
- Track time-to-complete for each input type
- Monitor drop-off rates on forms
- A/B test form variations
- Alert if input volume drops (compressor starvation warning)

### 4.7 Deliverables
- `POST /labs/{lab_id}/experiments` — structured experiment entry
- `POST /labs/{lab_id}/experiments/quick` — single-field quick log
- `POST /labs/{lab_id}/experiments/bulk` — bulk import
- `POST /labs/{lab_id}/documents` — document upload
- `POST /labs/{lab_id}/documents/bulk` — bulk document upload
- `POST /labs/{lab_id}/feedback` — user corrections
- `GET /labs/{lab_id}/search` — search past work
- Cloud connector configurations
- Staging deployment

---

## Phase 5: Frontend + Polish

**Goal:** Build the user-facing application. (Auth already implemented in Phase 1.)

### 5.1 Core UI
- Dashboard: lab state summary, recent opportunities, pending actions
- Experiment entry forms with validation
- Document upload with progress
- Opportunity browser with filters and ranking explanation
- Protocol viewer with export (PDF, Markdown)
- Lab state editor for manual corrections

### 5.2 Notifications
- Email/in-app alerts for new high-match opportunities
- Weekly digest of literature scans

### 5.3 Deliverables
- React 18 + TypeScript + Vite app
- Responsive design for desktop (lab use case)
- Deployed frontend on staging

---

## Infrastructure Milestones

| Milestone | Phase | Criteria |
|-----------|-------|----------|
| Local dev environment | 1.1 | `docker-compose up` runs full stack |
| **Security foundation** | 1.1.1 | Auth, RLS, audit logging, input validation operational |
| CI/CD pipeline | 1.1 | PRs blocked on lint + test + 80% coverage + **SAST + dependency scan** |
| Staging deployment | 1.5 | Backend on Cloud Run, DB on managed PostgreSQL, **TLS enforced** |
| Eval harness framework | 1.4 | Evals run in CI, results logged |
| **Security review gate** | Each phase | Phase not complete until security review passes |
| Production readiness | 5.3 | Monitoring, backups, rate limiting, **incident response plan**, **penetration test passed** |

---

## Eval Strategy Summary

Each core component has dedicated evals:

1. **Distillation evals** — Compression ratio, fidelity tests, regression detection
2. **Extraction evals** — Precision/recall on annotated abstracts, quality scoring
3. **Matching evals** — Ranking correlation with human judgments

Evals run on every PR. Prompt changes require eval approval before merge.

---

## Dependency Graph

```
┌─────────────────────────────────────────────────────────────┐
│              SECURITY (cross-cutting, every phase)          │
└─────────────────────────────────────────────────────────────┘
                              │
Phase 1: Lab State Compressor + Security Foundation
    ↓
Phase 2: Opportunity Extraction ←──┐
    ↓                              │
Phase 3: Matching Engine ──────────┘
    ↓
Phase 4: Input Surfaces (can partially parallel with Phase 2-3)
    ↓                    ↑
    │         [Low-friction design is critical here]
    ↓
Phase 5: Frontend (can partially parallel with Phase 4)
```

---

## Risk Mitigations

| Risk | Mitigation |
|------|------------|
| **Data breach / unauthorized access** | Defense in depth: auth + RLS + encryption + audit logs; regular security reviews; penetration testing before launch |
| **Cross-tenant data leakage** | Row-level security enforced at DB level; tenant isolation tests in CI; query-level tenant checks |
| **Credential/secret exposure** | No secrets in code; secret manager for all credentials; automated secret scanning in CI |
| **Input friction kills adoption** | 30-second target for experiment logging; adoption metrics dashboard; continuous UX testing with researchers |
| **Compressor starved of data** | Multiple low-friction input paths; cloud integrations; monitor input volume; alert on drops |
| Compression loses critical detail | Fidelity evals with factual QA; human review checkpoints |
| Literature APIs rate-limited | Aggressive caching; fallback to Semantic Scholar if PubMed constrained |
| Opportunity extraction too noisy | Strict quality filters; user feedback loop to tune |
| Match rankings don't match intuition | Expose scoring factors; let users override weights |
| Eval sets don't cover edge cases | Continuously expand eval sets from production feedback |

---

## What's Explicitly Out of Scope

Per project brief:
- Separate vector databases (using pgvector only)
- GraphRAG / knowledge graphs
- Custom ML models (LLM-based only)
- Microservices architecture
- Hybrid search complexity
- Faceted filter systems
- Multimodal parsing of complex formats

---

## Summary: Two Non-Negotiable Constraints

1. **Security is the highest priority.** No feature ships without its security controls. Every phase includes security review. A breach would compromise proprietary research data — this is unacceptable.

2. **Input surfaces must be low-friction.** The compressor is the core system, but it's worthless without data. If researchers won't use the input tools, the product fails. Target: 30 seconds to log an experiment.
