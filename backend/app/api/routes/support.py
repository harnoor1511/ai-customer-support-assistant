"""
HTTP routes for the support-assistant feature.

Routes stay thin: validate/deserialize via Pydantic (handled by FastAPI),
delegate to the service layer, and translate service errors into HTTP
responses. No LLM or prompt logic lives here.
"""
import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.core.config import get_settings
from app.schemas.support import (
    BatchMessageItem,
    BatchSupportRequest,
    BatchSupportResponse,
    SupportRequest,
    SupportResponse,
)
from app.services.llm_service import get_llm_client
from app.services.support_service import SupportService, SupportServiceError

router = APIRouter(prefix="/api/support", tags=["support"])

MAX_BATCH_FILE_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB is plenty for a few hundred rows


def get_support_service() -> SupportService:
    """Dependency provider — easy to swap/mock the LLM client in tests."""
    settings = get_settings()
    return SupportService(
        llm_client=get_llm_client(settings),
        kb_similarity_threshold=settings.kb_similarity_threshold,
    )


@router.post("/triage", response_model=SupportResponse)
async def triage_message(
    payload: SupportRequest,
    service: SupportService = Depends(get_support_service),
) -> SupportResponse:
    """Accept a raw customer message and return a structured triage response."""
    try:
        return await service.triage_message(payload)
    except SupportServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/triage-batch", response_model=BatchSupportResponse)
async def triage_batch(
    payload: BatchSupportRequest,
    service: SupportService = Depends(get_support_service),
) -> BatchSupportResponse:
    """Triage a batch of messages (JSON body). Never raises per-item — every
    row gets either a real result or a safe fallback in the response body.
    """
    return await service.triage_batch(payload.messages)


@router.post("/triage-batch-file", response_model=BatchSupportResponse)
async def triage_batch_file(
    file: UploadFile,
    service: SupportService = Depends(get_support_service),
) -> BatchSupportResponse:
    """Upload a dataset file (.csv with an 'id' and 'message' column, or
    .json as a list of {id, message} objects / list of strings) and triage
    every row in one batch call.
    """
    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_BATCH_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 2MB).")

    filename = (file.filename or "").lower()
    text = raw_bytes.decode("utf-8-sig", errors="replace")

    items: list[BatchMessageItem] = []

    if filename.endswith(".json"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON file: {exc}") from exc

        if not isinstance(data, list):
            raise HTTPException(status_code=400, detail="JSON file must contain a list.")

        for idx, row in enumerate(data):
            if isinstance(row, str):
                items.append(BatchMessageItem(id=str(idx + 1), message=row))
            elif isinstance(row, dict) and "message" in row:
                items.append(
                    BatchMessageItem(id=str(row.get("id", idx + 1)), message=str(row["message"]))
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Row {idx + 1} must be a string or an object with a 'message' field.",
                )

    elif filename.endswith(".csv"):
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None or "message" not in [f.strip().lower() for f in reader.fieldnames]:
            raise HTTPException(
                status_code=400,
                detail="CSV must have a 'message' column (an 'id' column is optional).",
            )
        # Normalize header lookups case-insensitively.
        field_map = {f.strip().lower(): f for f in reader.fieldnames}
        for idx, row in enumerate(reader):
            message = (row.get(field_map["message"]) or "").strip()
            if not message:
                continue  # skip blank rows rather than failing the whole upload
            row_id = row.get(field_map.get("id", ""), "") or str(idx + 1)
            items.append(BatchMessageItem(id=str(row_id), message=message))
    else:
        raise HTTPException(status_code=400, detail="Only .csv and .json files are supported.")

    if not items:
        raise HTTPException(status_code=400, detail="No valid message rows found in the file.")
    if len(items) > 200:
        raise HTTPException(status_code=400, detail="Max 200 messages per batch upload.")

    return await service.triage_batch(items)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
