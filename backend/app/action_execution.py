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


class ActionExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    merchant_id: str
    action_type: ActionType
    status: Literal["executed", "prepared", "rejected"]
    external_id: str | None = None
    outcome_note: str
    executed_at: str | None = None
    provider: str
    campaign_type: str | None = None
    customer_id: str | None = None
    message: str | None = None
    payment_link_reference: str | None = None
    confirmation_source: str | None = None


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
        status: Literal["executed", "prepared"] = "executed"
    else:
        external_id = "KK-REACT-DEMO"
        customer_id = str(payload.get("customer_id", "")).strip() or None
        message = str(payload.get("message", "")).strip() or None
        note = (
            "Customer reactivation pack prepared for merchant review; "
            "nothing was sent automatically."
        )
        status = "prepared"

    return ActionExecutionResult(
        merchant_id=merchant_id,
        action_type=action_type,
        status=status,
        external_id=external_id,
        outcome_note=note,
        executed_at=now,
        provider="mock",
        campaign_type=("customer_reactivation" if action_type == "DRAFT_CUSTOMER_MESSAGE" else None),
        customer_id=(customer_id if action_type == "DRAFT_CUSTOMER_MESSAGE" else None),
        message=(message if action_type == "DRAFT_CUSTOMER_MESSAGE" else None),
        payment_link_reference=(
            "KK-PAY-DEMO" if action_type == "DRAFT_CUSTOMER_MESSAGE" else None
        ),
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
            **payload,
            "merchant_id": merchant_id,
            "action_type": action["type"],
            "provider": "n8n",
        }
    )
    return result
