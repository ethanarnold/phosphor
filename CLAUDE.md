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

## What's Explicitly Out of Scope

- Separate vector databases (use pgvector only)
- GraphRAG / knowledge graphs
- Custom ML models
- Microservices architecture
- Faceted filter systems
