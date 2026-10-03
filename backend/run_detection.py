from datetime import datetime
from app.data_store import get_transactions
from app.detection import detect_customer_frequency_drop, detect_settlement_leak

MERCHANT_ID = "M1001"
AS_OF = datetime.fromisoformat("2026-10-02T12:00:00")

txns = get_transactions(MERCHANT_ID)
settlement = detect_settlement_leak(txns, as_of=AS_OF)
customer = detect_customer_frequency_drop(txns, as_of=AS_OF)

print("=== KIRANA KAVACH | PHASE 1 DETECTION ===")
print(f"Merchant: {MERCHANT_ID}")
print(f"As of: {AS_OF.isoformat()}")
print("\n[Settlement leak]")
print(settlement)
print("\n[Customer frequency leaks]")
for leak in customer:
    print(leak)
