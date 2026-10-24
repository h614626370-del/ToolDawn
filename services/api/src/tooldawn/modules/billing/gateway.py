import asyncio

import stripe
from fastapi import HTTPException

from tooldawn.config import Settings
from tooldawn.modules.billing.models import OrderRecord


class StripeGateway:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.enabled = bool(settings.stripe_secret_key and settings.stripe_webhook_secret)
        self.client = (
            stripe.StripeClient(
                settings.stripe_secret_key.get_secret_value(),
                http_client=stripe.RequestsClient(timeout=20),
                max_network_retries=2,
            )
            if self.enabled
            else None
        )

    async def checkout(self, order: OrderRecord) -> tuple[str, str]:
        if not self.client:
            raise HTTPException(503, "支付尚未开放。")
        origin = self.settings.billing_origin.rstrip("/")
        try:
            session = await asyncio.to_thread(
                self.client.v1.checkout.sessions.create,
                {
                    "mode": "payment",
                    "client_reference_id": str(order.id),
                    "metadata": {"order_id": str(order.id)},
                    "success_url": f"{origin}/account/credits?order={order.id}",
                    "cancel_url": f"{origin}/account/credits?canceled=1",
                    "expires_at": int(order.expires_at.timestamp()),
                    "line_items": [
                        {
                            "quantity": 1,
                            "price_data": {
                                "currency": order.currency,
                                "unit_amount": order.unit_amount,
                                "product_data": {"name": f"ToolDawn {order.credits} credits"},
                            },
                        }
                    ],
                },
                {"idempotency_key": f"tooldawn-order-{order.id}"},
            )
        except stripe.StripeError as exc:
            raise HTTPException(503, "支付服务暂时不可用，请稍后重试。") from exc
        if not session.url or not session.url.startswith("https://checkout.stripe.com/"):
            raise HTTPException(503, "支付服务未返回有效地址。")
        return session.id, session.url

    def verify(self, body: bytes, signature: str) -> dict:
        if not self.enabled:
            raise HTTPException(503, "支付尚未开放。")
        try:
            event = stripe.Webhook.construct_event(
                body,
                signature,
                self.settings.stripe_webhook_secret.get_secret_value(),
                tolerance=300,
            ).to_dict()
        except (ValueError, stripe.SignatureVerificationError) as exc:
            raise HTTPException(400, "支付通知签名无效。") from exc
        live = self.settings.stripe_secret_key.get_secret_value().startswith("sk_live_")
        if event.get("livemode") is not live:
            raise HTTPException(400, "支付环境不匹配。")
        return event
