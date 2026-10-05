from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal
from urllib import error as urlerror
from urllib import request

from pydantic import BaseModel, ConfigDict, Field


ActionType = Literal[
    "CREATE_PAYTM_SUPPORT_CASE",
    "DRAFT_CUSTOMER_MESSAGE",
]


class ActionExecutionError(RuntimeError):
    """Raised when the configured action executor cannot complete an action."""


class ActionConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: ActionType
    approved: bool
    confirmation_source: Literal["text", "voice", "ui", "api"] = "api"
    message: str | None = None


class ActionExecutionResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    merchant_id: str
    action_type: ActionType
    status: str
    external_id: str | None = None
    outcome_note: str
    executed_at: str | None = None
    provider: str
    campaign_type: str | None = None
    customer_id: str | None = None
    message: str | None = None
    payment_link_reference: str | None = None
    confirmation_source: str | None = None
    channel: str | None = None
    message_sid: str | None = None
    recipient: str | None = None
    template_sid: str | None = None
    draft_message: str | None = None
    error_code: int | str | None = None


@dataclass(frozen=True)
class N8NConfig:
    provider: str = "mock"
    webhook_url: str | None = None
    webhook_secret: str | None = None
    timeout_seconds: float = 20.0

    @classmethod
    def from_env(cls) -> "N8NConfig":
        return cls(
            provider=os.getenv("N8N_EXECUTION_PROVIDER", "mock").lower(),
            webhook_url=os.getenv("N8N_WEBHOOK_URL") or None,
            webhook_secret=os.getenv("N8N_WEBHOOK_SECRET") or None,
            timeout_seconds=float(os.getenv("N8N_TIMEOUT", "20")),
        )


@dataclass(frozen=True)
class TwilioConfig:
    enabled: bool = False
    account_sid: str | None = None
    whatsapp_from: str | None = None
    whatsapp_to: str | None = None
    content_sid: str | None = None

    @classmethod
    def from_env(cls) -> "TwilioConfig":
        enabled_str = os.getenv("TWILIO_WHATSAPP_ENABLED", "false").lower()
        enabled = enabled_str in {"true", "1", "yes"}
        return cls(
            enabled=enabled,
            account_sid=os.getenv("TWILIO_ACCOUNT_SID") or None,
            whatsapp_from=os.getenv("TWILIO_WHATSAPP_FROM") or None,
            whatsapp_to=os.getenv("TWILIO_WHATSAPP_TO") or None,
            content_sid=os.getenv("TWILIO_CONTENT_SID") or None,
        )

    def validate_for_execution(self) -> None:
        if not self.enabled:
            return
        missing = []
        if not self.account_sid:
            missing.append("TWILIO_ACCOUNT_SID")
        if not self.whatsapp_from:
            missing.append("TWILIO_WHATSAPP_FROM")
        if not self.whatsapp_to:
            missing.append("TWILIO_WHATSAPP_TO")
        if not self.content_sid:
            missing.append("TWILIO_CONTENT_SID")
        if missing:
            raise ActionExecutionError(
                f"Missing required Twilio WhatsApp configuration: {', '.join(missing)}"
            )


def execute_action(
    *,
    merchant_id: str,
    action: dict[str, Any],
    confirmation_source: str,
    config: N8NConfig | None = None,
) -> ActionExecutionResult:
    config = config or N8NConfig.from_env()

    action_type = action.get("type")
    if action_type not in {
        "CREATE_PAYTM_SUPPORT_CASE",
        "DRAFT_CUSTOMER_MESSAGE",
    }:
        raise ActionExecutionError(
            f"Unsupported action type: {action_type}"
        )

    if config.provider == "mock":
        return _mock_execute(
            merchant_id=merchant_id,
            action=action,
        )

    if config.provider == "webhook":
        if not config.webhook_url:
            raise ActionExecutionError(
                "N8N_EXECUTION_PROVIDER=webhook requires N8N_WEBHOOK_URL"
            )

        return _call_n8n_webhook(
            merchant_id=merchant_id,
            action=action,
            confirmation_source=confirmation_source,
            config=config,
        )

    raise ActionExecutionError(
        f"Unknown N8N execution provider: {config.provider}"
    )


