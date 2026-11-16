import socket

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import AuditEvent, User
from ..schemas import AuditOut
from ..security import require_roles

router = APIRouter(tags=["Служебные"])


@router.get("/health/live")
def live():
    """Проверка живости: процесс отвечает на запросы."""
    return {"status": "ok"}


@router.get("/health/ready")
def ready(db: Session = Depends(get_db)):
    """Проверка готовности: есть соединение с базой данных."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="База данных недоступна") from None
    return {"status": "ready"}


@router.get("/version")
def version():
    return {
        "version": settings.app_version,
        "commit": settings.git_commit,
        "env": settings.app_env,
        "instance": socket.gethostname(),
    }


@router.get("/audit", response_model=list[AuditOut])
def audit_log(limit: int = 200, db: Session = Depends(get_db),
              _: User = Depends(require_roles("admin", "auditor"))):
    limit = max(1, min(limit, 1000))
    return db.query(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit).all()
