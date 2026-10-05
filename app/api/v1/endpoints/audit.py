from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db_session
from app.services.audit_service import AuditService
from app.schemas.transaction import AuditReportResponse

router = APIRouter()


@router.get(
    "/audit",
    response_model=AuditReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Cryptographic audit verifying ledger chain continuity and content hashes",
)
async def audit_ledger_chain(
    db: AsyncSession = Depends(get_db_session),
):
    """
    Traverses the historical transaction chain, verifying SHA-256 integrity block-by-block.
    Detects any malicious alterations, deleted rows, or broken hash links.
    """
    report = await AuditService.verify_ledger_integrity(db)
    return report
