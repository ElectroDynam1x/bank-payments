from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..models import Account, Payment, User
from ..schemas import AccountIn, AccountOut, AccountUpdate
from ..security import get_current_user, require_roles

router = APIRouter(prefix="/accounts", tags=["Счета"])


def get_or_404(db: Session, account_id: int) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Счёт не найден")
    return account


@router.get("", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Account).order_by(Account.id).all()


@router.get("/{account_id}", response_model=AccountOut)
def get_account(account_id: int, db: Session = Depends(get_db),
                _: User = Depends(get_current_user)):
    return get_or_404(db, account_id)


@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_account(data: AccountIn, db: Session = Depends(get_db),
                   user: User = Depends(require_roles("admin", "operator"))):
    if db.query(Account).filter(Account.number == data.number).first():
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Счёт с таким номером уже существует")
    account = Account(**data.model_dump())
    db.add(account)
    db.flush()
    audit.record(db, user, "create", "account", account.id, account.number)
    db.commit()
    return account


@router.put("/{account_id}", response_model=AccountOut)
def update_account(account_id: int, data: AccountUpdate, db: Session = Depends(get_db),
                   user: User = Depends(require_roles("admin", "operator"))):
    account = get_or_404(db, account_id)
    changes = data.model_dump(exclude_none=True)
    for field, value in changes.items():
        setattr(account, field, value)
    audit.record(db, user, "update", "account", account.id, ", ".join(sorted(changes)))
    db.commit()
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: int, db: Session = Depends(get_db),
                   user: User = Depends(require_roles("admin"))):
    account = get_or_404(db, account_id)
    if db.query(Payment).filter(Payment.account_id == account_id).first():
        raise HTTPException(status.HTTP_409_CONFLICT,
                            detail="По счёту есть платёжные поручения, удаление запрещено")
    db.delete(account)
    audit.record(db, user, "delete", "account", account_id, account.number)
    db.commit()
