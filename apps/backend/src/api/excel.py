from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.errors import ApiError
from src.middleware.auth import AuthSession, require_session
from src.services import excel_ingestion_service

router = APIRouter()

MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024


class ReingestData(BaseModel):
    snapshotId: str
    itemCount: int
    ingestedAt: str
    isNoop: bool


class ReingestResponse(BaseModel):
    ok: bool = True
    data: ReingestData


@router.post("/reingest")
async def reingest_route(
    file: UploadFile = File(...),
    session: AuthSession = Depends(require_session),
    db: AsyncSession = Depends(get_db),
) -> ReingestResponse:
    if file.filename is None or not file.filename.lower().endswith(".xlsx"):
        raise ApiError(400, "BAD_REQUEST", "Only .xlsx files are accepted", field="file")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise ApiError(400, "BAD_REQUEST", "File is empty", field="file")
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise ApiError(413, "PAYLOAD_TOO_LARGE", "File exceeds the 2MB limit", field="file")

    snapshot, is_noop = await excel_ingestion_service.ingest(
        db, session.sme_id, file_bytes, file.filename
    )

    return ReingestResponse(
        data=ReingestData(
            snapshotId=snapshot.id,
            itemCount=snapshot.item_count,
            ingestedAt=snapshot.ingested_at.isoformat(),
            isNoop=is_noop,
        )
    )
