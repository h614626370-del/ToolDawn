import asyncio
import base64
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException

from tooldawn.config import Settings
from tooldawn.modules.billing.provider_config import validate_config
from tooldawn.modules.billing.provider_gateway import (
    ProviderGateway,
    canonical,
    minor_amount,
    rsa_sign,
    rsa_verify,
)


@pytest.fixture(scope="module")
def keys():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return (
        private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode(),
        private.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode(),
    )


def config(kind, keys):
    private, public = keys
    return {
        "public_origin": "https://tools.example",
        "environment": "sandbox",
        "api_base": "https://pay.example",
        "pid": "123",
        "key": "test-only-pkey",
        "app_id": "app-test",
        "seller_id": "seller-test",
        "private_key": private,
        "public_key": public,
        "mch_id": "merchant-test",
        "cert_serial": "serial-test",
        "public_key_id": "PUB_KEY_ID_TEST",
        "api_v3_key": "test" * 8,
        "secret_key": "sk_test_placeholder",
        "webhook_secret": "whsec_test_only",
        "client_id": "client-test",
        "account_id": "account-test",
        "api_key": "api-test",
    }


def gateway(kind, keys):
    return ProviderGateway(
        SimpleNamespace(id=uuid4(), kind=kind),
        config(kind, keys),
        Settings(_env_file=None, environment="test"),
    )


