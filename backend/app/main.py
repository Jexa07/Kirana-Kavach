import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime
from functools import lru_cache
from typing import Literal

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from dotenv import load_dotenv

load_dotenv()

from .action_execution import (
    ActionConfirmationRequest,
    ActionExecutionError,
    N8NConfig,
    execute_action,
)
from .data_store import get_merchant, get_transactions
from .detection import detect_customer_frequency_drop, detect_settlement_leak
from .memory import (
    MemoryConfig,
    action_outcome_memory,
    create_memory_store,
    ensure_merchant_profile_seeded,
    leak_proposal_memory,
    merchant_profile_memory,
)
from .reasoning import ReasoningConfig, reason_about_leak
from .voice import SarvamVoiceConfig, SarvamVoiceError, language_code, synthesize_speech, transcribe_audio

DEFAULT_MERCHANT = "M1001"

AS_OF = datetime.fromisoformat("2026-10-02T12:00:00")


@lru_cache(maxsize=1)
def get_memory_store():
    return create_memory_store(MemoryConfig.from_env())


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        m_data = get_merchant(DEFAULT_MERCHANT)
        m_store = get_memory_store()
        t0 = time.perf_counter()
        seeded = await ensure_merchant_profile_seeded(m_store, m_data)
        seed_dur = time.perf_counter() - t0
        if seeded:
            print(f"[KAVACH TIMING] COGNEE STARTUP SEED ({DEFAULT_MERCHANT}): {seed_dur:.2f}s", flush=True)

        t1 = time.perf_counter()
        warm_results = await m_store.recall(DEFAULT_MERCHANT, "merchant outcomes")
        warm_dur = time.perf_counter() - t1
        print(f"[KAVACH TIMING] COGNEE STARTUP PRE-WARM ({DEFAULT_MERCHANT}): {warm_dur:.2f}s (found {len(warm_results)})", flush=True)
    except Exception as exc:
        print(f"[KAVACH STARTUP WARNING] {exc}", flush=True)
    yield


app = FastAPI(title="Kirana Kavach Phase 5", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



class TTSRequest(BaseModel):
    text: str = Field(min_length=1)
    language: str | None = None


class ActionOutcomeRequest(BaseModel):
    action_type: Literal[
        "CREATE_PAYTM_SUPPORT_CASE",
        "DRAFT_CUSTOMER_MESSAGE",
    ]
    approved: bool
    status: str = Field(min_length=1)
    outcome_note: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "5"}


