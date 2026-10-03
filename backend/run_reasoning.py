from datetime import datetime

from app.data_store import get_merchant, get_transactions
from app.detection import detect_customer_frequency_drop, detect_settlement_leak
from app.reasoning import ReasoningConfig, reason_about_leak

MERCHANT_ID = "M1001"
AS_OF = datetime.fromisoformat("2026-10-02T12:00:00")

merchant = get_merchant(MERCHANT_ID)
txns = get_transactions(MERCHANT_ID)

leaks = []
settlement = detect_settlement_leak(txns, as_of=AS_OF)
if settlement:
    leaks.append(settlement)
leaks.extend(detect_customer_frequency_drop(txns, as_of=AS_OF))

config = ReasoningConfig.from_env()
print("=== KIRANA KAVACH | PHASE 2 REASONING ===")
print(f"Provider: {config.provider}")
for leak in leaks:
    result = reason_about_leak(merchant=merchant, leak=leak, config=config)
    print(f"\n[{leak['type']}]")
    print("Explanation:", result.explanation)
    print("Recommendation:", result.recommendation)
    print("Action:", result.action.model_dump())
