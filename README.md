# Phosphor

An AI tool for research labs that surfaces high-value research opportunities by matching a lab's capabilities against emerging directions from scientific literature.

## What It Does

Phosphor maintains a compressed, continuously-updated representation of what your lab can do—equipment, techniques, expertise, past experiments—and matches it against actionable opportunities extracted from PubMed and Semantic Scholar. It ranks opportunities by feasibility (do you have the resources?) and alignment (does it fit your focus?), then generates protocols grounded in your actual capabilities.

## Architecture

**Two inputs, one output:**

- **Lab State** — A living summary distilled from experiment logs, documents, and feedback. Compressed to ~2K tokens while retaining enough fidelity for LLM reasoning.
- **Research Directions** — Concrete opportunities extracted from literature. Not vague "further research needed"—actionable directions with identifiable resource requirements.
- **The Match** — Opportunities ranked by feasibility and alignment, with gap analysis and protocol generation.

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

## Project Structure

```
/backend     # Python FastAPI application
/frontend    # React TypeScript application
/evals       # Evaluation harnesses for LLM prompts
```

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

## Security

Lab data is proprietary and often pre-publication. Security is the highest priority:

- All API endpoints require authentication
- Row-level security for tenant isolation
- Encryption at rest and in transit
- Audit logging on all write operations

## License

Proprietary. All rights reserved.
