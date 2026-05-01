<p align="center">
  <img src="docs/banner.png" alt="Phosphor" width="100%" />
</p>

---

Frontier models can now reason about scientific work at the scale of an entire field. What they can't do — yet — is know what's in your freezer, which assays your postdocs are trained on, or which failures your lab has already logged. Phosphor closes that gap.

---

## What It Does

Phosphor distills a research lab — equipment, techniques, expertise, experimental history — into a compressed representation a model can hold in a single prompt. With that primitive in place, agents can act on the lab:

- **Strengthen project plans.** Read an in-flight plan alongside the lab state, surface gaps, and suggest experiments that shore up the strongest claims.
- **Address reviewer comments.** Draft targeted responses to peer-review feedback, grounded in what the lab has actually done and what it can realistically run.
- **Surface research directions.** Scan PubMed and Semantic Scholar for concrete opportunities, score each against the lab state for feasibility, and draft protocols using the lab's own methods.

The hard part is the representation. The agents are the easy part — and more follow once a lab is readable.

---

## Architecture

**Compressed lab state (the primitive).** A continuously-updated ~2K-token summary distilled from experiment logs, documents, protocols, and feedback. Validated by factual-QA evals: a frontier model must be able to answer ground-truth questions about the lab from this representation alone.

**Agents (the layer above).** Each agent reads the compressed lab state plus its own task input — a project plan, a set of reviewer comments, a literature feed — and produces output grounded in what the lab can actually do.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.12, FastAPI, Celery + Redis |
| Database | PostgreSQL 16 + pgvector |
| Frontend | React 18 + TypeScript + Vite |
| Auth | Clerk (lab-level multi-tenancy) |
| LLM | LiteLLM (provider-agnostic) |
| Document Parsing | Unstructured.io |
| Storage | S3/GCS |
| Infrastructure | Docker, Cloud Run or ECS |

---

## Project Structure

```
/backend     # Python FastAPI application
/frontend    # React TypeScript application
/evals       # Evaluation harnesses for LLM prompts
```

---

## Development

Requirements:
- Python 3.12+
- Node.js 18+
- Docker & Docker Compose
- PostgreSQL 16 with pgvector extension

```bash
# Start local development environment
docker-compose up

# Run backend tests
cd backend && pytest

# Run frontend
cd frontend && npm run dev
```
---

## Security

Lab data is proprietary and often pre-publication. Security is the highest priority:

- All API endpoints require authentication
- Row-level security for tenant isolation
- Encryption at rest and in transit
- Audit logging on all write operations

---

## License

MIT License. See [LICENSE](LICENSE) for details.
