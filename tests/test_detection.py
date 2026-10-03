from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.data_store import get_transactions
from app.detection import detect_customer_frequency_drop, detect_settlement_leak

AS_OF = datetime.fromisoformat("2026-10-02T12:00:00")


def test_settlement_leak_detected():
    txns = get_transactions("M1001")
    leak = detect_settlement_leak(txns, as_of=AS_OF)
    assert leak is not None
    assert leak["pending_transaction_count"] == 1
    assert leak["pending_amount"] == 1240.0
    assert leak["transactions"][0]["transaction_id"] == "TXN1021"


def test_customer_frequency_drop_detected():
    txns = get_transactions("M1001")
    leaks = detect_customer_frequency_drop(txns, as_of=AS_OF)
    ids = {item["customer_id"] for item in leaks}
    assert "C1001" in ids


def test_other_merchant_data_is_isolated():
    txns = get_transactions("M1001")
    assert all(t["merchant_id"] == "M1001" for t in txns)