def _mock_execute(
    *,
    merchant_id: str,
    action: dict[str, Any],
) -> ActionExecutionResult:
    now = datetime.now(timezone.utc).isoformat()
    action_type = action["type"]
    payload = action.get("payload", {})

    if action_type == "CREATE_PAYTM_SUPPORT_CASE":
        transaction_ids = payload.get("transaction_ids", [])
        pending_amount = payload.get("pending_amount", 0)
        external_id = "KK-SUPPORT-DEMO"
        note = (
            "Demo Paytm support case prepared for "
            f"{len(transaction_ids)} transaction(s) totaling ₹{pending_amount:,.0f}."
        )
        status = "executed"
        return ActionExecutionResult(
            merchant_id=merchant_id,
            action_type=action_type,
            status=status,
            external_id=external_id,
            outcome_note=note,
            executed_at=now,
            provider="mock",
        )
    else:
        customer_id = str(payload.get("customer_id", "")).strip() or None
        message = str(payload.get("message", "")).strip() or None

        if payload.get("twilio_whatsapp_to"):
            to_num = str(payload.get("twilio_whatsapp_to"))
            masked_recipient = (
                to_num[:5] + "******" + to_num[-4:] if len(to_num) >= 9 else to_num
            )
            return ActionExecutionResult(
                merchant_id=merchant_id,
                action_type=action_type,
                status="queued",
                channel="whatsapp",
                provider="twilio",
                message_sid="SMmock123456789",
                external_id="SMmock123456789",
                customer_id=customer_id,
                campaign_type="customer_reactivation",
                recipient=masked_recipient,
                template_sid=payload.get("twilio_content_sid"),
                draft_message=message,
                message=message,
                payment_link_reference="KK-PAY-DEMO",
                outcome_note="WhatsApp message submitted to Twilio using the configured trial template.",
                executed_at=now,
                confirmation_source="ui",
            )

        external_id = "KK-REACT-DEMO"
        note = (
            "Customer reactivation pack prepared for merchant review; "
            "nothing was sent automatically."
        )
        return ActionExecutionResult(
            merchant_id=merchant_id,
            action_type=action_type,
            status="prepared",
            external_id=external_id,
            outcome_note=note,
            executed_at=now,
            provider="mock",
            campaign_type="customer_reactivation",
            customer_id=customer_id,
            message=message,
            payment_link_reference="KK-PAY-DEMO",
        )


def _call_n8n_webhook(
    *,
    merchant_id: str,
    action: dict[str, Any],
    confirmation_source: str,
    config: N8NConfig,
) -> ActionExecutionResult:
    body = json.dumps(
        {
            "merchant_id": merchant_id,
            "approved": True,
            "confirmation_source": confirmation_source,
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
            "action": action,
        },
        ensure_ascii=False,
    ).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "kirana-kavach/phase5",
    }
    if config.webhook_secret:
        headers["X-Kavach-Secret"] = config.webhook_secret

    req = request.Request(
        config.webhook_url,
        data=body,
        method="POST",
        headers=headers,
    )

    try:
        with request.urlopen(
            req,
            timeout=config.timeout_seconds,
        ) as response:
            response_body = response.read().decode("utf-8")
            status_code = response.status
    except (urlerror.URLError, TimeoutError) as exc:
        raise ActionExecutionError(
            f"n8n webhook request failed: {exc}"
        ) from exc

    if status_code < 200 or status_code >= 300:
        raise ActionExecutionError(
            f"n8n returned HTTP {status_code}"
        )

    try:
        payload = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise ActionExecutionError(
            "n8n returned a non-JSON response"
        ) from exc

    result = ActionExecutionResult.model_validate(
        {
            "provider": "n8n",
            **payload,
            "merchant_id": merchant_id,
            "action_type": action["type"],
        }
    )
    return result
