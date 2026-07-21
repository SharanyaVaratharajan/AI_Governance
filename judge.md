

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

---

## Recent Governance Enhancements

### Safer gateway preflight

`POST /governance/run` performs a preflight check before a model call. It returns one of four decisions:

- `ALLOW` � request can continue.
- `REDACT` � recognised PII is replaced with typed placeholders such as `[REDACTED_EMAIL]`.
- `REVIEW` � a suspicious request needs human attention.
- `BLOCK` � high-confidence phishing or a system policy prevents the model call.

Recognised PII is sanitized before model processing and before it is stored in `model_runs.input_payload`. Safety flags record `pii_redacted`, `redacted_types`, `preflight_decision`, and whether the model was called. The gateway response includes the redaction and preflight result.

### Per-system PII policy

Systems can be registered and edited from the UI. Each system has a PII policy:

- `REDACT` (default)
- `BLOCK`
- `ALLOW` for approved workflows

### Dashboard controls and evidence

The dashboard now includes:

- a distinct Governance Tower overview with live KPIs;
- a Run Gateway action workspace;
- Systems, Runs, and Incidents search/filter controls, including date ranges;
- run drill-down pages with input, output, safety flags, preflight decision, a PII Redacted badge, and a safe preview that withholds original values;
- incident review workflow (status, reviewer, and notes);
- an Audit page for risk evaluations, incidents, reviews, and seeded events;
- CSV exports for filtered runs and incidents;
- dark mode and action toast feedback;
- an idempotent Seed Demo Data button that creates two systems, three runs, two incidents, and audit events without duplicate records.

### Metadata scanning

Table scans are idempotent. Re-scanning updates existing table/column metadata and removes legacy duplicate rows instead of creating duplicate metadata records.

---

# Codex Contribution Summary

Codex (GPT-5.6) was used as a collaborative engineering assistant during development. It helped inspect the FastAPI/SQLAlchemy/Jinja application, implement scoped features, and run local verification checks. Its contributions included:

- building the dashboard navigation, Governance Gateway input workspace, live response view, cURL preview, dark-mode preference, and toast feedback;
- improving Systems, Runs, Incidents, Metadata, Documents, Diagrams, and detail-page presentation;
- adding system registration/editing, page filters, date ranges, run drill-down, incident review controls, audit evidence, and CSV report exports;
- implementing pre-model governance controls: PII redaction, typed redaction flags, phishing preflight decisions, per-system PII policies, and safe previews that withhold original sensitive values;
- making metadata scans and demo-data seeding idempotent;
- diagnosing and correcting the SQLite `pii_policy` migration issue; and
- validating Python compilation, database migration behavior, page responses, and isolated safety/redaction cases.

The project author retains ownership of the application design, the governance policies, all final implementation decisions, and the submitted work.