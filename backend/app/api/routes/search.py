"""Search endpoints — Phase 4.4."""

from fastapi import APIRouter, Query

from app.api.deps import CurrentLab, CurrentUser, DbSession
from app.core.config import get_settings
from app.schemas.search import SearchResponse
from app.services.search import hybrid_search

router = APIRouter()


@router.get(
    "/{lab_id}/search",
    response_model=SearchResponse,
)
async def search_past_work(
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
    q: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(20, ge=1, le=100),
) -> SearchResponse:
    """Hybrid keyword + embedding search over signals and papers."""
    hits = await hybrid_search(
        session=session,
        settings=get_settings(),
        lab_id=lab.id,
        query=q,
        limit=limit,
    )
    return SearchResponse(query=q, hits=hits, total=len(hits))
