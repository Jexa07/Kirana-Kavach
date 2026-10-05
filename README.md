# 🛡️ Kirana Kavach

### AI Copilot for India's Kirana Merchants

**Kirana Kavach** is a voice-first AI copilot designed to help kirana merchants understand what is happening in their business, identify revenue and customer problems early, and take the next best action without navigating complex dashboards.

The core idea is simple:

**Detect → Recommend → Execute → Remember**

Instead of only showing a merchant numbers, Kavach turns business signals into an actionable conversation.

---

## 🚀 The Problem

Kirana stores have something large digital platforms struggle to replicate:

- local trust
- repeat customers
- personal relationships
- flexible credit
- knowledge of their neighbourhood

But many merchants still have to manually interpret sales patterns and decide what to do when customers stop coming, settlements are delayed, or revenue starts weakening.

At the same time, quick-commerce platforms compete heavily for everyday purchases.

The problem isn't simply:

> **"How much did I sell?"**

It's:

> **"What is going wrong, why is it happening, and what should I do about it right now?"**

Kirana Kavach is built around that question.

---

# 💡 Our Solution

Kirana Kavach acts as a merchant's AI copilot.

It continuously turns business signals into a simple workflow:

```text
Business Data
     ↓
   Detect
     ↓
   Reason
     ↓
   Remember past context
     ↓
 Recommend an action
     ↓
 Merchant reviews
     ↓
 Approve / Reject
     ↓
 n8n executes the approved workflow
     ↓
 Remember the outcome
```

The experience is intentionally **voice-first**.

A merchant shouldn't need to understand analytics dashboards, filters, charts, or complicated software.

They should be able to simply say:

> **"मेरी दुकान पर ग्राहक कम क्यों आ रहे हैं?"**

And Kavach should explain what it found and what can be done next.

---

# 🎯 What the MVP Demonstrates

The current MVP focuses on a concrete merchant problem:

## Customer Visit Frequency Drop

Kavach detects when a customer's visit frequency has changed significantly compared with their historical behaviour.

For example:

```text
Customer: C1001

Usual visit gap:       ~2.6 days
Current visit gap:     ~8.8 days

Frequency deterioration: ~3.4×
```

Instead of merely showing the metric, Kavach turns the signal into a recommendation:

```text
Customer frequency has dropped significantly.
        ↓
Customer may be at risk of becoming inactive.
        ↓
Recommend reactivation.
        ↓
Prepare a personalised Hindi message.
        ↓
Merchant reviews the action.
        ↓
Merchant approves.
        ↓
n8n prepares the reactivation workflow.
```

The merchant remains in control.

---

# 🧠 The Kavach Loop

## 1. Detect

Kavach analyses merchant activity and identifies signals that require attention.

Current MVP signals include:

- Customer visit-frequency drop
- Settlement delays / pending settlement risk

The detection layer compares current behaviour with the merchant's historical baseline.

---

## 2. Recommend

The reasoning layer explains:

- What happened
- Why it matters
- What the merchant can do
- What action can be prepared

The goal is not to overwhelm the merchant with analytics.

It is to answer:

> **"So what should I do?"**

---

## 3. Execute

Actions are not silently executed.

Kavach generates an action contract and asks the merchant to approve it.

For example:

```text
Customer: C1001

Recommended action:
Reactivate customer

Message:
"नमस्ते, काफी समय से आपसे मुलाकात नहीं हुई।
जब भी सुविधा हो, दुकान पर ज़रूर आइए।"
```

The merchant can then:

**Approve Action**  
or  
**Reject Action**

Once approved, the action is passed to n8n.

---

## 4. Remember

Kavach uses **Cognee** as its memory layer.

The system can remember merchant-specific context such as:

- previous recommendations
- merchant preferences
- previous leaks
- customer-related context
- previous action outcomes

This means the copilot does not have to treat every conversation as a completely new interaction.

---

# 🎤 Voice-First Experience

Kirana Kavach is designed around voice rather than a traditional analytics dashboard.

The voice pipeline is:

```text
Merchant speaks
      ↓
Sarvam Speech-to-Text
      ↓
Kavach detection
      ↓
Cognee memory recall
      ↓
Reasoning
      ↓
Action recommendation
      ↓
Sarvam Text-to-Speech
```

