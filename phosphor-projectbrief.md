# Phosphor — Project Brief

## What it is

An AI tool for research labs. It maintains a compressed, continuously-updated representation of a lab's capabilities and matches it against emerging research directions from the literature to surface high-value opportunities.

## Core architecture

The system has two inputs and one output.

**Input 1 — Lab state.** A living summary of what a lab can do: equipment, techniques, expertise, organisms, reagents, past experimental results (what worked, what failed, and why), and resource constraints. This representation is continuously distilled from multiple signal types — structured experiment logs, uploaded documents, and user feedback. The key design constraint is that this representation must compress to as few tokens as possible while retaining enough fidelity for an LLM to reason over it accurately. Every new signal triggers a re-distillation of the lab state.

**Input 2 — Adjacent research directions.** Sourced from PubMed and Semantic Scholar APIs. The system extracts actionable future directions, emerging techniques, and open problems from recent literature in the lab's field and adjacent fields. Not vague "further research is needed" — concrete opportunities with identifiable resource requirements.

**Output — The match.** Given the lab state and the research directions, the system ranks opportunities by feasibility (does this lab have the equipment, techniques, and expertise?) and alignment (does this fit their research focus?). On request, it generates protocols grounded in the lab's actual capabilities, flagging resource gaps.

## Everything else is plumbing

- Experiment entry (structured forms, templates) → feeds the lab state compressor
- Document ingestion (PDFs, protocols, papers) → feeds the lab state compressor
- User feedback (accepted/rejected suggestions, corrections) → feeds the lab state compressor
- Reasoning/suggestions about experimental design → reads from the lab state
- Protocol generation → reads from the lab state + a matched opportunity
- Search over past work → reads from the lab state + raw document chunks

## Key design problems to solve

1. **The distillation strategy.** How do you compress a lab's full history into a compact representation without losing critical detail? How do you validate that compression quality stays high as more data comes in? This is the core technical challenge.

2. **Opportunity extraction quality.** Most abstracts don't contain actionable opportunities. The filtering/quality problem for Input 2 is hard and needs its own eval.

3. **Match quality evaluation.** The match output is the product. The eval harness should primarily test: given a known lab state and known opportunities, does the system rank them correctly?

4. **Input friction.** The compressor is worthless if it's starved of data. Experiment entry and document upload must be low-friction enough that researchers actually use them. This means: minimal required fields, smart defaults, bulk operations, mobile-friendly capture, integrations with tools researchers already use (ELNs, Google Drive, Dropbox). If it takes more than 30 seconds to log an experiment, adoption will fail.

## Non-negotiables

**Security is the highest priority.** Lab data is proprietary and often pre-publication. A breach could compromise years of research, competitive advantage, or IP. Every design decision must assume adversarial conditions. This means: defense in depth, principle of least privilege, encryption at rest and in transit, audit logging, regular security reviews, and no shortcuts on auth/authz. Security is not a phase — it's a constraint on every phase.

## Tech stack (decided)

- Backend: Python 3.12, FastAPI, Celery + Redis, PostgreSQL 16 + pgvector
- Frontend: React 18 + TypeScript + Vite
- Auth: Clerk (lab-level multi-tenancy)
- LLM: LiteLLM (provider-agnostic)
- Document parsing: Unstructured.io
- File storage: S3/GCS
- Infra: Docker, Cloud Run or ECS

## Development standards (decided)

- TDD, 80% coverage minimum, CI with lint + test gates
- Conventional commits, feature branches, PR to main
- Eval harness for all LLM-facing prompts — prompt engineering is a first-class work stream
- Deploy to staging from day one, not as a final phase

## What to skip

Separate vector DBs, GraphRAG, knowledge graphs, custom ML models, microservices, hybrid search, faceted filters, multimodal parsing of nightmare formats. Keep it simple.

## What I need from you

A phased implementation plan organized around the two-input/one-output architecture. The lab state compressor is the central system — everything else either feeds it or reads from it. Prioritize: (1) the distillation/compression layer and its eval harness, (2) the opportunity extraction and matching pipeline, (3) the input surfaces (experiment entry, document ingestion) that feed the compressor. Frontend, polish, and secondary features come after the core loop works.