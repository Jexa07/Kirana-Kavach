from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "paytm_mock.json"


def load_data() -> dict[str, Any]:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Mock data not found: {DATA_PATH}")
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def get_transactions(merchant_id: str) -> list[dict[str, Any]]:
    data = load_data()
    return [
        transaction
        for transaction in data["transactions"]
        if transaction["merchant_id"] == merchant_id
    ]


def calculate_average_daily_sales(
    transactions: list[dict[str, Any]],
) -> float:
    """Calculate successful average daily sales from transaction data.

    Transaction history is the single source of truth for this metric.
    """
    successful_by_day: dict[str, float] = {}

    for transaction in transactions:
        if transaction["status"] != "SUCCESS":
            continue
        day = transaction["timestamp"][:10]
        successful_by_day[day] = successful_by_day.get(day, 0.0) + float(
            transaction["amount"]
        )

    daily_sales = list(successful_by_day.values())
    if not daily_sales:
        return 0.0

    return round(mean(daily_sales), 2)


def get_merchant(merchant_id: str) -> dict[str, Any]:
    data = load_data()
    for merchant in data["merchants"]:
        if merchant["merchant_id"] == merchant_id:
            merchant_data = dict(merchant)
            merchant_data["average_daily_sales"] = calculate_average_daily_sales(
                get_transactions(merchant_id)
            )
            return merchant_data
    raise KeyError(f"Unknown merchant: {merchant_id}")
