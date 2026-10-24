"""Hosted checkout / Native adapters. No browser result can mark an order paid."""

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qsl, urlencode, urlsplit
from uuid import UUID

import httpx
from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException
from pydantic import SecretStr

from tooldawn.modules.billing.gateway import StripeGateway


def invalid():
    return HTTPException(400, "支付通知签名或订单信息无效。")


def rsa_key(value, private=False):
    if "-----BEGIN" not in value:
        value = "".join(value.split())
        label = "PRIVATE KEY" if private else "PUBLIC KEY"
        value = f"-----BEGIN {label}-----\n{value}\n-----END {label}-----"
    key = (
        serialization.load_pem_private_key(value.encode(), password=None)
        if private
        else serialization.load_pem_public_key(value.encode())
    )
    expected = rsa.RSAPrivateKey if private else rsa.RSAPublicKey
    if not isinstance(key, expected) or key.key_size < 2048:
        raise ValueError("Invalid RSA key")
    return key


def rsa_sign(key, message):
    return base64.b64encode(
        rsa_key(key, True).sign(message, padding.PKCS1v15(), hashes.SHA256())
    ).decode()


def rsa_verify(key, message, signature):
    rsa_key(key).verify(
        base64.b64decode(signature, validate=True), message, padding.PKCS1v15(), hashes.SHA256()
    )


def canonical(params, excluded=("sign", "sign_type")):
    return "&".join(
        f"{key}={value}"
        for key, value in sorted(params.items())
        if key not in excluded and value != ""
    )


def form_values(raw):
    pairs = parse_qsl(raw.decode("utf-8"), keep_blank_values=True, max_num_fields=100)
    if len({key for key, _ in pairs}) != len(pairs):
        raise invalid()
    return dict(pairs)


def minor_amount(value):
    try:
        number = Decimal(str(value)) * 100
        if (
            not number.is_finite()
            or number != number.to_integral_value()
            or not 0 < number <= 100_000_000
        ):
            raise invalid()
        return int(number)
    except (InvalidOperation, ValueError, TypeError):
        raise invalid() from None


@dataclass
class PaymentNotice:
    order_id: UUID
    trade_id: str
    amount: int
    currency: str
    method: str | None = None
    checkout_id: str | None = None
    status: str = "paid"


@dataclass
class PaymentLink:
    url: str = ""
    qr_code: str | None = None
    checkout_id: str | None = None