def order():
    return SimpleNamespace(
        id=uuid4(),
        credits=100,
        unit_amount=500,
        currency="cny",
        payment_method="alipay",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def signed_event(kind, cfg, order_id, amount=500, trade_id="trade-test", **changes):
    if kind in {"easypay", "alipay"}:
        data = dict(out_trade_no=order_id.hex, trade_no=trade_id, trade_status="TRADE_SUCCESS")
        if kind == "easypay":
            data.update(pid=cfg["pid"], type="alipay", money=f"{amount / 100:.2f}")
            data.update(changes)
            data["sign"] = hashlib.md5((canonical(data) + cfg["key"]).encode()).hexdigest()
            data["sign_type"] = "MD5"
        else:
            data.update(
                app_id=cfg["app_id"], seller_id=cfg["seller_id"], total_amount=f"{amount / 100:.2f}"
            )
            data.update(changes)
            data["sign"] = rsa_sign(cfg["private_key"], canonical(data).encode())
            data["sign_type"] = "RSA2"
        return urlencode(data).encode(), {"content-type": "application/x-www-form-urlencoded"}
    if kind == "wxpay":
        data = dict(
            out_trade_no=order_id.hex,
            transaction_id=trade_id,
            appid=cfg["app_id"],
            mchid=cfg["mch_id"],
            trade_state="SUCCESS",
            trade_type="NATIVE",
            amount={"total": amount, "currency": "CNY"},
        )
        data.update(changes)
        cipher = AESGCM(cfg["api_v3_key"].encode()).encrypt(
            b"012345678901", json.dumps(data).encode(), b"transaction"
        )
        body = json.dumps(
            {
                "event_type": "TRANSACTION.SUCCESS",
                "resource": {
                    "algorithm": "AEAD_AES_256_GCM",
                    "nonce": "012345678901",
                    "associated_data": "transaction",
                    "ciphertext": base64.b64encode(cipher).decode(),
                },
            }
        ).encode()
        timestamp = str(int(time.time()))
        return body, {
            "wechatpay-timestamp": timestamp,
            "wechatpay-nonce": "nonce-test",
            "wechatpay-serial": cfg["public_key_id"],
            "wechatpay-signature": rsa_sign(
                cfg["private_key"], f"{timestamp}\nnonce-test\n".encode() + body + b"\n"
            ),
        }
    if kind == "stripe":
        data = dict(
            id=trade_id,
            mode="payment",
            metadata={"order_id": str(order_id)},
            client_reference_id=str(order_id),
            amount_total=amount,
            currency="cny",
            payment_status="paid",
        )
        data.update(changes)
        body = json.dumps(
            {
                "object": "event",
                "id": "evt_test",
                "livemode": False,
                "type": "checkout.session.completed",
                "data": {"object": data},
            }
        ).encode()
        timestamp = str(int(time.time()))
        sign = hmac.new(
            cfg["webhook_secret"].encode(), timestamp.encode() + b"." + body, hashlib.sha256
        ).hexdigest()
        return body, {"stripe-signature": f"t={timestamp},v1={sign}"}
    data = dict(
        id=trade_id,
        reference=order_id.hex,
        metadata={"order_id": order_id.hex},
        reusable=False,
        status="PAID",
        currency="CNY",
        amount=amount / 100,
    )
    data.update(changes)
    body = json.dumps(
        {"name": "payment_link.paid", "account_id": cfg["account_id"], "data": {"object": data}}
    ).encode()
    timestamp = str(int(time.time() * 1000))
    return body, {
        "x-timestamp": timestamp,
        "x-signature": hmac.new(
            cfg["webhook_secret"].encode(), timestamp.encode() + body, hashlib.sha256
        ).hexdigest(),
    }


@pytest.mark.parametrize("kind", ["easypay", "alipay", "wxpay", "stripe", "airwallex"])
def test_all_provider_signatures_and_tampering(kind, keys):
    adapter = gateway(kind, keys)
    identity = uuid4()
    body, headers = signed_event(kind, adapter.config, identity)
    notice = adapter.notification(body, headers)
    assert notice.order_id == identity and notice.amount == 500 and notice.currency == "cny"
    assert notice.trade_id == "trade-test"
    with pytest.raises(HTTPException) as error:
        adapter.notification(body + b"tampered", headers)
    assert error.value.status_code == 400


@pytest.mark.parametrize("kind", ["easypay", "alipay"])
def test_form_duplicate_fields_and_wrong_merchant(kind, keys):
    adapter = gateway(kind, keys)
    body, headers = signed_event(kind, adapter.config, uuid4())
    with pytest.raises(HTTPException):
        adapter.notification(body + b"&out_trade_no=other", headers)
    wrong = {"pid": "other"} if kind == "easypay" else {"seller_id": "other"}
    body, headers = signed_event(kind, adapter.config, uuid4(), **wrong)
    with pytest.raises(HTTPException):
        adapter.notification(body, headers)


def test_wechat_signed_but_wrong_merchant_and_replay(keys):
    adapter = gateway("wxpay", keys)
    body, headers = signed_event("wxpay", adapter.config, uuid4(), mchid="other")
    with pytest.raises(HTTPException):
        adapter.notification(body, headers)
    body, headers = signed_event("wxpay", adapter.config, uuid4())
    headers["wechatpay-timestamp"] = str(int(time.time()) - 600)
    with pytest.raises(HTTPException):
        adapter.notification(body, headers)


def test_airwallex_reusable_links_and_stale_delivery_rejected(keys):
    adapter = gateway("airwallex", keys)
    body, headers = signed_event("airwallex", adapter.config, uuid4(), reusable=True)
    with pytest.raises(HTTPException):
        adapter.notification(body, headers)
    body, headers = signed_event("airwallex", adapter.config, uuid4())
    timestamp = str(int((time.time() - 600) * 1000))
    headers = {
        "x-timestamp": timestamp,
        "x-signature": hmac.new(
            adapter.config["webhook_secret"].encode(), timestamp.encode() + body, hashlib.sha256
        ).hexdigest(),
    }
    with pytest.raises(HTTPException):
        adapter.notification(body, headers)


@pytest.mark.parametrize("value", ["1.001", "NaN", "Infinity", "-1", "0", True])
def test_amounts_reject_rounding_and_invalid_values(value):
    with pytest.raises(HTTPException):
        minor_amount(value)


def test_redirect_signatures(keys):
    for kind in ("easypay", "alipay"):
        adapter = gateway(kind, keys)
        record = order()
        result = asyncio.run(adapter.checkout(record))
        params = {k: v[0] for k, v in parse_qs(urlsplit(result.url).query).items()}
        if kind == "easypay":
            assert params["out_trade_no"] == record.id.hex
            expected = hashlib.md5((canonical(params) + adapter.config["key"]).encode()).hexdigest()
            assert params["sign"] == expected
            assert adapter.config["key"] not in result.url
        else:
            assert json.loads(params["biz_content"])["total_amount"] == "5.00"
            rsa_verify(keys[1], canonical(params, ("sign",)).encode(), params["sign"])


def test_wechat_and_airwallex_upstream_contracts(keys):
    adapter = gateway("wxpay", keys)
    adapter.request = AsyncMock(return_value={"code_url": "weixin://wxpay/test"})
    record = order()
    assert asyncio.run(adapter.checkout(record)).qr_code == "weixin://wxpay/test"
    call = adapter.request.call_args
    assert call.args[0] == "https://api.mch.weixin.qq.com/v3/pay/transactions/native"
    data = json.loads(call.kwargs["payload"])
    assert data["amount"]["total"] == 500 and data["out_trade_no"] == record.id.hex
    assert call.kwargs["verify_wechat"] is True
    adapter = gateway("airwallex", keys)
    adapter.request = AsyncMock(
        side_effect=[
            {"token": "test-token"},
            {"id": "pl-test", "url": "https://pay.airwallex.com/test"},
        ]
    )
    link = asyncio.run(adapter.checkout(record))
    assert link.checkout_id == "pl-test"
    payload = json.loads(adapter.request.call_args.kwargs["payload"])
    assert payload["reusable"] is False and payload["amount"] == 5
    assert (
        payload["reference"] == record.id.hex and payload["metadata"]["order_id"] == record.id.hex
    )


def test_provider_configuration_validation(keys):
    for kind in ("easypay", "alipay", "wxpay", "stripe", "airwallex"):
        validate_config(kind, config(kind, keys), True)
    for origin in (
        "http://public.example",
        "https://user:pass@example.com",
        "https://example.com?key=1",
    ):
        with pytest.raises(HTTPException):
            validate_config("easypay", {**config("easypay", keys), "public_origin": origin}, True)
    with pytest.raises(HTTPException):
        validate_config("wxpay", {**config("wxpay", keys), "api_v3_key": "short"}, True)


def test_wechat_http_response_requires_platform_signature(keys, monkeypatch):
    adapter = gateway("wxpay", keys)
    original = httpx.AsyncClient
    timestamp = str(int(time.time()))
    body = b'{"code_url":"weixin://wxpay/test"}'
    headers = {
        "wechatpay-timestamp": timestamp,
        "wechatpay-nonce": "response-nonce",
        "wechatpay-serial": adapter.config["public_key_id"],
    }
    headers["wechatpay-signature"] = rsa_sign(
        keys[0], f"{timestamp}\nresponse-nonce\n".encode() + body + b"\n"
    )

    def transport(request):
        return httpx.Response(200, content=body, headers=headers)

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(transport)),
    )
    result = asyncio.run(adapter.request("https://api.mch.weixin.qq.com/test", verify_wechat=True))
    assert result["code_url"] == "weixin://wxpay/test"
    del headers["wechatpay-signature"]
    with pytest.raises(HTTPException) as error:
        asyncio.run(adapter.request("https://api.mch.weixin.qq.com/test", verify_wechat=True))
    assert error.value.status_code == 503
