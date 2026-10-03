# Kirana Kavach — Phase 5

Phase 5 adds merchant-approved action execution on top of the verified Phase 1–4 pipeline. The settlement support action remains available, while the existing customer-frequency leak now naturally doubles as the product's growth/retention action: prepare a customer reactivation pack for merchant review. This keeps the live implementation close to the original Kirana Kavach pitch without claiming an automatic WhatsApp or real Paytm customer-contact integration.

## Current architecture

```text
Paytm-shaped transaction data
        ↓
Rule-based leak detection
        ↓
Cognee memory recall
        ↓
Narrow reasoning layer
        ↓
Sarvam voice / text confirmation
        ↓
Approved action endpoint
        ↓
n8n or local mock executor
        ↓
Outcome stored in Cognee
```

For voice input:

```text
Merchant audio (short clip)
        ↓
Sarvam Saaras v4 STT
        ↓
Transcript
        ↓
Leak selection
        ↓
Existing reasoning + Cognee memory
        ↓
Sarvam Bulbul v3 TTS
        ↓
Base64 WAV response
```

The voice endpoint does **not** execute an action. It only explains a detected leak and asks for confirmation. Phase 5 then uses the separate approved-action endpoint to execute the confirmed action through n8n or the local mock executor.

## Demo-aligned action path

The customer-frequency leak is intentionally reused as the growth/retention story from the original pitch:

```text
Regular customer normally buys every ~2–3 days
        ↓
Current gap is ~3.4× normal
        ↓
Kavach recommends a customer-recovery offer
        ↓
Merchant approves
        ↓
n8n prepares a reactivation pack
        ↓
Demo campaign reference + payment-link reference + draft message
        ↓
Nothing is sent automatically
        ↓
Outcome is remembered in Cognee
```

The settlement-support action remains as a second, operational capability.

## Run

From the project root:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest -q
```

The current Phase 5 test suite should report `20 passed` before you connect n8n.

Start the API:

```powershell
$env:KAVACH_MEMORY_PROVIDER="cognee"
$env:KAVACH_REASONING_PROVIDER="mock"
$env:AUTO_FEEDBACK="false"
$env:COGNEE_DATASET_PREFIX="kirana_kavach_v2"
uvicorn backend.app.main:app --reload
```

Open:

`http://127.0.0.1:8000/docs`

## Enable real Sarvam voice

Set the API key in the same PowerShell session:

```powershell
$env:SARVAM_API_KEY="YOUR_KEY"
```

Then use:

`POST /api/merchants/{merchant_id}/voice`

Upload a short audio clip. The current Sarvam REST speech-to-text API supports short synchronous clips under 30 seconds, and the text-to-speech REST API returns base64-encoded audio. The project explicitly uses `saaras:v4` for STT and `bulbul:v3` for TTS. [Sarvam STT](https://docs.sarvam.ai/api-reference/speech-to-text/transcribe) | [Sarvam TTS](https://docs.sarvam.ai/api-reference/text-to-speech/convert)

## Text fallback

The existing reasoning endpoint remains available:

`POST /api/merchants/{merchant_id}/reasoning/{leak_type}`

If voice fails near the demo, keep using the text endpoint rather than risking the demo.

## Phase 5 — approved action execution with n8n

The new endpoint is:

`POST /api/merchants/{merchant_id}/actions/confirm`

Example request:

```json
{
  "action_type": "CREATE_PAYTM_SUPPORT_CASE",
  "approved": true,
  "confirmation_source": "ui"
}
```

The backend recomputes the current recommended action instead of trusting client-supplied transaction/customer details. If approved, it sends the validated action contract to n8n.

For local development:

```powershell
$env:N8N_EXECUTION_PROVIDER="mock"
```

For the real n8n workflow:

```powershell
$env:N8N_EXECUTION_PROVIDER="webhook"
$env:N8N_WEBHOOK_URL="YOUR_N8N_PRODUCTION_WEBHOOK_URL"
$env:N8N_WEBHOOK_SECRET="YOUR_SHARED_SECRET"
```

See `n8n/SETUP.md` and `n8n/kirana_kavach_action_workflow.json`.
