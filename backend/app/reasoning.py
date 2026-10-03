from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Literal
from urllib import error as urlerror
from urllib import request

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["CREATE_PAYTM_SUPPORT_CASE", "DRAFT_CUSTOMER_MESSAGE"]
    description: str = Field(min_length=1)
    requires_confirmation: bool = True
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_payload(self) -> "Action":
        if self.type == "CREATE_PAYTM_SUPPORT_CASE":
            if "transaction_ids" not in self.payload:
                raise ValueError(
                    "CREATE_PAYTM_SUPPORT_CASE requires transaction_ids"
                )
            if "pending_amount" not in self.payload:
                raise ValueError(
                    "CREATE_PAYTM_SUPPORT_CASE requires pending_amount"
                )

        if self.type == "DRAFT_CUSTOMER_MESSAGE":
            if "customer_id" not in self.payload:
                raise ValueError(
                    "DRAFT_CUSTOMER_MESSAGE requires customer_id"
                )
            if self.payload.get("channel") != "merchant_review":
                raise ValueError(
                    "DRAFT_CUSTOMER_MESSAGE channel must be 'merchant_review'"
                )
            message = self.payload.get("message")
            if not isinstance(message, str) or not message.strip():
                raise ValueError(
                    "DRAFT_CUSTOMER_MESSAGE requires a non-empty message"
                )

        return self


class ReasoningOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explanation: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)
    action: Action

    @field_validator("explanation", "recommendation")
    @classmethod
    def single_line_text(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("text must not be empty")
        return value


@dataclass(frozen=True)
class ReasoningConfig:
    provider: str = "mock"
    model: str = "sarvam-105b"
    timeout_seconds: float = 20.0

    @classmethod
    def from_env(cls) -> "ReasoningConfig":
        return cls(
            provider=os.getenv("KAVACH_REASONING_PROVIDER", "mock").lower(),
            model=os.getenv("SARVAM_MODEL", "sarvam-105b"),
            timeout_seconds=float(os.getenv("KAVACH_REASONING_TIMEOUT", "20")),
        )


def _safe_language_name(language: str | None) -> str:
    aliases = {"hi": "Hindi", "mr": "Marathi", "en": "English"}
    return aliases.get((language or "en").lower(), language or "English")


def _build_system_prompt() -> str:
    return """You are Kirana Kavach's narrow business reasoning layer.

Your only job is to turn one already-detected merchant leak into:
1) one factual explanation in one sentence,
2) one specific recommendation in one sentence,
3) one approved-action contract.

Rules:
- Do not invent transactions, customers, causes, amounts, policies, inventory, discounts, competitor information, or external events.
- Treat detected facts as facts and unknown causes as unknown. You may say 'this may indicate' when the data does not prove a cause.
- Never recommend a discount.
- Never claim to automatically message a customer.
- For customer-frequency leaks, the allowed action is only to draft a message for the merchant to review/send themselves.
- For settlement leaks, the allowed action is to prepare a Paytm support case; it still requires merchant confirmation before execution.
- Every action must have "requires_confirmation": true.
- Keep explanation and recommendation short and spoken-language friendly.
- Return ONLY valid JSON matching this exact shape:
{
  "explanation": "...",
  "recommendation": "...",
  "action": {
    "type": "CREATE_PAYTM_SUPPORT_CASE" | "DRAFT_CUSTOMER_MESSAGE",
    "description": "...",
    "requires_confirmation": true,
    "payload": {}
  }
}

For CREATE_PAYTM_SUPPORT_CASE:
- payload must contain:
  "transaction_ids": [...],
  "pending_amount": number

For DRAFT_CUSTOMER_MESSAGE:
- payload must contain:
  "customer_id": "...",
  "channel": "merchant_review",
  "message": "actual message text for the merchant to review and send"

Do not put the customer message only inside the recommendation.
The actual message must be present in payload.message.
"""


def build_prompt(
    *,
    merchant: dict[str, Any],
    leak: dict[str, Any],
    memory_context: list[str] | None = None,
) -> list[dict[str, str]]:
    language = _safe_language_name(merchant.get("preferred_language"))
    context = {
        "merchant": {
            "merchant_id": merchant.get("merchant_id"),
            "merchant_name": merchant.get("merchant_name"),
            "owner_name": merchant.get("owner_name"),
            "preferred_language": language,
            "average_daily_sales": merchant.get("average_daily_sales"),
            "city": merchant.get("city"),
        },
        "detected_leak": leak,
    }
    memory_text = memory_context or []
    user_prompt = (
        f"Explain this detected leak to the merchant in {language}. "
        "Do not add facts beyond the detected leak. You may use relevant remembered merchant context, "
        "but do not invent anything that is not explicitly present in the memory. "
        "Choose the one allowed action that fits the leak.\n\n"
        + json.dumps(context, ensure_ascii=False, indent=2)
        + "\n\nREMEMBERED MERCHANT CONTEXT:\n"
        + ("\n---\n".join(memory_text) if memory_text else "No prior memory found.")
    )
    return [
        {"role": "system", "content": _build_system_prompt()},
        {"role": "user", "content": user_prompt},
    ]


def _mock_reasoning(
    merchant: dict[str, Any],
    leak: dict[str, Any],
) -> ReasoningOutput:
    language = (merchant.get("preferred_language") or "en").lower()

    if leak["type"] == "settlement_leak":
        amount = f"₹{leak['pending_amount']:,.0f}"
        days = leak["days_of_sales_stuck"]
        age = max(item["age_hours"] for item in leak["transactions"])
        transaction_ids = [
            transaction["transaction_id"]
            for transaction in leak["transactions"]
        ]

        if language == "hi":
            return ReasoningOutput(
                explanation=(
                    f"{amount} का एक सफल पेमेंट {age:.1f} घंटे से सेटल नहीं हुआ है, "
                    f"जो आपकी सामान्य बिक्री के लगभग {days:.1f} दिनों के बराबर है।"
                ),
                recommendation=(
                    "मेरी सलाह है कि इस लंबित सेटलमेंट के लिए Paytm सपोर्ट केस तैयार करें।"
                ),
                action=Action(
                    type="CREATE_PAYTM_SUPPORT_CASE",
                    description=(
                        "Prepare a Paytm support case for the delayed settlement."
                    ),
                    payload={
                        "transaction_ids": transaction_ids,
                        "pending_amount": leak["pending_amount"],
                    },
                ),
            )

        return ReasoningOutput(
            explanation=(
                f"{amount} from {leak['pending_transaction_count']} successful payment(s) "
                f"has remained unsettled for up to {age:.1f} hours, equal to about "
                f"{days:.1f} days of your usual sales."
            ),
            recommendation=(
                "I recommend preparing a Paytm support case for this delayed settlement."
            ),
            action=Action(
                type="CREATE_PAYTM_SUPPORT_CASE",
                description=(
                    "Prepare a Paytm support case for the delayed settlement."
                ),
                payload={
                    "transaction_ids": transaction_ids,
                    "pending_amount": leak["pending_amount"],
                },
            ),
        )

    if leak["type"] == "customer_frequency_drop":
        customer_id = leak["customer_id"]
        normal = leak["normal_purchase_gap_days"]
        current = leak["current_gap_days"]

        if language == "hi":
            message = (
                "नमस्ते, काफी समय से आपसे मुलाकात नहीं हुई। "
                "जब भी सुविधा हो, दुकान पर ज़रूर आइए।"
            )
            return ReasoningOutput(
                explanation=(
                    f"ग्राहक {customer_id} आमतौर पर लगभग हर {normal:.1f} दिन में खरीदते थे, "
                    f"लेकिन इस बार {current:.1f} दिन से कोई खरीद नहीं हुई है।"
                ),
                recommendation=(
                    "मेरी सलाह है कि मैं इस नियमित ग्राहक के लिए एक छोटा ग्राहक-वापसी ऑफ़र तैयार करूँ, "
                    "जिसे आप पहले देख कर खुद भेज सकें।"
                ),
                action=Action(
                    type="DRAFT_CUSTOMER_MESSAGE",
                    description=(
                        "Draft a reminder for the merchant to review and send themselves."
                    ),
                    payload={
                        "customer_id": customer_id,
                        "channel": "merchant_review",
                        "message": message,
                        "campaign_type": "customer_reactivation",
                        "payment_link_mode": "demo_only",
                    },
                ),
            )

        message = (
            "Hi, we haven't seen you in a while. "
            "Please visit the shop whenever it is convenient for you."
        )
        return ReasoningOutput(
            explanation=(
                f"Customer {customer_id} usually buys about every {normal:.1f} days, "
                f"but has now gone {current:.1f} days without a purchase."
            ),
            recommendation=(
                "I recommend preparing a small customer reactivation offer for you to review and send yourself."
            ),
            action=Action(
                type="DRAFT_CUSTOMER_MESSAGE",
                description=(
                    "Draft a reminder for the merchant to review and send themselves."
                ),
                payload={
                    "customer_id": customer_id,
                    "channel": "merchant_review",
                    "message": message,
                },
            ),
        )

    raise ValueError(f"Unsupported leak type: {leak.get('type')}")


def _call_sarvam(
    *,
    messages: list[dict[str, str]],
    config: ReasoningConfig,
    api_key: str,
) -> ReasoningOutput:
    payload = json.dumps(
        {
            "model": config.model,
            "messages": messages,
            "max_tokens": 300,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
    ).encode("utf-8")

    req = request.Request(
        "https://api.sarvam.ai/v1/chat/completions",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "api-subscription-key": api_key,
        },
    )
    try:
        with request.urlopen(req, timeout=config.timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urlerror.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Sarvam reasoning request failed: {exc}") from exc

    try:
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Sarvam returned an invalid reasoning response") from exc

    try:
        return ReasoningOutput.model_validate(parsed)
    except ValidationError as exc:
        raise RuntimeError(f"Sarvam reasoning failed schema validation: {exc}") from exc


def reason_about_leak(
    *,
    merchant: dict[str, Any],
    leak: dict[str, Any],
    config: ReasoningConfig | None = None,
    memory_context: list[str] | None = None,
) -> ReasoningOutput:
    config = config or ReasoningConfig.from_env()

    if config.provider == "mock":
        return _mock_reasoning(merchant, leak)

    if config.provider == "sarvam":
        api_key = os.getenv("SARVAM_API_KEY")
        if not api_key:
            raise RuntimeError(
                "KAVACH_REASONING_PROVIDER=sarvam requires SARVAM_API_KEY"
            )
        return _call_sarvam(
            messages=build_prompt(
                merchant=merchant,
                leak=leak,
                memory_context=memory_context,
            ),
            config=config,
            api_key=api_key,
        )

    raise ValueError(f"Unknown reasoning provider: {config.provider}")
