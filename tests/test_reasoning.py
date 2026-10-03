from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.data_store import get_merchant, get_transactions
from app.detection import detect_customer_frequency_drop, detect_settlement_leak
from app.reasoning import ReasoningConfig, ReasoningOutput, reason_about_leak

AS_OF = datetime.fromisoformat("2026-10-02T12:00:00")


def test_settlement_reasoning_has_one_action_and_requires_confirmation():
    merchant = get_merchant("M1001")
    leak = detect_settlement_leak(get_transactions("M1001"), as_of=AS_OF)
    result = reason_about_leak(
        merchant=merchant,
        leak=leak,
        config=ReasoningConfig(provider="mock"),
    )

    assert isinstance(result, ReasoningOutput)
    assert result.action.type == "CREATE_PAYTM_SUPPORT_CASE"
    assert result.action.requires_confirmation is True
    assert result.recommendation


def test_customer_reasoning_does_not_auto_send_message():
    merchant = get_merchant("M1001")
    leak = detect_customer_frequency_drop(
        get_transactions("M1001"), as_of=AS_OF
    )[0]
    result = reason_about_leak(
        merchant=merchant,
        leak=leak,
        config=ReasoningConfig(provider="mock"),
    )

    assert result.action.type == "DRAFT_CUSTOMER_MESSAGE"
    assert result.action.requires_confirmation is True
    assert result.action.payload["channel"] == "merchant_review"
    assert result.action.payload["campaign_type"] == "customer_reactivation"
    assert result.action.payload["payment_link_mode"] == "demo_only"
    assert "send automatically" not in result.recommendation.lower()


def test_unknown_provider_fails_fast():
    merchant = get_merchant("M1001")
    leak = detect_settlement_leak(get_transactions("M1001"), as_of=AS_OF)
    try:
        reason_about_leak(
            merchant=merchant,
            leak=leak,
            config=ReasoningConfig(provider="unknown"),
        )
    except ValueError as exc:
        assert "Unknown reasoning provider" in str(exc)
    else:
        raise AssertionError("Expected unknown provider to fail")


def test_reasoning_accepts_memory_context():
    merchant = get_merchant("M1001")
    leak = detect_settlement_leak(get_transactions("M1001"), as_of=AS_OF)
    result = reason_about_leak(
        merchant=merchant,
        leak=leak,
        config=ReasoningConfig(provider="mock"),
        memory_context=[
            "MERCHANT PROFILE preferred_language: hi",
            "Previous settlement issue was handled through Paytm support.",
        ],
    )

    assert result.action.type == "CREATE_PAYTM_SUPPORT_CASE"
    assert result.action.requires_confirmation is True


def test_customer_action_requires_message_payload():
    merchant = get_merchant("M1001")
    leak = detect_customer_frequency_drop(
        get_transactions("M1001"), as_of=AS_OF
    )[0]
    result = reason_about_leak(
        merchant=merchant,
        leak=leak,
        config=ReasoningConfig(provider="mock"),
    )

    assert result.action.payload["customer_id"] == "C1001"
    assert result.action.payload["channel"] == "merchant_review"
    assert isinstance(result.action.payload["message"], str)
    assert result.action.payload["message"].strip()