class ProviderGateway:
    def __init__(self, provider, config, settings):
        self.provider, self.config, self.settings = provider, config, settings
        self.kind = provider.kind
        self.notify = f"{config['public_origin']}/api/v1/billing/providers/{provider.id}/webhook"

    def stripe(self):
        settings = self.settings.model_copy(
            update={
                "stripe_secret_key": SecretStr(self.config["secret_key"]),
                "stripe_webhook_secret": SecretStr(self.config["webhook_secret"]),
                "billing_origin": self.config["public_origin"],
            }
        )
        return StripeGateway(settings)

    async def request(self, url, *, headers=None, payload=None, verify_wechat=False):
        # Only fixed official API hosts reach this method. EasyPay is a redirect,
        # never a server-side fetch to a configurable destination.
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
                async with client.stream("POST", url, headers=headers, content=payload) as response:
                    chunks = bytearray()
                    async for part in response.aiter_bytes():
                        chunks.extend(part)
                        if len(chunks) > 1_048_576:
                            raise ValueError("Oversized payment response")
                    body = bytes(chunks)
                    if verify_wechat:
                        self.verify_wechat(body, response.headers)
                    response.raise_for_status()
                    result = json.loads(body)
                    if not isinstance(result, dict):
                        raise ValueError("Invalid payment response")
                    return result
        except (httpx.HTTPError, ValueError, HTTPException, InvalidSignature) as exc:
            raise HTTPException(503, "支付服务暂时不可用，请检查供应商配置后重试。") from exc

    async def checkout(self, order):
        cfg = self.config
        reference = order.id.hex  # WeChat requires at most 32 characters.
        subject = f"ToolDawn {order.credits} credits"
        return_url = f"{cfg['public_origin']}/account/credits?order={order.id}"
        amount = f"{order.unit_amount // 100}.{order.unit_amount % 100:02d}"
        if self.kind == "stripe":
            identity, url = await self.stripe().checkout(order)
            return PaymentLink(url=url, checkout_id=identity)
        if self.kind == "easypay":
            params = dict(
                pid=cfg["pid"],
                type=order.payment_method,
                out_trade_no=reference,
                notify_url=self.notify,
                return_url=return_url,
                name=subject,
                money=amount,
            )
            params["sign"] = hashlib.md5((canonical(params) + cfg["key"]).encode()).hexdigest()
            params["sign_type"] = "MD5"
            return PaymentLink(url=f"{cfg['api_base']}/submit.php?{urlencode(params)}")
        if self.kind == "alipay":
            params = dict(
                app_id=cfg["app_id"],
                method="alipay.trade.page.pay",
                format="JSON",
                charset="utf-8",
                sign_type="RSA2",
                version="1.0",
                notify_url=self.notify,
                return_url=return_url,
                timestamp=(datetime.now(UTC) + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S"),
                biz_content=json.dumps(
                    dict(
                        out_trade_no=reference,
                        total_amount=amount,
                        subject=subject,
                        product_code="FAST_INSTANT_TRADE_PAY",
                        timeout_express="60m",
                    ),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            )
            params["sign"] = rsa_sign(cfg["private_key"], canonical(params, ("sign",)).encode())
            host = (
                "openapi.alipay.com"
                if cfg["environment"] == "live"
                else "openapi-sandbox.dl.alipaydev.com"
            )
            return PaymentLink(url=f"https://{host}/gateway.do?{urlencode(params)}")
        if self.kind == "wxpay":
            path = "/v3/pay/transactions/native"
            body = json.dumps(
                dict(
                    appid=cfg["app_id"],
                    mchid=cfg["mch_id"],
                    description=subject,
                    out_trade_no=reference,
                    notify_url=self.notify,
                    time_expire=order.expires_at.isoformat(),
                    amount=dict(total=order.unit_amount, currency="CNY"),
                ),
                separators=(",", ":"),
            ).encode()
            timestamp, nonce = str(int(time.time())), secrets.token_hex(16)
            message = f"POST\n{path}\n{timestamp}\n{nonce}\n".encode() + body + b"\n"
            signature = rsa_sign(cfg["private_key"], message)
            authorization = (
                f'WECHATPAY2-SHA256-RSA2048 mchid="{cfg["mch_id"]}",'
                f'nonce_str="{nonce}",timestamp="{timestamp}",serial_no="{cfg["cert_serial"]}",'
                f'signature="{signature}"'
            )
            data = await self.request(
                "https://api.mch.weixin.qq.com" + path,
                headers={
                    "Authorization": authorization,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Wechatpay-Serial": cfg["public_key_id"],
                },
                payload=body,
                verify_wechat=True,
            )
            code = data.get("code_url", "")
            if not isinstance(code, str) or not code.startswith("weixin://") or len(code) > 4096:
                raise HTTPException(503, "支付服务未返回有效地址。")
            return PaymentLink(qr_code=code)
        if self.kind == "airwallex":
            base = (
                "https://api.airwallex.com"
                if cfg["environment"] == "live"
                else "https://api-demo.airwallex.com"
            )
            token = await self.request(
                base + "/api/v1/authentication/login",
                headers={
                    "x-client-id": cfg["client_id"],
                    "x-api-key": cfg["api_key"],
                    "Content-Type": "application/json",
                },
                payload=b"{}",
            )
            if not isinstance(token.get("token"), str) or not token["token"]:
                raise HTTPException(503, "支付服务暂时不可用，请检查供应商配置后重试。")
            # Serialize the integer minor amount as an exact JSON decimal, not a float.
            body = json.dumps(
                dict(
                    reusable=False,
                    title=subject,
                    currency=order.currency.upper(),
                    reference=reference,
                    metadata={"order_id": reference},
                    expires_at=order.expires_at.isoformat(),
                ),
                separators=(",", ":"),
            )
            body = body[:-1] + ',"amount":' + amount + "}"
            data = await self.request(
                base + "/api/v1/pa/payment_links/create",
                headers={
                    "Authorization": "Bearer " + token["token"],
                    "Content-Type": "application/json",
                },
                payload=body.encode(),
            )
            url = data.get("url", "")
            parsed = urlsplit(url)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or not (
                    parsed.hostname == "airwallex.com" or parsed.hostname.endswith(".airwallex.com")
                )
                or parsed.username
                or parsed.password
                or not data.get("id")
            ):
                raise HTTPException(503, "支付服务未返回有效地址。")
            return PaymentLink(url=url, checkout_id=data["id"])
        raise HTTPException(422, "不支持此支付供应商。")

    def verify_wechat(self, body, headers):
        timestamp = headers.get("wechatpay-timestamp", "")
        nonce = headers.get("wechatpay-nonce", "")
        if (
            abs(time.time() - int(timestamp)) > 300
            or headers.get("wechatpay-serial") != self.config["public_key_id"]
            or not nonce
        ):
            raise invalid()
        rsa_verify(
            self.config["public_key"],
            f"{timestamp}\n{nonce}\n".encode() + body + b"\n",
            headers.get("wechatpay-signature", ""),
        )

    def notification(self, body, headers):
        try:
            return self._notification(body, headers)
        except (KeyError, ValueError, TypeError, AttributeError, InvalidSignature, InvalidTag):
            raise invalid() from None

    def _notification(self, body, headers):
        cfg = self.config
        if self.kind in {"easypay", "alipay"}:
            data = form_values(body)
            if self.kind == "easypay":
                expected = hashlib.md5((canonical(data) + cfg["key"]).encode()).hexdigest()
                if (
                    data.get("sign_type", "MD5") != "MD5"
                    or not hmac.compare_digest(expected, data.get("sign", ""))
                    or data.get("pid") != cfg["pid"]
                ):
                    raise invalid()
                method = data.get("type")
                if method not in {"alipay", "wxpay"}:
                    raise invalid()
                amount = data.get("money")
            else:
                if (
                    data.get("sign_type") != "RSA2"
                    or data.get("app_id") != cfg["app_id"]
                    or data.get("seller_id") != cfg["seller_id"]
                ):
                    raise invalid()
                rsa_verify(cfg["public_key"], canonical(data).encode(), data.get("sign", ""))
                method, amount = "alipay", data.get("total_amount")
            allowed = (
                {"TRADE_SUCCESS"} if self.kind == "easypay" else {"TRADE_SUCCESS", "TRADE_FINISHED"}
            )
            if data.get("trade_status") not in allowed:
                return None
            return PaymentNotice(
                UUID(data["out_trade_no"]),
                data["trade_no"],
                minor_amount(amount),
                "cny",
                method=method,
            )
        if self.kind == "wxpay":
            self.verify_wechat(body, headers)
            event = json.loads(body)
            if event.get("event_type") != "TRANSACTION.SUCCESS":
                return None
            resource = event["resource"]
            if resource["algorithm"] != "AEAD_AES_256_GCM":
                raise invalid()
            plain = AESGCM(cfg["api_v3_key"].encode()).decrypt(
                resource["nonce"].encode(),
                base64.b64decode(resource["ciphertext"], validate=True),
                resource.get("associated_data", "").encode(),
            )
            data = json.loads(plain)
            if (
                data["appid"] != cfg["app_id"]
                or data["mchid"] != cfg["mch_id"]
                or data["trade_state"] != "SUCCESS"
                or data["trade_type"] != "NATIVE"
                or type(data["amount"]["total"]) is not int
            ):
                raise invalid()
            return PaymentNotice(
                UUID(data["out_trade_no"]),
                data["transaction_id"],
                data["amount"]["total"],
                data["amount"]["currency"].lower(),
                method="wxpay",
            )
        if self.kind == "stripe":
            event = self.stripe().verify(body, headers.get("stripe-signature", ""))
            event_type = event["type"]
            if event_type not in {
                "checkout.session.completed",
                "checkout.session.async_payment_succeeded",
                "checkout.session.expired",
                "checkout.session.async_payment_failed",
            }:
                return None
            data = event["data"]["object"]
            order_id = UUID(data["metadata"]["order_id"])
            if data.get("mode") != "payment" or data.get("client_reference_id") != str(order_id):
                raise invalid()
            status = {
                "checkout.session.expired": "expired",
                "checkout.session.async_payment_failed": "failed",
            }.get(event_type, "paid")
            if status == "paid" and data.get("payment_status") != "paid":
                return None
            if type(data.get("amount_total")) is not int:
                raise invalid()
            return PaymentNotice(
                order_id,
                data["id"],
                data["amount_total"],
                data["currency"].lower(),
                checkout_id=data["id"],
                status=status,
            )
        if self.kind == "airwallex":
            timestamp = headers.get("x-timestamp", "")
            expected = hmac.new(
                cfg["webhook_secret"].encode(), timestamp.encode() + body, hashlib.sha256
            ).hexdigest()
            if (
                not hmac.compare_digest(expected, headers.get("x-signature", ""))
                or abs(time.time() - int(timestamp) / 1000) > 300
            ):
                raise invalid()
            event = json.loads(body, parse_float=Decimal)
            if event.get("account_id") != cfg["account_id"]:
                raise invalid()
            if event.get("name") != "payment_link.paid":
                return None
            data = event["data"]["object"]
            if data.get("status") != "PAID" or data.get("reusable") is not False:
                raise invalid()
            order_id = UUID(data["reference"])
            if UUID(data["metadata"]["order_id"]) != order_id:
                raise invalid()
            # A non-reusable link is itself a unique payment reference.
            return PaymentNotice(
                order_id,
                data["id"],
                minor_amount(data["amount"]),
                data["currency"].lower(),
                checkout_id=data["id"],
            )
        raise invalid()