The system is designed for natural Indian-language interaction and can respond in Hindi for the current demo flow.

Example:

> **Merchant:**  
> "मेरी दुकान पर ग्राहक कम आ रहे हैं।"

Kavach processes the request, checks the available merchant context, identifies the relevant signal, and presents an actionable recommendation.

---

# 🏗️ Architecture

```text
                    ┌─────────────────────┐
                    │     Merchant        │
                    │  Voice Interaction  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │       Sarvam        │
                    │ Speech-to-Text / TTS│
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │      FastAPI        │
                    │    Kavach Backend   │
                    └──────────┬──────────┘
                               │
                ┌──────────────┼──────────────┐
                │              │              │
                ▼              ▼              ▼
        ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
        │  Detection  │ │  Reasoning  │ │   Cognee    │
        │    Layer    │ │    Layer    │ │   Memory    │
        └─────────────┘ └─────────────┘ └─────────────┘
                │              │              │
                └──────────────┼──────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Merchant Approval  │
                    └──────────┬──────────┘
                               │
                         Approved Action
                               │
                               ▼
                    ┌─────────────────────┐
                    │        n8n          │
                    │ Workflow Execution  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Action Result /     │
                    │ Outcome Memory      │
                    └─────────────────────┘
```

---

# 🧰 Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite + TypeScript |
| Backend | FastAPI + Python |
| Voice | Sarvam AI |
| Memory | Cognee |
| Workflow Automation | n8n |
| Data | Paytm-shaped mock merchant data |
| API | REST |
| Styling | CSS |
| Development | Python virtual environment + npm |

The hackathon concept is designed around Paytm's merchant ecosystem, while the current repository uses **mock Paytm-shaped data for the demo rather than claiming access to production Paytm merchant APIs**.

---

# 📂 Project Structure

```text
kirana_kavach/
│
├── backend/
│   ├── app/
│   │   ├── action_execution.py
│   │   ├── data_store.py
│   │   ├── detection.py
│   │   ├── main.py
│   │   ├── memory.py
│   │   ├── models.py
│   │   ├── reasoning.py
│   │   └── voice.py
│   │
│   └── run_detection.py
│
├── data/
│   └── paytm_mock.json
│
├── frontend/
│   ├── public/
│   └── src/
│       ├── App.tsx
│       ├── App.css
│       ├── PlansModal.tsx
│       └── index.css
│
├── n8n/
│   └── kirana_kavach_action_workflow.json
│
├── tests/
│
├── .env.example
├── .gitignore
└── README.md
```

---

# ⚙️ Getting Started

## Prerequisites

Make sure you have:

- Python 3.12+
- Node.js 18+
- npm
- n8n
- A Sarvam API key

---

## 1. Clone the repository

```bash
git clone <your-repository-url>
cd kirana_kavach
```

---

# 2. Create the Python environment

From the project root:

### Windows PowerShell

```powershell
python -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\Activate.ps1
```

---

# 3. Install backend dependencies

```powershell
pip install -r requirements.txt
```

---

# 4. Configure environment variables

Create a `.env` file from `.env.example`.

```powershell
Copy-Item .env.example .env
```

Add your credentials locally.

Example:

```env
SARVAM_API_KEY=your_sarvam_api_key

KAVACH_MEMORY_PROVIDER=cognee
KAVACH_REASONING_PROVIDER=mock

AUTO_FEEDBACK=false

COGNEE_DATASET_PREFIX=kirana_kavach_v2
COGNEE_TOP_K=2
```

---

# 5. Start the FastAPI backend

From the project root:

```powershell
uvicorn backend.app.main:app --reload --port 8000
```

The backend will be available at:

```text
http://127.0.0.1:8000
```

FastAPI documentation:

```text
http://127.0.0.1:8000/docs
```

---

# 6. Start the frontend

Open another terminal:

```powershell
cd frontend
npm install
npm run dev
```

The frontend will normally be available at:

```text
http://localhost:5173
```

---

# 7. Start n8n

Start your local n8n instance:

```powershell
n8n start
```

Open:

```text
http://localhost:5678
```

Import:

```text
n8n/kirana_kavach_action_workflow.json
```

Activate the workflow.

The local action webhook used by the MVP is:

```text
http://localhost:5678/webhook/kirana-kavach/action
```

---

# 🔌 API Overview

## Health

```http
GET /health
```

Checks whether the backend is running.

---

## Merchant leaks

```http
GET /api/merchants/{merchant_id}/leaks
```

Returns detected merchant signals.

Example:

```http
GET /api/merchants/M1001/leaks
```

---

## Reasoning

```http
POST /api/merchants/{merchant_id}/reasoning/{leak_type}
```

Generates the explanation, recommendation, and action contract for a detected signal.

---

## Voice

```http
POST /api/merchants/{merchant_id}/voice
```

Processes merchant audio through the voice pipeline.

The frontend currently uses:

```text
include_tts=false
```

for the faster insight flow.

---

## Text-to-Speech

```http
POST /api/merchants/{merchant_id}/tts
```

Generates the spoken response using Sarvam TTS.

---

## Confirm Action

```http
POST /api/merchants/{merchant_id}/actions/confirm
```

The merchant explicitly approves or rejects the proposed action.

The backend recomputes the action contract before execution rather than trusting an arbitrary client payload.

---

# 🔐 Human-in-the-Loop Safety

Kirana Kavach is designed so that AI recommendations do not automatically trigger sensitive merchant actions.

The workflow is:

```text
AI Recommendation
       ↓
Action Preview
       ↓
Merchant Approval
       ↓
Workflow Execution
```

This is especially important for actions involving:

- customer communication
- promotional campaigns
- financial recommendations
- external workflow execution

The merchant remains the final decision-maker.

---

# 🔄 n8n Action Workflow

The current n8n workflow supports the MVP action contracts:

### `CREATE_PAYTM_SUPPORT_CASE`

Used for settlement-related support workflows.

### `DRAFT_CUSTOMER_MESSAGE`

Used for customer reactivation.

The customer reactivation flow currently prepares an action package containing:

- customer ID
- campaign type
- approved message
- payment-link reference
- external action reference
- execution status

The MVP intentionally distinguishes between:

**Prepared / submitted**

and

**Delivered**

so that the system does not claim successful delivery without confirmation from the external provider.

---

# 🧪 Demo Scenario

The easiest way to experience the MVP is through the merchant:

```text
M1001
Sharma General Store
Mumbai
```

### Step 1 — Merchant opens Kavach

The dashboard shows a customer-frequency warning.

### Step 2 — Merchant interacts through voice

Example:

> "मेरी दुकान पर ग्राहक कम क्यों आ रहे हैं?"

### Step 3 — Kavach identifies the signal

```text
Customer visit frequency has dropped.

Usual gap:    ~2.6 days
Current gap:  ~8.8 days
Change:       ~3.4×
```

### Step 4 — Kavach explains the problem

The system generates:

- explanation
- recommendation
- action contract

### Step 5 — Merchant reviews the action

Kavach prepares a Hindi customer-reengagement message.

### Step 6 — Merchant approves

The merchant explicitly clicks:

```text
Approve Action
```

### Step 7 — n8n executes the workflow

The action is sent to the configured n8n workflow.

### Step 8 — Outcome is remembered

The action result can be stored back into the merchant's memory context.

---

# 🧠 Why Cognee?

Traditional analytics can tell a merchant:

> "Sales are down."

Kavach aims to answer:

> "Sales are down, this is what we know about your business, this is what happened before, and this is what you can do next."

Cognee provides the memory layer required to move toward that experience.

The long-term vision is for every merchant to have a persistent business context rather than a stateless chatbot.

---

# 🎯 Why Voice?

Kirana Kavach is designed for merchants who may not want to interact with complex dashboards.

Instead of:

```text
Open dashboard
→ Find analytics
→ Select date
→ Filter customers
→ Interpret chart
→ Decide action
```

the goal is:

```text
Speak
→ Understand
→ Decide
→ Approve
```

This makes the product especially suited to fast-moving retail environments where the merchant is busy running the store.

---

# 📈 Product Vision

The current MVP is the first step toward a broader merchant-defense system.

Future versions can expand detection to:

