from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.action_execution import (
    ActionExecutionError,
    N8NConfig,
    execute_action,
)


def test_mock_support_case_execution():
    result = execute_action(
        merchant_id="M1001",
        action={
            "type": "CREATE_PAYTM_SUPPORT_CASE",
            "description": "Prepare a support case.",
            "requires_confirmation": True,
            "payload": {
                "transaction_ids": ["TXN1021"],
                "pending_amount": 1240,
            },
        },
        confirmation_source="ui",
        config=N8NConfig(provider="mock"),
    )

    assert result.status == "executed"
    assert result.external_id == "KK-SUPPORT-DEMO"
    assert result.provider == "mock"


def test_mock_customer_draft_never_sends():
    result = execute_action(
        merchant_id="M1001",
        action={
            "type": "DRAFT_CUSTOMER_MESSAGE",
            "description": "Draft a reminder.",
            "requires_confirmation": True,
            "payload": {
                "customer_id": "C1001",
                "channel": "merchant_review",
                "message": "नमस्ते, काफी समय से आपसे मुलाकात नहीं हुई।",
            },
        },
        confirmation_source="ui",
        config=N8NConfig(provider="mock"),
    )

    assert result.status == "prepared"
    assert result.external_id == "KK-REACT-DEMO"
    assert result.campaign_type == "customer_reactivation"
    assert result.customer_id == "C1001"
    assert result.message
    assert result.payment_link_reference == "KK-PAY-DEMO"
    assert "nothing was sent" in result.outcome_note.lower()


def test_unknown_n8n_provider_fails():
    try:
        execute_action(
            merchant_id="M1001",
            action={
                "type": "CREATE_PAYTM_SUPPORT_CASE",
                "payload": {
                    "transaction_ids": ["TXN1021"],
                    "pending_amount": 1240,
                },
            },
            confirmation_source="ui",
            config=N8NConfig(provider="unknown"),
        )
    except ActionExecutionError as exc:
        assert "Unknown N8N execution provider" in str(exc)
    else:
        raise AssertionError("Expected unknown provider to fail")


def test_customer_reactivation_payload_contains_growth_metadata():
    result = execute_action(
        merchant_id="M1001",
        action={
            "type": "DRAFT_CUSTOMER_MESSAGE",
            "description": "Prepare a customer reactivation offer.",
            "requires_confirmation": True,
            "payload": {
                "customer_id": "C1001",
                "channel": "merchant_review",
                "message": "नमस्ते, काफी समय से आपसे मुलाकात नहीं हुई।",
                "campaign_type": "customer_reactivation",
                "payment_link_mode": "demo_only",
            },
        },
        confirmation_source="voice",
        config=N8NConfig(provider="mock"),
    )

    assert result.campaign_type == "customer_reactivation"
    assert result.customer_id == "C1001"
    assert result.payment_link_reference == "KK-PAY-DEMO"
