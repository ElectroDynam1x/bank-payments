"""Журнал аудита: фиксирует, кто и что изменил."""
from sqlalchemy.orm import Session

from .models import AuditEvent, User


def record(db: Session, user: User | str, action: str, entity: str,
           entity_id: int | None = None, details: str = "") -> None:
    username = user if isinstance(user, str) else user.username
    db.add(AuditEvent(username=username, action=action, entity=entity,
                      entity_id=entity_id, details=details))
