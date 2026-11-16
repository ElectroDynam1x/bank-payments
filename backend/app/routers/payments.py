from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from .. import audit
from ..db import get_db
from ..models import Account, Payment, User
from ..schemas import PaymentIn, PaymentOut, PaymentUpdate
from ..security import get_current_user, require_roles

router = APIRouter(prefix="/payments", tags=["Платёжные поручения"])


def to_out(payment: Payment) -> PaymentOut:
    return PaymentOut.model_validate(
        {**payment.__dict__, "account_number": payment.account.number}
    )


def get_or_404(db: Session, payment_id: int) -> Payment:
    query = db.query(Payment).options(joinedload(Payment.account)).filter(Payment.id == payment_id)
    payment = query.first()
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Платёжное поручение не найдено")
    return payment


def require_draft(payment: Payment) -> None:
    if payment.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT,
                            detail="Изменять можно только поручение в статусе «черновик»")


@router.get("", response_model=list[PaymentOut])
def list_payments(status_filter: str | None = Query(default=None, alias="status"),
                  db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    query = db.query(Payment).options(joinedload(Payment.account))
    if status_filter:
        query = query.filter(Payment.status == status_filter)
    return [to_out(p) for p in query.order_by(Payment.id.desc()).all()]


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment(payment_id: int, db: Session = Depends(get_db),
                _: User = Depends(get_current_user)):
    return to_out(get_or_404(db, payment_id))


@router.post("", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def create_payment(data: PaymentIn, db: Session = Depends(get_db),
                   user: User = Depends(require_roles("admin", "operator"))):
    account = db.get(Account, data.account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Счёт плательщика не найден")
    if account.status != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Счёт плательщика закрыт")
    payment = Payment(**data.model_dump(), created_by=user.username)
    db.add(payment)
    db.flush()
    audit.record(db, user, "create", "payment", payment.id, f"{data.amount} {account.currency}")
    db.commit()
    return to_out(get_or_404(db, payment.id))


@router.put("/{payment_id}", response_model=PaymentOut)
def update_payment(payment_id: int, data: PaymentUpdate, db: Session = Depends(get_db),
                   user: User = Depends(require_roles("admin", "operator"))):
    payment = get_or_404(db, payment_id)
    require_draft(payment)
    changes = data.model_dump(exclude_none=True)
    for field, value in changes.items():
        setattr(payment, field, value)
    audit.record(db, user, "update", "payment", payment.id, ", ".join(sorted(changes)))
    db.commit()
    return to_out(get_or_404(db, payment_id))


@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payment(payment_id: int, db: Session = Depends(get_db),
                   user: User = Depends(require_roles("admin", "operator"))):
    payment = get_or_404(db, payment_id)
    require_draft(payment)
    db.delete(payment)
    audit.record(db, user, "delete", "payment", payment_id)
    db.commit()


@router.post("/{payment_id}/execute", response_model=PaymentOut)
def execute_payment(payment_id: int, db: Session = Depends(get_db),
                    user: User = Depends(require_roles("admin"))):
    """Исполнение поручения контролёром: списание суммы со счёта плательщика."""
    payment = get_or_404(db, payment_id)
    require_draft(payment)
    if payment.created_by == user.username:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            detail="Поручение исполняет другой сотрудник (принцип двух лиц)")
    # блокировка строки счёта на время списания
    account = db.query(Account).filter(Account.id == payment.account_id).with_for_update().one()
    if account.status != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Счёт плательщика закрыт")
    if account.balance < payment.amount:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Недостаточно средств на счёте")
    account.balance -= payment.amount
    payment.status = "executed"
    audit.record(db, user, "execute", "payment", payment.id, f"{payment.amount} {account.currency}")
    db.commit()
    return to_out(get_or_404(db, payment_id))


@router.post("/{payment_id}/reject", response_model=PaymentOut)
def reject_payment(payment_id: int, db: Session = Depends(get_db),
                   user: User = Depends(require_roles("admin"))):
    payment = get_or_404(db, payment_id)
    require_draft(payment)
    payment.status = "rejected"
    audit.record(db, user, "reject", "payment", payment.id)
    db.commit()
    return to_out(get_or_404(db, payment_id))
