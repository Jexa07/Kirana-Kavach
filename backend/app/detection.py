from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from statistics import mean
from typing import Any

from .data_store import calculate_average_daily_sales


def detect_settlement_leak(
    transactions: list[dict[str, Any]],
    *,
    as_of: datetime,
    normal_window_hours: float = 24.0,
) -> dict[str, Any] | None:
    pending = []

    for txn in transactions:
        if txn["status"] != "SUCCESS" or txn["settlement_status"] != "PENDING":
            continue

        txn_time = datetime.fromisoformat(txn["timestamp"])
        age_hours = (as_of - txn_time).total_seconds() / 3600
        if age_hours > normal_window_hours:
            pending.append(
                {
                    "transaction_id": txn["transaction_id"],
                    "amount": float(txn["amount"]),
                    "age_hours": round(age_hours, 1),
                    "utr_reference": txn.get("utr_reference"),
                    "timestamp": txn["timestamp"],
                }
            )

    if not pending:
        return None

    pending_amount = sum(item["amount"] for item in pending)
    avg_daily_sales = calculate_average_daily_sales(transactions)
    days_of_sales = pending_amount / avg_daily_sales if avg_daily_sales else 0.0

    return {
        "type": "settlement_leak",
        "severity": "high" if days_of_sales >= 0.5 else "medium",
        "pending_transaction_count": len(pending),
        "pending_amount": round(pending_amount, 2),
        "average_daily_sales": round(avg_daily_sales, 2),
        "days_of_sales_stuck": round(days_of_sales, 2),
        "transactions": pending,
        "rule": f"successful settlement pending > {normal_window_hours:.0f}h",
    }


def detect_customer_frequency_drop(
    transactions: list[dict[str, Any]],
    *,
    as_of: datetime,
    minimum_purchases: int = 3,
) -> list[dict[str, Any]]:
    from collections import Counter

    by_customer: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for txn in transactions:
        customer_id = txn.get("customer_id")
        if txn.get("status") != "SUCCESS" or not customer_id:
            continue
        by_customer[customer_id].append(txn)

    leaks = []
    for customer_id, cust_txns in by_customer.items():
        cust_txns.sort(key=lambda t: t["timestamp"])
        timestamps = [datetime.fromisoformat(t["timestamp"]) for t in cust_txns]
        if len(timestamps) < minimum_purchases:
            continue

        gaps = [
            (timestamps[i] - timestamps[i - 1]).total_seconds() / 86400
            for i in range(1, len(timestamps))
        ]
        baseline_gaps = gaps[:-1]
        if not baseline_gaps:
            continue

        normal_gap = mean(baseline_gaps)
        current_gap = (as_of - timestamps[-1]).total_seconds() / 86400

        if normal_gap > 0 and current_gap > 2 * normal_gap:
            total_purchases = len(cust_txns)
            amounts = [float(t["amount"]) for t in cust_txns]
            total_spent = round(sum(amounts), 2)
            average_ticket = round(total_spent / total_purchases, 2)

            mode_counts = Counter(t.get("payment_mode", "UPI") for t in cust_txns)
            preferred_payment_mode = (
                mode_counts.most_common(1)[0][0] if mode_counts else "UPI"
            )

            descending_txns = sorted(
                cust_txns, key=lambda t: t["timestamp"], reverse=True
            )
            recent_transactions = [
                {
                    "transaction_id": t["transaction_id"],
                    "amount": float(t["amount"]),
                    "timestamp": t["timestamp"],
                    "payment_mode": t.get("payment_mode", "UPI"),
                }
                for t in descending_txns[:5]
            ]

            leaks.append(
                {
                    "type": "customer_frequency_drop",
                    "customer_id": customer_id,
                    "normal_purchase_gap_days": round(normal_gap, 1),
                    "current_gap_days": round(current_gap, 1),
                    "ratio_vs_normal": round(current_gap / normal_gap, 1),
                    "last_purchase": timestamps[-1].isoformat(),
                    "total_purchases": total_purchases,
                    "total_spent": total_spent,
                    "average_ticket": average_ticket,
                    "preferred_payment_mode": preferred_payment_mode,
                    "recent_transactions": recent_transactions,
                    "rule": "current gap > 2x normal gap",
                }
            )

    leaks.sort(key=lambda x: x["ratio_vs_normal"], reverse=True)
    return leaks
