from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..models import User
from ..schemas import LoginIn, TokenOut, UserOut
from ..security import create_access_token, get_current_user, verify_password

router = APIRouter(prefix="/auth", tags=["Аутентификация"])


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()
    if user is None or not user.is_active or not verify_password(data.password, user.password_hash):
        audit.record(db, data.username, "login_failed", "user")
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
    audit.record(db, user, "login", "user", user.id)
    db.commit()
    return TokenOut(
        access_token=create_access_token(user),
        username=user.username,
        full_name=user.full_name,
        role=user.role,
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
