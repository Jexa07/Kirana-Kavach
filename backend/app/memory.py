from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


import time


@dataclass(frozen=True)
class MemoryConfig:
    provider: str = "cognee"
    dataset_prefix: str = "kirana_kavach_v2"
    data_root: Path = Path("data") / "cognee"
    system_root: Path = Path("data") / "cognee_system"
    top_k: int = 2

    @classmethod
    def from_env(cls) -> "MemoryConfig":
        return cls(
            provider=os.getenv("KAVACH_MEMORY_PROVIDER", "cognee").lower(),
            dataset_prefix=os.getenv("COGNEE_DATASET_PREFIX", "kirana_kavach_v2"),
            data_root=Path(os.getenv("COGNEE_DATA_ROOT", "data/cognee")),
            system_root=Path(
                os.getenv("COGNEE_SYSTEM_ROOT", "data/cognee_system")
            ),
            top_k=int(os.getenv("COGNEE_TOP_K", "2")),
        )


class MemoryStore(Protocol):
    async def remember(self, merchant_id: str, records: list[str]) -> None:
        ...

    async def recall(self, merchant_id: str, query: str) -> list[str]:
        ...

    def invalidate_cache(self, merchant_id: str | None = None) -> None:
        ...


@dataclass
class InMemoryStore:
    """Small deterministic memory used by tests and local fallback development."""

    records: dict[str, list[str]] = field(default_factory=dict)

    def invalidate_cache(self, merchant_id: str | None = None) -> None:
        pass

    async def remember(self, merchant_id: str, records: list[str]) -> None:
        bucket = self.records.setdefault(merchant_id, [])
        for record in records:
            if record not in bucket:
                bucket.append(record)

    async def recall(self, merchant_id: str, query: str) -> list[str]:
        bucket = self.records.get(merchant_id, [])
        if not query.strip():
            return bucket[-2:]

        terms = [term.lower() for term in query.split() if term.strip()]
        ranked: list[tuple[int, str]] = []
        for record in bucket:
            lowered = record.lower()
            score = sum(1 for term in terms if term in lowered)
            if score:
                ranked.append((score, record))

        ranked.sort(key=lambda item: item[0], reverse=True)
        return [record for _, record in ranked[:2]]


@dataclass
class _CacheEntry:
    timestamp: float
    results: list[str]


class CogneeMemoryStore:
    def __init__(self, config: MemoryConfig):
        self.config = config
        self._cognee: Any | None = None
        self._configured = False
        self._recall_cache: dict[str, dict[str, _CacheEntry]] = {}
        self._cache_lock = asyncio.Lock()
        self._ttl_seconds: float = 60.0

    def invalidate_cache(self, merchant_id: str | None = None) -> None:
        """Invalidate recall cache for a specific merchant, or all merchants."""
        if merchant_id:
            self._recall_cache.pop(merchant_id, None)
        else:
            self._recall_cache.clear()

    def _dataset_name(self, merchant_id: str) -> str:
        return f"{self.config.dataset_prefix}_{merchant_id}"

    async def _get_cognee(self) -> Any:
        if self._cognee is None:
            try:
                import cognee
            except ImportError as exc:
                raise RuntimeError(
                    "Cognee is not installed. Run: pip install \"cognee[gliner]\""
                ) from exc

            self._cognee = cognee

        if not self._configured:
            self.config.data_root.mkdir(parents=True, exist_ok=True)
            self.config.system_root.mkdir(parents=True, exist_ok=True)

            # Cognee's local defaults use file-based storage. We keep its data
            # inside this project so the demo remains self-contained.
            self._cognee.config.data_root_directory(
                str(self.config.data_root.resolve())
            )
            self._cognee.config.system_root_directory(
                str(self.config.system_root.resolve())
            )
            self._configured = True

        return self._cognee

    async def remember(self, merchant_id: str, records: list[str]) -> None:
        cognee = await self._get_cognee()
        if not records:
            return

        await cognee.remember(
            records,
            dataset_name=self._dataset_name(merchant_id),
            self_improvement=False,
        )

        async with self._cache_lock:
            self.invalidate_cache(merchant_id)

    async def recall(self, merchant_id: str, query: str) -> list[str]:
        now = time.monotonic()
        async with self._cache_lock:
            merchant_cache = self._recall_cache.get(merchant_id, {})
            entry = merchant_cache.get(query)
            if entry and (now - entry.timestamp) < self._ttl_seconds:
                return list(entry.results)

        cognee = await self._get_cognee()

        results = await cognee.recall(
            query,
            datasets=[self._dataset_name(merchant_id)],
            top_k=self.config.top_k,
            query_type=cognee.SearchType.CHUNKS,
        )

        extracted = [_result_to_text(result) for result in results]

        async with self._cache_lock:
            merchant_cache = self._recall_cache.setdefault(merchant_id, {})
            merchant_cache[query] = _CacheEntry(
                timestamp=time.monotonic(),
                results=extracted,
            )

        return extracted


