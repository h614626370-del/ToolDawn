from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tooldawn.modules.admin.models import AuditRecord
from tooldawn.modules.auth.models import UserRecord
from tooldawn.modules.billing.models import CreditRecord, OrderRecord, ProviderRecord, WalletRecord
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
        self,
        user_id: UUID,
        request_key: UUID,
        package_id: str,
        packages: list[CreditPackage],
        provider_id=None,
        payment_method="card",
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
                if (
                    existing.package_id != package_id
                    or existing.provider_id != provider_id
                    or existing.payment_method != payment_method
                ):
                    raise HTTPException(409, "重复请求的套餐不一致。")
                if existing.status != "pending" or existing.expires_at <= datetime.now(UTC):
                    raise HTTPException(409, "订单已结束，请重新创建。")
                return existing
            package = next((p for p in packages if p.id == package_id), None)
            if not package:
                raise HTTPException(422, "套餐不存在或已停用。")
            provider = None
            if provider_id:
                from tooldawn.modules.billing.provider_config import CATALOG

                provider = await db.get(ProviderRecord, provider_id, with_for_update=True)
                if not provider or not provider.enabled:
                    raise HTTPException(422, "支付供应商不存在或已停用。")
                if (
                    payment_method not in provider.methods
                    or package.currency not in CATALOG[provider.kind]["currencies"]
                ):
                    raise HTTPException(422, "此支付方式不支持所选套餐币种。")
            elif payment_method != "card":
                raise HTTPException(422, "此支付方式不支持所选套餐币种。")
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
                provider_id=provider_id,
                provider_key=provider.kind if provider else "stripe",
                provider_name=provider.name if provider else "Stripe",
                payment_method=payment_method,
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
                order.provider_id is not None
                or payload.get("mode") != "payment"
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

    async def provider_checkout(self, identity, user_id, gateway=None):
        from tooldawn.modules.billing.schemas import Checkout

        async with self.sessions.begin() as db:
            order = await db.scalar(
                select(OrderRecord)
                .where(OrderRecord.id == identity, OrderRecord.user_id == user_id)
                .with_for_update()
            )
            if not order:
                raise HTTPException(404, "订单不存在。")
            if order.status != "pending" or order.expires_at <= datetime.now(UTC):
                raise HTTPException(409, "订单已结束，请重新创建。")
            if not order.checkout_url and not order.qr_code:
                if gateway is None:
                    raise HTTPException(409, "支付尚未创建成功，请重新选择套餐。")
                # Serialize upstream creation for double-clicks and simultaneous retries.
                result = await gateway.checkout(order)
                order.checkout_url, order.qr_code = result.url or None, result.qr_code
                order.checkout_id = result.checkout_id
            return Checkout(
                order_id=order.id,
                url=order.checkout_url or "",
                qr_code=order.qr_code,
                expires_at=order.expires_at,
            )

    async def fulfill_provider(self, provider_id, notice):
        if not isinstance(notice.trade_id, str) or not 0 < len(notice.trade_id) <= 255:
            raise HTTPException(400, "支付通知签名或订单信息无效。")
        async with self.sessions.begin() as db:
            snapshot = await db.get(OrderRecord, notice.order_id)
            if not snapshot or snapshot.provider_id != provider_id:
                raise HTTPException(400, "支付金额或订单不匹配。")
            await self._lock_user(db, snapshot.user_id)
            order = await db.scalar(
                select(OrderRecord)
                .where(OrderRecord.id == notice.order_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if (
                order.currency != notice.currency
                or order.unit_amount != notice.amount
                or (notice.method and order.payment_method != notice.method)
                or (notice.checkout_id and order.checkout_id != notice.checkout_id)
            ):
                raise HTTPException(400, "支付金额或订单不匹配。")
            if order.status == "paid":
                if notice.status == "paid" and order.provider_trade_id != notice.trade_id:
                    raise HTTPException(400, "支付金额或订单不匹配。")
                return
            if notice.status in {"expired", "failed"}:
                order.status = notice.status
                return
            if notice.status != "paid":
                raise HTTPException(400, "支付通知签名或订单信息无效。")
            # Unique (provider, transaction) and the user row lock protect both
            # cross-order reuse and duplicate/concurrent notification delivery.
            duplicate = await db.scalar(
                select(OrderRecord.id).where(
                    OrderRecord.provider_id == provider_id,
                    OrderRecord.provider_trade_id == notice.trade_id,
                    OrderRecord.id != order.id,
                )
            )
            if duplicate:
                raise HTTPException(400, "支付金额或订单不匹配。")
            order.provider_trade_id = notice.trade_id
            await db.flush()
            await self._apply(
                db, order.user_id, order.credits, "purchase", f"order:{order.id}", order.package_id
            )
            order.status, order.paid_at = "paid", datetime.now(UTC)

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
        self,
        user_id: UUID | None,
        offset: int,
        limit: int,
        q="",
        status=None,
        start=None,
        end=None,
    ) -> OrderPage | AdminOrderPage:
        async with self.sessions() as db:
            where = self.order_filters(q, status, start, end)
            if user_id:
                where.append(OrderRecord.user_id == user_id)
            total = await db.scalar(
                select(func.count()).select_from(OrderRecord).join(UserRecord).where(*where)
            )
            rows = await db.execute(
                select(OrderRecord, UserRecord.email)
                .join(UserRecord, UserRecord.id == OrderRecord.user_id)
                .where(*where)
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

    @staticmethod
    def order_filters(q="", status=None, start=None, end=None):
        filters = []
        if q.strip():
            filters.append(
                or_(
                    UserRecord.email.icontains(q.strip(), autoescape=True),
                    cast(OrderRecord.id, String).icontains(q.strip(), autoescape=True),
                    OrderRecord.package_id.icontains(q.strip(), autoescape=True),
                )
            )
        if status:
            filters.append(OrderRecord.status == status)
        if start:
            filters.append(OrderRecord.created_at >= start)
        if end:
            filters.append(OrderRecord.created_at < end)
        return filters

    async def statistics(self, q="", status=None, start=None, end=None):
        filters = self.order_filters(q, status, start, end)
        async with self.sessions() as db:
            rows = await db.execute(
                select(OrderRecord.status, func.count())
                .join(UserRecord)
                .where(*filters)
                .group_by(OrderRecord.status)
            )
            counts = dict.fromkeys(("pending", "paid", "expired", "failed"), 0)
            counts.update(dict(rows.all()))
            revenue = await db.execute(
                select(
                    OrderRecord.currency,
                    func.sum(OrderRecord.unit_amount),
                    func.sum(OrderRecord.credits),
                    func.count(),
                )
                .join(UserRecord)
                .where(*filters, OrderRecord.status == "paid")
                .group_by(OrderRecord.currency)
                .order_by(OrderRecord.currency)
            )
            return {
                "total": sum(counts.values()),
                "statuses": counts,
                "revenue": [
                    {
                        "currency": currency,
                        "amount": int(amount),
                        "credits": int(credits),
                        "orders": count,
                    }
                    for currency, amount, credits, count in revenue
                ],
            }
