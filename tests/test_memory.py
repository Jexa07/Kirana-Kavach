from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import asyncio

from app.memory import (
    InMemoryStore,
    action_outcome_memory,
    leak_proposal_memory,
    merchant_profile_memory,
)
from app.data_store import get_merchant
from app.detection import detect_settlement_leak
from app.data_store import get_transactions
from datetime import datetime


AS_OF = datetime.fromisoformat("2026-10-02T12:00:00")


def test_in_memory_store_roundtrip():
    async def run():
        store = InMemoryStore()
        await store.remember("M1001", ["Merchant prefers Hindi.", "A settlement was delayed."])
        results = await store.recall("M1001", "settlement")
        assert results == ["A settlement was delayed."]

    asyncio.run(run())


def test_memory_record_builders_contain_required_context():
    merchant = get_merchant("M1001")
    leak = detect_settlement_leak(get_transactions("M1001"), as_of=AS_OF)

    profile = merchant_profile_memory(merchant)
    proposal = leak_proposal_memory(
        merchant=merchant,
        leak=leak,
        reasoning={
            "explanation": "Settlement is delayed.",
            "recommendation": "Prepare a support case.",
            "action": {
                "type": "CREATE_PAYTM_SUPPORT_CASE",
                "payload": {"transaction_ids": ["TXN1021"]},
            },
        },
    )
    outcome = action_outcome_memory(
        merchant_id="M1001",
        action_type="CREATE_PAYTM_SUPPORT_CASE",
        approved=True,
        status="executed",
        outcome_note="Support case created.",
    )

    assert "merchant_id: M1001" in profile
    assert "leak_type: settlement_leak" in proposal
    assert "status: proposed" in proposal
    assert "merchant_approval: approved" in outcome
    assert "status: executed" in outcome


def test_merchant_average_daily_sales_is_transaction_derived():
    merchant = get_merchant("M1001")
    transactions = get_transactions("M1001")

    successful_days = {
        transaction["timestamp"][:10]
        for transaction in transactions
        if transaction["status"] == "SUCCESS"
    }

    successful_total = sum(
        transaction["amount"]
        for transaction in transactions
        if transaction["status"] == "SUCCESS"
    )

    expected = round(successful_total / len(successful_days), 2)
    assert merchant["average_daily_sales"] == expected


def test_cognee_memory_store_recall_cache_and_invalidation():
    from unittest.mock import AsyncMock, MagicMock
    from app.memory import CogneeMemoryStore, MemoryConfig

    async def run():
        config = MemoryConfig(provider="cognee", top_k=2)
        store = CogneeMemoryStore(config)

        mock_cognee = MagicMock()
        mock_cognee.recall = AsyncMock(side_effect=[
            ["Record 1"],
            ["Query B Record"],
            ["Other Merchant Record"],
            ["Record 2 (Fresh After Remember)"],
        ])
        mock_cognee.remember = AsyncMock()
        store._cognee = mock_cognee
        store._configured = True

        # 1. Cache miss -> Calls cognee.recall
        res1 = await store.recall("M1001", "merchant outcomes")
        assert res1 == ["Record 1"]
        assert mock_cognee.recall.call_count == 1

        # 2. Cache hit (same merchant, same query) -> cognee.recall NOT called again
        res2 = await store.recall("M1001", "merchant outcomes")
        assert res2 == ["Record 1"]
        assert mock_cognee.recall.call_count == 1

        # 3. Different query -> Cache miss -> calls cognee.recall
        res_q2 = await store.recall("M1001", "settlement leaks")
        assert res_q2 == ["Query B Record"]
        assert mock_cognee.recall.call_count == 2

        # 4. Different merchant -> Cache miss -> calls cognee.recall
        res_m2 = await store.recall("M1002", "merchant outcomes")
        assert res_m2 == ["Other Merchant Record"]
        assert mock_cognee.recall.call_count == 3

        # 5. remember() for M1001 -> Invalidates M1001 recall cache
        await store.remember("M1001", ["New Action Outcome"])
        assert mock_cognee.remember.call_count == 1

        # 6. Next recall for M1001 -> Cache miss due to invalidation -> calls cognee.recall again
        res3 = await store.recall("M1001", "merchant outcomes")
        assert res3 == ["Record 2 (Fresh After Remember)"]
        assert mock_cognee.recall.call_count == 4

    asyncio.run(run())


def test_cognee_memory_store_ttl_expiry():
    from unittest.mock import AsyncMock, MagicMock
    from app.memory import CogneeMemoryStore, MemoryConfig

    async def run():
        config = MemoryConfig(provider="cognee", top_k=2)
        store = CogneeMemoryStore(config)
        store._ttl_seconds = 0.05  # Short 50ms TTL for testing

        mock_cognee = MagicMock()
        mock_cognee.recall = AsyncMock(side_effect=[
            ["Initial"],
            ["After TTL Expiry"],
        ])
        store._cognee = mock_cognee
        store._configured = True

        res1 = await store.recall("M1001", "query")
        assert res1 == ["Initial"]
        assert mock_cognee.recall.call_count == 1

        # Wait past TTL
        await asyncio.sleep(0.08)

        res2 = await store.recall("M1001", "query")
        assert res2 == ["After TTL Expiry"]
        assert mock_cognee.recall.call_count == 2

    asyncio.run(run())

