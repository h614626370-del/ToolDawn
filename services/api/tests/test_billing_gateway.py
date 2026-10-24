import asyncio
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
import stripe
from fastapi import HTTPException
from pydantic import ValidationError

from tooldawn.config import Settings
from tooldawn.modules.billing.gateway import StripeGateway
from tooldawn.modules.billing.models import OrderRecord


def gateway():
    return StripeGateway(
        Settings(
            _env_file=None,
            environment="test",
            stripe_secret_key="sk_test_placeholder",
            stripe_webhook_secret="whsec_test_placeholder",
        )
    )


def test_checkout_uses_server_snapshot_and_stable_idempotency():
    provider = gateway()
    create = Mock(
        return_value=SimpleNamespace(id="cs_test_123", url="https://checkout.stripe.com/c/pay/123")
    )
    provider.client = SimpleNamespace(
        v1=SimpleNamespace(checkout=SimpleNamespace(sessions=SimpleNamespace(create=create)))
    )
    order = OrderRecord(
        id=uuid4(),
        user_id=uuid4(),
        credits=123,
        unit_amount=456,
        currency="eur",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    assert asyncio.run(provider.checkout(order)) == (
        "cs_test_123",
        "https://checkout.stripe.com/c/pay/123",
    )
    data, options = create.call_args.args
    assert options == {"idempotency_key": f"tooldawn-order-{order.id}"}
    assert data["line_items"][0]["price_data"]["unit_amount"] == 456
    assert data["line_items"][0]["price_data"]["currency"] == "eur"
    assert data["metadata"] == {"order_id": str(order.id)}
    assert data["client_reference_id"] == str(order.id)
    create.return_value.url = "https://example.com/"
    with pytest.raises(HTTPException) as exc:
        asyncio.run(provider.checkout(order))
    assert exc.value.status_code == 503
    create.side_effect = stripe.APIConnectionError("test network failure")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(provider.checkout(order))
    assert exc.value.status_code == 503


@pytest.mark.parametrize(
    "age,live,valid", [(0, False, True), (600, False, False), (0, True, False)]
)
def test_webhook_signature_age_and_mode(age, live, valid):
    provider = gateway()
    body = json.dumps(
        {"id": "evt_test", "object": "event", "livemode": live, "type": "ignored"}
    ).encode()
    timestamp = int(time.time()) - age
    digest = hmac.new(
        b"whsec_test_placeholder", str(timestamp).encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    signature = f"t={timestamp},v1={digest}"
    if valid:
        assert provider.verify(body, signature)["id"] == "evt_test"
        with pytest.raises(HTTPException):
            provider.verify(body + b" ", signature)
    else:
        with pytest.raises(HTTPException) as exc:
            provider.verify(body, signature)
        assert exc.value.status_code == 400


def test_payment_config_requires_matching_secrets_and_test_environment():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, stripe_secret_key="sk_test_placeholder")
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            stripe_secret_key="sk_live_placeholder",
            stripe_webhook_secret="whsec_test",
        )
    assert not StripeGateway(Settings(_env_file=None)).enabled
