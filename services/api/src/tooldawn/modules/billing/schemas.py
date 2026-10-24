from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreditPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,49}$")
    credits: int = Field(gt=0, le=100_000_000)
    unit_amount: int = Field(ge=50, le=100_000_000)
    currency: Literal["usd", "eur", "cny"] = "usd"


class CheckoutInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    package_id: str = Field(max_length=50)
    request_key: UUID


class AdjustmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: int = Field(ge=-100_000_000, le=100_000_000)
    reason: str = Field(min_length=3, max_length=300)
    request_key: UUID


class CreditEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    amount: int
    balance_after: int
    kind: str
    reason: str
    created_at: datetime


class Order(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    package_id: str
    credits: int
    unit_amount: int
    currency: str
    status: str
    created_at: datetime
    expires_at: datetime
    paid_at: datetime | None


class AdminOrder(Order):
    user_id: UUID
    email: str


class CreditPage(BaseModel):
    items: list[CreditEntry]
    total: int


class OrderPage(BaseModel):
    items: list[Order]
    total: int


class AdminOrderPage(BaseModel):
    items: list[AdminOrder]
    total: int


class Wallet(BaseModel):
    balance: int


class Packages(BaseModel):
    enabled: bool
    items: list[CreditPackage]


class Checkout(BaseModel):
    order_id: UUID
    url: str
