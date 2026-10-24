from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tooldawn.modules.admin.models import AuditRecord
from tooldawn.modules.auth.models import UserRecord
from tooldawn.modules.billing.models import CreditRecord, OrderRecord, WalletRecord
from tooldawn.modules.billing.schemas import (
    AdjustmentInput,
    AdminOrder,
    AdminOrderPage,
    CreditEntry,
    CreditPackage,
    CreditPage,
    Order,
    OrderPage,
)


class BillingRepository:
    def __init__(self, sessions: async_sessionmaker):
        self.sessions = sessions

    async def _lock_user(self, db: AsyncSession, user_id: UUID) -> UserRecord:
        user = await db.scalar(select(UserRecord).where(UserRecord.id == user_id).with_for_update())
        if user is None:
            raise HTTPException(404, "用户不存在。")
        return user

    async def _apply(
        self,
        db: AsyncSession,
        user_id: UUID,
        amount: int,
        kind: str,
        reference: str,
        reason: str,
        actor_id: UUID | None = None,
    ) -> CreditRecord:
        # Every writer locks the owner first, including the initial wallet creation.
        wallet = await db.get(WalletRecord, user_id)
        if wallet is None:
            wallet = WalletRecord(user_id=user_id, balance=0)
            db.add(wallet)
        if wallet.balance + amount < 0:
            raise HTTPException(409, "积分不足。")
        wallet.balance += amount
        entry = CreditRecord(
            id=uuid4(),
            user_id=user_id,
            amount=amount,
            balance_after=wallet.balance,
            kind=kind,
            reference=reference,
            reason=reason,
            actor_id=actor_id,
            created_at=datetime.now(UTC),
        )
        db.add(entry)
        return entry

    async def balance(self, user_id: UUID) -> int:
        async with self.sessions() as db:
            return (
                await db.scalar(select(WalletRecord.balance).where(WalletRecord.user_id == user_id))
                or 0
            )

    async def entries(self, user_id: UUID, offset: int, limit: int) -> CreditPage:
        async with self.sessions() as db:
            where = CreditRecord.user_id == user_id
            total = await db.scalar(select(func.count()).select_from(CreditRecord).where(where))
            records = await db.scalars(
                select(CreditRecord)
                .where(where)
                .order_by(CreditRecord.created_at.desc(), CreditRecord.id.desc())
                .offset(offset)
                .limit(limit)
            )
            return CreditPage(items=[CreditEntry.model_validate(r) for r in records], total=total)

    async def adjust(self, user_id: UUID, data: AdjustmentInput, actor_id: UUID) -> CreditEntry:
        if not data.amount or len(data.reason.strip()) < 3:
            raise HTTPException(422, "请填写非零积分和调整原因。")
        reference = f"adjust:{data.request_key}"
        async with self.sessions.begin() as db:
            await self._lock_user(db, user_id)
            previous = await db.scalar(
                select(CreditRecord).where(
                    CreditRecord.user_id == user_id, CreditRecord.reference == reference
                )
            )
            if previous:
                if (previous.amount, previous.reason, previous.actor_id) != (
                    data.amount,
                    data.reason.strip(),
                    actor_id,
                ):
                    raise HTTPException(409, "重复请求的内容不一致。")
                return CreditEntry.model_validate(previous)
            entry = await self._apply(
                db, user_id, data.amount, "adjustment", reference, data.reason.strip(), actor_id
            )
            db.add(
                AuditRecord(
                    id=uuid4(),
                    actor_id=actor_id,
                    action="credit.adjust",
                    target=str(user_id),
                    changed_fields=["amount", "reason"],
                    created_at=datetime.now(UTC),
                )
            )
            return CreditEntry.model_validate(entry)

    async def prepare_order(
        self, user_id: UUID, request_key: UUID, package_id: str, packages: list[CreditPackage]
    ) -> OrderRecord:
        async with self.sessions.begin() as db:
            owner = await self._lock_user(db, user_id)
            if owner.disabled:
                raise HTTPException(403, "账户已禁用。")
            existing = await db.scalar(
                select(OrderRecord).where(
                    OrderRecord.user_id == user_id, OrderRecord.request_key == request_key
                )
            )
            if existing:
                if existing.package_id != package_id:
                    raise HTTPException(409, "重复请求的套餐不一致。")
                if existing.status != "pending" or existing.expires_at <= datetime.now(UTC):
                    raise HTTPException(409, "订单已结束，请重新创建。")
                return existing
            package = next((p for p in packages if p.id == package_id), None)
            if not package:
                raise HTTPException(422, "套餐不存在或已停用。")
            # Bound unpaid sessions without relying on the browser to debounce requests.
            pending = await db.scalar(
                select(func.count())
                .select_from(OrderRecord)
                .where(
                    OrderRecord.user_id == user_id,
                    OrderRecord.status == "pending",
                    OrderRecord.expires_at > datetime.now(UTC),
                )
            )
            if pending >= 5:
                raise HTTPException(429, "待支付订单过多，请稍后重试。")
            order = OrderRecord(
                id=uuid4(),
                user_id=user_id,
                request_key=request_key,
                package_id=package.id,
                credits=package.credits,
                unit_amount=package.unit_amount,
                currency=package.currency,
                status="pending",
                created_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
            db.add(order)
            await db.flush()
            return order

    async def attach_checkout(self, order_id: UUID, session_id: str, url: str) -> None:
        async with self.sessions.begin() as db:
            order = await db.scalar(
                select(OrderRecord)
                .where(OrderRecord.id == order_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if order.checkout_id and order.checkout_id != session_id:
                raise HTTPException(409, "支付订单不一致。")
            order.checkout_id, order.checkout_url = session_id, url

    async def fulfill(self, payload: dict, event_type: str) -> None:
        metadata = payload.get("metadata") or {}
        try:
            order_id = UUID(metadata.get("order_id", ""))
        except (ValueError, TypeError):
            return  # Other applications may share this Stripe account.
        async with self.sessions.begin() as db:
            snapshot = await db.get(OrderRecord, order_id)
            if snapshot is None:
                return
            await self._lock_user(db, snapshot.user_id)
            order = await db.scalar(
                select(OrderRecord)
                .where(OrderRecord.id == order_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if (
                payload.get("mode") != "payment"
                or payload.get("currency") != order.currency
                or payload.get("amount_total") != order.unit_amount
                or payload.get("client_reference_id") != str(order.id)
                or not payload.get("id")
                or (order.checkout_id and order.checkout_id != payload["id"])
            ):
                raise HTTPException(400, "支付金额或订单不匹配。")
            if order.status == "paid":
                return
            if event_type in {"checkout.session.expired", "checkout.session.async_payment_failed"}:
                order.status = "expired" if event_type.endswith("expired") else "failed"
                return
            if payload.get("payment_status") != "paid":
                return
            # The order snapshot is the only source of credits. Callback metadata cannot set it.
            await self._apply(
                db, order.user_id, order.credits, "purchase", f"order:{order.id}", order.package_id
            )
            order.status = "paid"
            order.paid_at = datetime.now(UTC)
            order.checkout_id = payload["id"]

    async def order(self, order_id: UUID, user_id: UUID) -> Order:
        async with self.sessions() as db:
            record = await db.scalar(
                select(OrderRecord).where(
                    OrderRecord.id == order_id, OrderRecord.user_id == user_id
                )
            )
            if record is None:
                raise HTTPException(404, "订单不存在。")
            return Order.model_validate(record)

    async def orders(
        self, user_id: UUID | None, offset: int, limit: int
    ) -> OrderPage | AdminOrderPage:
        async with self.sessions() as db:
            where = OrderRecord.user_id == user_id if user_id else True
            total = await db.scalar(select(func.count()).select_from(OrderRecord).where(where))
            rows = await db.execute(
                select(OrderRecord, UserRecord.email)
                .join(UserRecord, UserRecord.id == OrderRecord.user_id)
                .where(where)
                .order_by(OrderRecord.created_at.desc(), OrderRecord.id.desc())
                .offset(offset)
                .limit(limit)
            )
            if user_id:
                return OrderPage(items=[Order.model_validate(row[0]) for row in rows], total=total)
            return AdminOrderPage(
                items=[
                    AdminOrder(
                        **Order.model_validate(row[0]).model_dump(),
                        user_id=row[0].user_id,
                        email=row[1],
                    )
                    for row in rows
                ],
                total=total,
            )
