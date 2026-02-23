"""Signal ingestion endpoints."""

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import CurrentLab, CurrentUser, DbSession
from app.models.signal import RawSignal
from app.schemas.signal import SignalCreate, SignalListResponse, SignalResponse

router = APIRouter()


@router.post(
    "/{lab_id}/signals",
    response_model=SignalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_signal(
    signal_in: SignalCreate,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> RawSignal:
    """Ingest a new signal for distillation.

    Signals are raw inputs (experiments, documents, corrections) that will
    be processed by the distillation engine to update the lab state.
    """
    # Validate content based on signal type
    try:
        signal_in.get_typed_content()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid content for signal type: {e}",
        )

    signal = RawSignal(
        lab_id=lab.id,
        signal_type=signal_in.signal_type,
        content=signal_in.content,
        created_by=user.user_id,
    )
    session.add(signal)
    await session.flush()

    # Trigger async distillation (imported here to avoid circular imports)
    # In production, this would queue a Celery task
    # background_tasks.add_task(trigger_distillation, lab.id)

    return signal


@router.get(
    "/{lab_id}/signals",
    response_model=SignalListResponse,
)
async def list_signals(
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
    processed: bool | None = None,
    signal_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SignalListResponse:
    """List signals for a lab with optional filters."""
    query = select(RawSignal).where(RawSignal.lab_id == lab.id)

    if processed is not None:
        query = query.where(RawSignal.processed == processed)

    if signal_type is not None:
        query = query.where(RawSignal.signal_type == signal_type)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    query = query.order_by(RawSignal.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    signals = result.scalars().all()

    return SignalListResponse(
        signals=[SignalResponse.model_validate(s) for s in signals],
        total=total,
    )


@router.get(
    "/{lab_id}/signals/{signal_id}",
    response_model=SignalResponse,
)
async def get_signal(
    signal_id: uuid.UUID,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
) -> RawSignal:
    """Get a specific signal by ID."""
    result = await session.execute(
        select(RawSignal).where(
            RawSignal.id == signal_id,
            RawSignal.lab_id == lab.id,
        )
    )
    signal = result.scalar_one_or_none()

    if signal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signal not found",
        )

    return signal
