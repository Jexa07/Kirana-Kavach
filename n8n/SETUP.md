# n8n setup — Phase 5

Phase 5 adds merchant-approved action execution. The backend never calls n8n until the merchant confirmation endpoint is called with `approved=true`. The existing settlement-support action remains available, while the customer-frequency leak now uses the same action contract to prepare a customer reactivation pack.

## 1. Import the workflow

In n8n, import:

`n8n/kirana_kavach_action_workflow.json`

The workflow contains:

```text
Webhook
   ↓
Execute Approved Action
   ↓
Respond to Webhook
```

The Webhook node uses a POST endpoint and the Respond to Webhook node returns the final JSON result. n8n documents both the test and production webhook URLs; the production URL is available once the workflow is published/active.

## 2. Copy the production webhook URL

Open the **Kavach Action Webhook** node and copy its **Production URL** after publishing/activating the workflow.

Set it in the FastAPI terminal:

```powershell
$env:N8N_EXECUTION_PROVIDER="webhook"
$env:N8N_WEBHOOK_URL="PASTE_YOUR_N8N_PRODUCTION_WEBHOOK_URL_HERE"
```

Optional secret header:

```powershell
$env:N8N_WEBHOOK_SECRET="YOUR_SHARED_SECRET"
```

For the imported workflow, configure Webhook authentication in n8n if you want to require header authentication. Keep the shared secret out of source control.

## 3. Local development fallback

Before n8n is connected, keep:

```powershell
$env:N8N_EXECUTION_PROVIDER="mock"
```

This lets the API test the exact approval/execution contract without a live n8n instance.

## 4. What the MVP actually executes

### Settlement leak

`CREATE_PAYTM_SUPPORT_CASE` returns a **demo support-case reference** and records the action as executed. It does not claim that a real Paytm support case was created.

### Customer-frequency leak

`DRAFT_CUSTOMER_MESSAGE` returns a prepared message. Nothing is sent automatically. This remains a merchant-review action by design.

Later, the n8n Code node can be replaced with a real HTTP Request node once a real Paytm support endpoint or an approved customer messaging provider is available.