@app.get("/api/merchants/{merchant_id}")
def merchant(merchant_id: str):
    try:
        return get_merchant(merchant_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/merchants/{merchant_id}/transactions")
def transactions(merchant_id: str):
    return {
        "merchant_id": merchant_id,
        "transactions": get_transactions(merchant_id),
    }


@app.get("/api/merchants/{merchant_id}/leaks")
def leaks(merchant_id: str):
    txns = get_transactions(merchant_id)
    settlement = detect_settlement_leak(txns, as_of=AS_OF)
    customer = detect_customer_frequency_drop(txns, as_of=AS_OF)
    return {
        "merchant_id": merchant_id,
        "as_of": AS_OF.isoformat(),
        "settlement_leak": settlement,
        "customer_frequency_leaks": customer,
    }


@app.post("/api/merchants/{merchant_id}/reasoning/{leak_type}")
async def reasoning(merchant_id: str, leak_type: str):
    try:
        merchant_data = get_merchant(merchant_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    txns = get_transactions(merchant_id)

    if leak_type == "settlement_leak":
        leak = detect_settlement_leak(txns, as_of=AS_OF)
    elif leak_type == "customer_frequency_drop":
        customer_leaks = detect_customer_frequency_drop(txns, as_of=AS_OF)
        leak = customer_leaks[0] if customer_leaks else None
    else:
        raise HTTPException(status_code=400, detail="Unsupported leak type")

    if leak is None:
        raise HTTPException(
            status_code=404,
            detail="No detected leak of this type",
        )

    memory_store = get_memory_store()

    # Store the merchant profile once as a durable memory record.
    await ensure_merchant_profile_seeded(memory_store, merchant_data)

    memory_query = (
        "previous leaks recommendations merchant approvals outcomes "
        f"{leak_type}"
    )
    memory_context = await memory_store.recall(
        merchant_id,
        memory_query,
    )

    result = reason_about_leak(
        merchant=merchant_data,
        leak=leak,
        config=ReasoningConfig.from_env(),
        memory_context=memory_context,
    )

    # Persist the detected leak + recommendation so the next interaction can
    # retrieve it. Approval and final execution outcome are recorded separately.
    await memory_store.remember(
        merchant_id,
        [
            leak_proposal_memory(
                merchant=merchant_data,
                leak=leak,
                reasoning=result.model_dump(),
            )
        ],
    )

    return {
        "merchant_id": merchant_id,
        "memory": {
            "items_found": len(memory_context),
            "context": memory_context,
        },
        "leak": leak,
        "reasoning": result.model_dump(),
    }


_SETTLEMENT_TERMS = (
    "settlement",
    "settled",
    "payment",
    "पेमेंट",
    "सेटल",
    "सेटलमेंट",
    "पैसा",
    "पैसे",
    "अटका",
    "रुका",
    "utr",
    "upi",
)
_CUSTOMER_TERMS = (
    "customer",
    "ग्राहक",
    "कस्टमर",
    "खरीदता",
    "खरीदते",
    "खरीदा",
)


def _choose_voice_leak(
    transcript: str,
    *,
    settlement: dict | None,
    customer_leaks: list[dict],
) -> tuple[str, dict]:
    lowered = transcript.lower()

    if settlement and any(term in lowered for term in _SETTLEMENT_TERMS):
        return "settlement_leak", settlement

    if customer_leaks and any(term in lowered for term in _CUSTOMER_TERMS):
        return "customer_frequency_drop", customer_leaks[0]

    # Demo-safe fallback: the highest-priority available leak is the
    # settlement leak, otherwise the strongest customer-frequency leak.
    if settlement:
        return "settlement_leak", settlement
    if customer_leaks:
        return "customer_frequency_drop", customer_leaks[0]

    raise HTTPException(status_code=404, detail="No detected leak is available")


def _build_spoken_text(reasoning: dict, merchant_language: str) -> str:
    explanation = reasoning["explanation"]
    recommendation = reasoning["recommendation"]
    action_type = reasoning["action"]["type"]

    language = (merchant_language or "en").lower()
    if language == "hi":
        if action_type == "CREATE_PAYTM_SUPPORT_CASE":
            confirmation = "क्या मैं आपके लिए यह Paytm सपोर्ट केस तैयार कर दूँ?"
        else:
            confirmation = "क्या मैं आपके लिए यह संदेश तैयार कर दूँ?"
    else:
        if action_type == "CREATE_PAYTM_SUPPORT_CASE":
            confirmation = "Should I prepare the Paytm support case for you?"
        else:
            confirmation = "Should I prepare the message for you?"

    return f"{explanation} {recommendation} {confirmation}"


@app.post("/api/merchants/{merchant_id}/voice")
async def voice(
    merchant_id: str,
    audio: UploadFile = File(...),
    leak_type: str | None = None,
    include_tts: bool = False,
):
    """Transcribe a short merchant voice clip, reason over a detected leak,
    and return a Sarvam-generated spoken response.

    The endpoint intentionally keeps action confirmation outside execution:
    it only explains a leak and asks the merchant whether to proceed.
    """
    t_total_0 = time.perf_counter()

    try:
        merchant_data = get_merchant(merchant_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Audio file is empty")

    txns = get_transactions(merchant_id)
    settlement = detect_settlement_leak(txns, as_of=AS_OF)
    customer_leaks = detect_customer_frequency_drop(txns, as_of=AS_OF)

    voice_config = SarvamVoiceConfig.from_env()

    try:
        t_stt_0 = time.perf_counter()
        transcript_data = await asyncio.to_thread(
            transcribe_audio,
            audio=audio_bytes,
            filename=audio.filename or "merchant_audio.wav",
            content_type=audio.content_type or "audio/wav",
            config=voice_config,
        )
        stt_duration = time.perf_counter() - t_stt_0

        transcript = transcript_data["transcript"]
        detected_language = transcript_data["language_code"]

        if leak_type:
            if leak_type == "settlement_leak":
                leak = settlement
            elif leak_type == "customer_frequency_drop":
                leak = customer_leaks[0] if customer_leaks else None
            else:
                raise HTTPException(status_code=400, detail="Unsupported leak type")
            if leak is None:
                raise HTTPException(status_code=404, detail="No detected leak of this type")
            selected_leak_type = leak_type
        else:
            selected_leak_type, leak = _choose_voice_leak(
                transcript,
                settlement=settlement,
                customer_leaks=customer_leaks,
            )

        memory_store = get_memory_store()

        t_seed_0 = time.perf_counter()
        await ensure_merchant_profile_seeded(memory_store, merchant_data)
        seed_duration = time.perf_counter() - t_seed_0

        t_recall_0 = time.perf_counter()
        memory_context = await memory_store.recall(
            merchant_id,
            f"merchant outcomes {selected_leak_type}",
        )
        recall_duration = time.perf_counter() - t_recall_0

        t_reason_0 = time.perf_counter()
        reasoning_result = reason_about_leak(
            merchant=merchant_data,
            leak=leak,
            config=ReasoningConfig.from_env(),
            memory_context=memory_context,
        )
        reasoning_data = reasoning_result.model_dump()
        reasoning_duration = time.perf_counter() - t_reason_0

        spoken_text = _build_spoken_text(
            reasoning_data,
            merchant_data.get("preferred_language", "en"),
        )

        tts_duration = 0.0
        tts = None
        if include_tts:
            t_tts_0 = time.perf_counter()
            tts = await asyncio.to_thread(
                synthesize_speech,
                text=spoken_text,
                language_code_value=language_code(
                    merchant_data.get("preferred_language")
                ),
                config=voice_config,
            )
            tts_duration = time.perf_counter() - t_tts_0

        total_duration = time.perf_counter() - t_total_0

        print(f"[KAVACH TIMING] STT: {stt_duration:.2f}s", flush=True)
        print(f"[KAVACH TIMING] COGNEE SEED: {seed_duration:.2f}s", flush=True)
        print(f"[KAVACH TIMING] COGNEE RECALL: {recall_duration:.2f}s", flush=True)
        print(f"[KAVACH TIMING] REASONING: {reasoning_duration:.2f}s", flush=True)
        print(f"[KAVACH TIMING] TTS: {tts_duration:.2f}s", flush=True)
        print(f"[KAVACH TIMING] TOTAL: {total_duration:.2f}s", flush=True)

        return {
            "merchant_id": merchant_id,
            "transcript": transcript,
            "detected_language": detected_language,
            "selected_leak_type": selected_leak_type,
            "memory_items_found": len(memory_context),
            "spoken_text": spoken_text,
            "reasoning": reasoning_data,
            "audio": tts,
        }
    except SarvamVoiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/merchants/{merchant_id}/tts")
async def tts_endpoint(
    merchant_id: str,
    payload: TTSRequest,
):
    """Synthesize speech on-demand for a given text string using Sarvam TTS."""
    try:
        merchant_data = get_merchant(merchant_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    voice_config = SarvamVoiceConfig.from_env()
    lang = payload.language or merchant_data.get("preferred_language", "en")

    try:
        t_tts_0 = time.perf_counter()
        tts = await asyncio.to_thread(
            synthesize_speech,
            text=payload.text,
            language_code_value=language_code(lang),
            config=voice_config,
        )
        tts_duration = time.perf_counter() - t_tts_0
        print(f"[KAVACH TIMING] ONDEMAND TTS: {tts_duration:.2f}s", flush=True)

        return {
            "merchant_id": merchant_id,
            "text": payload.text,
            "audio": tts,
        }
    except SarvamVoiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/merchants/{merchant_id}/memory")
async def memory(merchant_id: str, query: str = "previous merchant context"):
    try:
        get_merchant(merchant_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    memory_store = get_memory_store()
    results = await memory_store.recall(merchant_id, query)

    return {
        "merchant_id": merchant_id,
        "query": query,
        "items_found": len(results),
        "results": results,
    }


@app.post("/api/merchants/{merchant_id}/memory/outcome")
async def memory_outcome(
    merchant_id: str,
    payload: ActionOutcomeRequest,
):
    try:
        get_merchant(merchant_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    memory_store = get_memory_store()

    record = action_outcome_memory(
        merchant_id=merchant_id,
        action_type=payload.action_type,
        approved=payload.approved,
        status=payload.status,
        outcome_note=payload.outcome_note,
    )

    await memory_store.remember(merchant_id, [record])

    return {
        "merchant_id": merchant_id,
        "stored": True,
        "record": record,
    }

@app.post("/api/merchants/{merchant_id}/actions/confirm")
async def confirm_action(
    merchant_id: str,
    payload: ActionConfirmationRequest,
):
    """Approve or reject the currently recommended action.

    The server recomputes the current leak and reasoning contract instead of
    trusting a client-supplied payload. This prevents an approved request from
    changing the transaction/customer details before n8n receives it.
    """
    try:
        merchant_data = get_merchant(merchant_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    txns = get_transactions(merchant_id)

    if payload.action_type == "CREATE_PAYTM_SUPPORT_CASE":
        leak = detect_settlement_leak(txns, as_of=AS_OF)
    else:
        customer_leaks = detect_customer_frequency_drop(txns, as_of=AS_OF)
        leak = customer_leaks[0] if customer_leaks else None

    if leak is None:
        raise HTTPException(
            status_code=404,
            detail="No currently detected leak matches the requested action",
        )

    memory_store = get_memory_store()
    await ensure_merchant_profile_seeded(memory_store, merchant_data)

    memory_context = await memory_store.recall(
        merchant_id,
        f"previous leaks recommendations merchant approvals outcomes {leak['type']}",
    )

    reasoning_result = reason_about_leak(
        merchant=merchant_data,
        leak=leak,
        config=ReasoningConfig.from_env(),
        memory_context=memory_context,
    )
    action = reasoning_result.action.model_dump()

    if action["type"] != payload.action_type:
        raise HTTPException(
            status_code=409,
            detail=(
                "Requested action does not match the currently recommended action"
            ),
        )

    if not payload.approved:
        await memory_store.remember(
            merchant_id,
            [
                action_outcome_memory(
                    merchant_id=merchant_id,
                    action_type=payload.action_type,
                    approved=False,
                    status="rejected",
                    outcome_note="Merchant declined the recommended action.",
                )
            ],
        )
        return {
            "merchant_id": merchant_id,
            "status": "rejected",
            "action": action,
        }

    try:
        execution = await asyncio.to_thread(
            execute_action,
            merchant_id=merchant_id,
            action=action,
            confirmation_source=payload.confirmation_source,
            config=N8NConfig.from_env(),
        )
    except ActionExecutionError as exc:
        await memory_store.remember(
            merchant_id,
            [
                action_outcome_memory(
                    merchant_id=merchant_id,
                    action_type=payload.action_type,
                    approved=True,
                    status="failed",
                    outcome_note=str(exc),
                )
            ],
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    await memory_store.remember(
        merchant_id,
        [
            action_outcome_memory(
                merchant_id=merchant_id,
                action_type=payload.action_type,
                approved=True,
                status=execution.status,
                outcome_note=(
                    f"{execution.outcome_note} "
                    f"external_id={execution.external_id or 'none'}"
                ),
            )
        ],
    )

    return {
        "merchant_id": merchant_id,
        "status": execution.status,
        "action": action,
        "execution": execution.model_dump(),
    }