- product-level sales drops
- inventory risk
- customer churn
- settlement anomalies
- local competitive pressure
- campaign performance
- merchant cash-flow stress

Future action integrations can include:

- WhatsApp reactivation
- Paytm payment links
- local merchant promotions
- advertising workflows
- Paytm lending recommendations

The architecture is designed so that new detection signals can plug into the same:

```text
Detect → Recommend → Execute → Remember
```

loop.

---

# 🗺️ Roadmap

## Phase 1 — Merchant Intelligence

- [x] Mock Paytm-shaped merchant data
- [x] Sales/settlement signals
- [x] Customer-frequency detection
- [x] Historical baseline comparison

## Phase 2 — AI Reasoning

- [x] Explain detected problems
- [x] Generate recommendations
- [x] Generate action contracts
- [x] Merchant approval flow

## Phase 3 — Memory

- [x] Cognee integration
- [x] Merchant-specific memory
- [x] Memory recall
- [x] Outcome storage

## Phase 4 — Voice

- [x] Sarvam STT
- [x] Voice-based merchant interaction
- [x] Sarvam TTS
- [x] Voice response playback

## Phase 5 — Actions

- [x] n8n workflow integration
- [x] Customer reactivation action
- [x] Settlement support action
- [x] Merchant approval before execution

## Next

- [ ] Production Paytm API integrations
- [ ] Production customer-consent workflows
- [ ] Verified WhatsApp delivery
- [ ] Product-level demand detection
- [ ] Inventory intelligence
- [ ] Local competitive signals
- [ ] More Indian languages
- [ ] Production-grade authentication and authorization
- [ ] Scalable persistent memory infrastructure

---

# ⚠️ MVP / Demo Scope

This repository is a hackathon MVP.

To keep the demo reproducible and honest:

### Paytm data

The current demo uses **Paytm-shaped mock merchant data**.

It does not claim access to private production Paytm merchant data.

### Customer data

Customer identifiers such as `C1001` are demo records.

### Competitive intelligence

Competitive signals are part of the product vision. They are not the foundation of the current detection pipeline.

### WhatsApp

The MVP can prepare customer reactivation workflows and can be extended with an external messaging provider.

It does **not** claim that a customer message was delivered unless the configured provider explicitly confirms delivery.

### Payments

Payment-link references used in the demo are demonstration references unless connected to a real payment-link provider.

### Inventory prediction

Inventory and stockout intelligence are roadmap capabilities, not claims about the current MVP.

---

# 💼 Business Model

The product vision is designed around a low-friction merchant SaaS model.

### Free

Basic alerts and voice insights.

### Pro

Advanced detection, memory, customer reactivation, workflow automation and deeper merchant intelligence.

### Paytm ecosystem revenue

As the product matures, successful merchant actions can naturally connect merchants with relevant Paytm ecosystem products such as payments, advertising and financial services.

The principle is:

> **Help the merchant grow first. Monetization follows the value created.**

---

# 🏪 Why Kirana Kavach?

Most merchant software answers:

> **"What happened?"**

Kavach aims to answer:

> **"What happened, why does it matter, and what should I do next?"**

That shift — from **analytics to action** — is the core idea behind Kirana Kavach.

---

# 🛡️ The Vision

India's kirana stores already have the most important competitive advantage:

**relationships.**

Kirana Kavach adds an AI layer that helps merchants use those relationships more intelligently.

The long-term goal is not to replace the merchant.

It is to give every merchant a small AI teammate that:

```text
Sees the signal.
Understands the context.
Suggests the move.
Waits for the merchant.
Takes the action.
Remembers what happened.
```

**That's the Kavach.**

---

# 👥 Team

Built for the **Paytm Build for India AI Hackathon — Mumbai Edition**.

**Track:** Merchant Growth AI

### Team

- **Arpita Pani**
- **Sanjana Annam**

---

# 🙌 Acknowledgements

Built using technologies and platforms provided as part of the hackathon ecosystem:

- **Paytm**
- **Sarvam AI**
- **Cognee**
- **n8n**

Special thanks to the organisers, mentors and fellow builders who made the hackathon experience possible.

---

## ⭐ If you find this project interesting

Give the repository a ⭐ !