def _result_to_text(result: Any) -> str:
    """Convert a Cognee result to only the useful stored text."""
    if isinstance(result, str):
        return result.strip()

    text = getattr(result, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    raw = getattr(result, "raw", None)
    if isinstance(raw, dict):
        raw_text = raw.get("text")
        if isinstance(raw_text, str) and raw_text.strip():
            return raw_text.strip()

    if isinstance(result, dict):
        for key in ("text", "content", "chunk", "source"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        search_result = result.get("search_result")
        if isinstance(search_result, str) and search_result.strip():
            return search_result.strip()

        try:
            return json.dumps(result, ensure_ascii=False, default=str)
        except TypeError:
            return str(result)

    return str(result)


def create_memory_store(config: MemoryConfig | None = None) -> MemoryStore:
    config = config or MemoryConfig.from_env()

    if config.provider == "cognee":
        return CogneeMemoryStore(config)

    if config.provider == "mock":
        return InMemoryStore()

    raise ValueError(
        f"Unknown memory provider: {config.provider}. "
        "Use 'cognee' or 'mock'."
    )


import asyncio

_SEEDED_MERCHANTS: set[str] = set()
_SEED_LOCK = asyncio.Lock()


def reset_seeded_merchants() -> None:
    """Clear the set of seeded merchants (useful for unit tests)."""
    _SEEDED_MERCHANTS.clear()


async def ensure_merchant_profile_seeded(
    memory_store: MemoryStore,
    merchant: dict[str, Any],
) -> bool:
    """Guarantee that the static merchant profile is stored in memory AT MOST ONCE.

    Returns True if seeding was performed, or False if already seeded.
    """
    merchant_id = merchant.get("merchant_id")
    if not merchant_id:
        return False

    if merchant_id in _SEEDED_MERCHANTS:
        return False

    async with _SEED_LOCK:
        if merchant_id in _SEEDED_MERCHANTS:
            return False

        profile_record = merchant_profile_memory(merchant)
        await memory_store.remember(merchant_id, [profile_record])
        _SEEDED_MERCHANTS.add(merchant_id)
        return True


def merchant_profile_memory(merchant: dict[str, Any]) -> str:
    return (
        "MERCHANT PROFILE\n"
        f"merchant_id: {merchant.get('merchant_id')}\n"
        f"merchant_name: {merchant.get('merchant_name')}\n"
        f"owner_name: {merchant.get('owner_name')}\n"
        f"preferred_language: {merchant.get('preferred_language')}\n"
        f"shop_type: {merchant.get('shop_type')}\n"
        f"average_daily_sales: {merchant.get('average_daily_sales')}\n"
        f"city: {merchant.get('city')}"
    )


def leak_proposal_memory(
    *,
    merchant: dict[str, Any],
    leak: dict[str, Any],
    reasoning: dict[str, Any],
) -> str:
    action = reasoning.get("action", {})
    return (
        "KIRANA KAVACH INTERACTION\n"
        f"merchant_id: {merchant.get('merchant_id')}\n"
        f"leak_type: {leak.get('type')}\n"
        f"leak_facts: {json.dumps(leak, ensure_ascii=False, default=str)}\n"
        f"explanation: {reasoning.get('explanation')}\n"
        f"recommendation: {reasoning.get('recommendation')}\n"
        f"action_type: {action.get('type')}\n"
        f"action_payload: {json.dumps(action.get('payload', {}), ensure_ascii=False, default=str)}\n"
        "status: proposed\n"
        "merchant_approval: unknown\n"
        "outcome: unknown"
    )


def action_outcome_memory(
    *,
    merchant_id: str,
    action_type: str,
    approved: bool,
    status: str,
    outcome_note: str | None = None,
) -> str:
    return (
        "KIRANA KAVACH ACTION OUTCOME\n"
        f"merchant_id: {merchant_id}\n"
        f"action_type: {action_type}\n"
        f"merchant_approval: {'approved' if approved else 'rejected'}\n"
        f"status: {status}\n"
        f"outcome: {outcome_note or 'No additional outcome note.'}"
    )

