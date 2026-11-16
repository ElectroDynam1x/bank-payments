"""Схемы запросов и ответов API."""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    full_name: str
    role: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    username: str
    full_name: str
    role: str


class AccountIn(BaseModel):
    number: str = Field(pattern=r"^\d{20}$", description="Номер счёта, 20 цифр")
    owner_name: str = Field(min_length=2, max_length=200)
    currency: str = Field(default="RUB", pattern=r"^[A-Z]{3}$")
    balance: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=18, decimal_places=2)


class AccountUpdate(BaseModel):
    owner_name: str | None = Field(default=None, min_length=2, max_length=200)
    status: str | None = Field(default=None, pattern=r"^(open|closed)$")


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    number: str
    owner_name: str
    currency: str
    balance: Decimal
    status: str
    created_at: datetime


class PaymentIn(BaseModel):
    account_id: int
    beneficiary_name: str = Field(min_length=2, max_length=200)
    beneficiary_account: str = Field(pattern=r"^\d{20}$")
    beneficiary_bik: str = Field(pattern=r"^\d{9}$")
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    purpose: str = Field(min_length=3, max_length=210)


class PaymentUpdate(BaseModel):
    beneficiary_name: str | None = Field(default=None, min_length=2, max_length=200)
    beneficiary_account: str | None = Field(default=None, pattern=r"^\d{20}$")
    beneficiary_bik: str | None = Field(default=None, pattern=r"^\d{9}$")
    amount: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    purpose: str | None = Field(default=None, min_length=3, max_length=210)


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    account_id: int
    account_number: str
    beneficiary_name: str
    beneficiary_account: str
    beneficiary_bik: str
    amount: Decimal
    purpose: str
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ts: datetime
    username: str
    action: str
    entity: str
    entity_id: int | None
    details: str
