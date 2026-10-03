from dataclasses import dataclass
from datetime import datetime
from typing import Literal

PaymentMode = Literal["UPI", "QR", "CARD", "WALLET"]
TxnStatus = Literal["SUCCESS", "FAILED", "PENDING"]
SettlementStatus = Literal["SETTLED", "PENDING"]

@dataclass(frozen=True)
class Transaction:
    transaction_id: str
    merchant_id: str
    customer_id: str | None
    amount: float
    status: TxnStatus
    settlement_status: SettlementStatus
    utr_reference: str | None
    timestamp: datetime
    settlement_timestamp: datetime | None
    payment_mode: PaymentMode
