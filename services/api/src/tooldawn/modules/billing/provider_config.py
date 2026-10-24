"""Provider contracts. Secrets are accepted only on writes, never returned."""

from typing import Literal
from urllib.parse import urlsplit

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, SecretStr

ProviderKind = Literal["easypay", "alipay", "wxpay", "stripe", "airwallex"]


def field(key, label, secret=False, multiline=False, options=None, default="", optional=False):
    return dict(
        key=key,
        label=label,
        secret=secret,
        multiline=multiline,
        options=options,
        default=default,
        optional=optional,
    )


COMMON = [field("public_origin", "支付回调域名")]
CATALOG = {
    "easypay": dict(
        name="易支付",
        methods=["alipay", "wxpay"],
        currencies=["cny"],
        fields=COMMON
        + [field("api_base", "网关地址"), field("pid", "商户 PID"), field("key", "商户密钥", True)],
        events=[],
    ),
    "alipay": dict(
        name="支付宝直连",
        methods=["alipay"],
        currencies=["cny"],
        fields=COMMON
        + [
            field("environment", "支付环境", options=["live", "sandbox"], default="live"),
            field("app_id", "应用 App ID"),
            field("seller_id", "支付宝商户 UID"),
            field("private_key", "应用私钥", True, True),
            field("public_key", "支付宝公钥", True, True),
        ],
        events=[],
    ),
    "wxpay": dict(
        name="微信支付",
        methods=["wxpay"],
        currencies=["cny"],
        fields=COMMON
        + [
            field("app_id", "应用 App ID"),
            field("mch_id", "微信商户号"),
            field("cert_serial", "商户证书序列号"),
            field("private_key", "商户 API 私钥", True, True),
            field("api_v3_key", "API v3 密钥", True),
            field("public_key_id", "微信支付公钥 ID"),
            field("public_key", "微信支付公钥", True, True),
        ],
        events=["TRANSACTION.SUCCESS"],
    ),
    "stripe": dict(
        name="Stripe",
        methods=["card"],
        currencies=["usd", "eur", "cny"],
        fields=COMMON
        + [
            field("secret_key", "Secret Key", True),
            field("webhook_secret", "Webhook Secret", True),
        ],
        events=[
            "checkout.session.completed",
            "checkout.session.async_payment_succeeded",
            "checkout.session.async_payment_failed",
            "checkout.session.expired",
        ],
    ),
    "airwallex": dict(
        name="Airwallex",
        methods=["airwallex"],
        currencies=["usd", "eur", "cny"],
        fields=COMMON
        + [
            field("environment", "支付环境", options=["live", "sandbox"], default="sandbox"),
            field("client_id", "Client ID"),
            field("account_id", "Account ID"),
            field("api_key", "API Key", True),
            field("webhook_secret", "Webhook Secret", True),
        ],
        events=["payment_link.paid"],
    ),
}


class ProviderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: ProviderKind
    name: str = Field(min_length=1, max_length=80)
    enabled: bool = False
    sort_order: int = Field(default=0, ge=0, le=10000)
    methods: list[str] = Field(min_length=1, max_length=4)
    config: dict[str, SecretStr | None] = Field(default_factory=dict, max_length=20)
    revision: int = Field(default=0, ge=0)


def https_url(value, origin_only=False):
    try:
        url = urlsplit(value)
        _ = url.port  # Validate malformed or out-of-range ports as well.
    except ValueError:
        raise HTTPException(422, "支付地址必须是无账号、查询参数的 HTTPS 地址。") from None
    if (
        url.scheme != "https"
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
        or any(c.isspace() for c in value)
        or "\\" in value
        or any(ord(c) < 32 for c in value)
        or (origin_only and url.path not in ("", "/"))
    ):
        raise HTTPException(422, "支付地址必须是无账号、查询参数的 HTTPS 地址。")
    return value.rstrip("/")


def validate_config(kind, values, enabled):
    # Constructors are used at save time, so malformed keys cannot be enabled.
    from tooldawn.modules.billing.provider_gateway import rsa_key

    spec = CATALOG[kind]
    for item in spec["fields"]:
        value = values.get(item["key"], "")
        if len(value) > 10000:
            raise HTTPException(422, "支付配置内容过长。")
        if enabled and not item["optional"] and not value:
            raise HTTPException(422, "请补全支付供应商的必填配置。")
        if value and item["options"] and value not in item["options"]:
            raise HTTPException(422, "支付环境不正确。")
        if value and item["key"] in {"private_key", "public_key"}:
            try:
                rsa_key(value, private=item["key"] == "private_key")
            except (ValueError, TypeError):
                raise HTTPException(422, "RSA 密钥格式不正确，需使用至少 2048 位密钥。") from None
    if values.get("public_origin"):
        values["public_origin"] = https_url(values["public_origin"], origin_only=True)
    if values.get("api_base"):
        base = https_url(values["api_base"])
        for suffix in ("/submit.php", "/mapi.php", "/api.php"):
            if base.lower().endswith(suffix):
                base = base[: -len(suffix)]
        values["api_base"] = base
    if kind == "wxpay" and values.get("api_v3_key") and len(values["api_v3_key"].encode()) != 32:
        raise HTTPException(422, "API v3 密钥必须为 32 字节。")
    if (
        kind == "stripe"
        and values.get("secret_key")
        and not values["secret_key"].startswith(("sk_test_", "sk_live_"))
    ):
        raise HTTPException(422, "Stripe Secret Key 格式不正确。")
    return values
