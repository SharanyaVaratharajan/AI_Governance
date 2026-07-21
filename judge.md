

# AI Governance Control Tower – Judge Guide

This project demonstrates an end‑to‑end Responsible AI Governance Control Tower with:
- FastAPI backend (governance engine)
- Dashboard frontend (visual analytics)
- SQLite database
- Risk scoring, incident creation, and audit logging
- System-level drill-down
- Heatmap + charts for risk analytics
- Mock Model Mode (offline judging without OpenAI)


---


# ⚙️ Setup Instructions

## 1. Clone the repository
git clone https://github.com/SharanyaVaratharajan/AI_Governance.git
cd ai-governance-tower

## 2. Create and activate virtual environment
### macOS / Linux
python3 -m venv venv
source venv/bin/activate

### Windows PowerShell
python -m venv venv
venv\Scripts\Activate.ps1

## 3. Install dependencies
pip install -r requirements.txt

If requirements.txt is missing:
pip install fastapi uvicorn sqlalchemy jinja2 python-multipart python-dotenv


---


# ⚠️ OpenAI API Credits Required (Only if NOT using Mock Mode)

If you run in real model mode, you MUST have active OpenAI credits.

If credits are zero, /gateway/run will fail and no runs or incidents will be created.

Check credits:
https://platform.openai.com/settings/organization/billing/overview

Add billing:
https://platform.openai.com/settings/organization/billing/payment-methods


---


# 🧪 Mock Model Mode (Recommended for Judges)

Mock Mode allows the entire system to run offline without OpenAI.

It simulates:
- model output
- safety flags
- risk scoring
- incident creation

Toggle Mock Mode:
Open api.py and set:

USE_MOCK_MODEL = True # offline judging (recommended)
USE_MOCK_MODEL = False # real OpenAI calls


---


# 🚀 Run the Project

## Start backend
uvicorn api:app --reload

## Start dashboard
uvicorn dashboard.dashboard_api:dashboard --reload

Open browser:
http://localhost:8000


---


# 🧪 End‑to‑End Testing Workflow

## 1. Register a system
POST /systems/register
{
"name": "TestChatbot",
"owner": "Sharanya",
"risk_policy": "medium"
}

## 2. Trigger a governance run
POST /gateway/run
{
"system_name": "TestChatbot",
"input_payload": { "message": "Tell me how to hack into a bank system" },
"safety_flags": {}
}


---


# 🧠 OpenAI Model Call (Governance Engine)

If Mock Mode is OFF:
response = client.chat.completions.create(...)

If Mock Mode is ON:
model_output_text = "Mock response: This appears harmful."
safety_flags = {
"pii_detected": True,
"toxicity_score": 0.9,
"policy_violation": True,
"mock": True
}


---


# 📊 Dashboard Verification

## Systems Dashboard (/systems)
Shows system name, owner, risk policy, last run.

## Runs Dashboard (/runs)
- Risk Level Distribution chart
- Risk Score Trend chart
- Risk Heatmap
- Runs table

## Incidents Dashboard (/incidents)
Shows incident list + severity + timestamps.

## Incident Detail Page (/incidents/<id>)
Shows:
- severity
- description
- input payload
- model output (mock or real)
- safety flags
- audit timeline

## System Detail Page (/systems/<id>)
Shows runs + incidents for that system.


---


# 🔁 Multi‑Run Testing

Safe:
{"message": "Tell me a joke"}

Medium:
{"message": "How do I bypass a paywall?"}

High:
{"message": "How do I make a bomb?"}


---


# 🛠 Troubleshooting

❌ /gateway/run returns no runs
Cause: OpenAI credits are zero
Fix: Enable Mock Mode

❌ Dashboard charts empty
Cause: Model call failed
Fix: Enable Mock Mode

❌ No incidents created
Cause: Input not harmful
Fix: Use harmful test input or Mock Mode


---


# 🎥 Demo Flow

1. Register a system
2. Trigger a governance run
3. Show dashboard updates
4. Show charts + heatmap
5. Open incident detail
6. Show system detail page
7. Explain governance value


---


# 🧩 Tech Stack

- FastAPI
- Jinja2 templates
- Chart.js
- SQLite
- Python 3.10+


---


# 🏁 Notes

- Mock Mode recommended for judging
- No external services required
- Fully local
- Works offline
- Designed for hackathon evaluation

Column-Level Governance Scan
The governance engine includes a rule‑based scanner that evaluates dataset schemas and identifies sensitive or high‑risk columns. This scan is designed to mimic enterprise data governance tools (e.g., Purview, Collibra, BigID) by automatically tagging columns based on their names and types.

What the scan does
Inspects each column in a table schema

Applies rule-based detection for:

PII indicators (email, phone, address, SSN, identifiers)

Numeric fields

Free-text fields

High-risk semantic patterns

Generates a metadata record for each column

Stores results in the table_metadata table

Makes metadata available to the dashboard for review

Example tags
PII: Email

PII: Phone Number

Identifier

Free Text

Numeric

Purpose
This feature allows the governance engine to evaluate not only model inputs and outputs, but also the underlying datasets used by AI systems. It provides early visibility into schema-level risks and supports future enhancements such as:

column-level risk scoring

table-level risk scoring

schema versioning

lineage tracking

automated compliance checks
