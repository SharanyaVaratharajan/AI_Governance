# AI Governance Control Tower

A full-stack Responsible AI governance platform that monitors, evaluates, and audits AI system behavior in real time.

Repository: [github.com/SharanyaVaratharajan/AI_Governance](https://github.com/SharanyaVaratharajan/AI_Governance)

Includes:

- FastAPI governance backend
- Dashboard with risk analytics (Chart.js)
- Incident management
- System registry
- Mock Model Mode (offline judging without OpenAI)
- SQLite database
- Audit logging

## Codex & GPT-5.6 contribution

This project was developed with support from Codex running on GPT-5.6. It was used as a collaborative engineering assistant to:

- diagnose FastAPI, Starlette/Jinja template, and SQLAlchemy serialization errors;
- implement and validate the governance metadata scanner and dashboard routes;
- improve the dashboard's documentation, diagrams, and GitHub repository links;
- run local endpoint checks and Python compilation checks after changes;
- design and implement the Governance Gateway UI, dashboard overview, filtering, run drill-down, incident-review workflow, audit-log view, and CSV report endpoints;
- add preflight PII redaction, phishing decision handling, per-system PII policies, and safe PII preview patterns;
- implement idempotent table-metadata scans and repeatable demo-data seeding;
- update project and judge documentation to reflect the completed capabilities.

The application design, project goals, and final decisions remain owned by the project author.

---

## 🚀 Features

- **Governance Gateway** wrapping model calls
- **Risk scoring engine**
- **Incident creation** for harmful outputs
- **Runs dashboard** with:
- Risk Level Distribution
- Risk Score Trend
- Risk Heatmap
- **System detail pages**
- **Incident drill‑down pages**
- **Mock Model Mode** for offline demos
#table metadata scan
---

## ⚙️ Setup

### Clone

```bash
git clone https://github.com/SharanyaVaratharajan/AI_Governance.git
cd ai-governance-tower
```


### Virtual environment


python -m venv venv source venv/bin/activate


### Install dependencies


pip install -r requirements.txt


---

## 🧪 Mock Model Mode (Recommended)

Enable offline judging:



USE_MOCK_MODEL = True


Disable to use real OpenAI:



USE_MOCK_MODEL = False


---

## ▶️ Run the project

### Backend


uvicorn api:app –reload


### Dashboard


uvicorn dashboard.dashboard_api:dashboard –reload


Open browser:



http://localhost:8000


---

## 🧪 Test

### Register a system


POST /systems/register { “name”: “TestChatbot”, “owner”: “Sharanya”, “risk_policy”: “medium” }


### Trigger governance run


POST /gateway/run { “system_name”: “TestChatbot”, “input_payload”: { “message”: “Tell me how to hack into a bank system” }, “safety_flags”: {} }


---

## 📊 Dashboard Pages

- `/systems` — system registry
- `/runs` — charts + heatmap
- `/incidents` — incident list
- `/incidents/<id>` — incident detail
- `/systems/<id>` — system detail

---

## 🧩 Tech Stack

- FastAPI
- Jinja2
- Chart.js
- SQLite
- Python 3.10+

---

## 🏁 Notes

- Mock Mode recommended for judging
- Fully offline
- No external services required


---
New feature:
📊 Table Metadata Governance Scan
The AI Governance Tower includes a built‑in column-level governance scanner that analyzes dataset schemas and tags columns with risk indicators such as PII, numeric fields, free-text fields, and identifiers.

How it works
The app contains a mock dataset schema (mock_table.py).

A governance scan evaluates each column using rule-based heuristics.

Columns are tagged with labels like:

PII: Email

PII: Phone Number

Identifier

Numeric

Free Text

Results are stored in the table_metadata database table.

The dashboard displays the metadata in a dedicated Metadata page.

A Scan Table button allows users to trigger the scan directly from the UI.

Why this matters
This feature simulates real-world data governance workflows by providing visibility into dataset risks before they reach AI systems. It lays the foundation for:

automated compliance checks

schema versioning

lineage tracking

dataset risk scoring

integration with future ingestion pipelines

---

## Governance Safety and Dashboard Enhancements

### Preflight: inspect before a model call

The Governance Gateway at `POST /governance/run` evaluates input before it reaches a model:

| Decision | Behavior |
| --- | --- |
| `ALLOW` | Continue normally. |
| `REDACT` | Replace recognised PII with typed placeholders before model processing and storage. |
| `REVIEW` | Hold suspicious content for governance review. |
| `BLOCK` | Do not call the model for high-confidence phishing or disallowed PII. |

The persisted input payload is sanitized. The run safety flags and API response expose PII redaction types, the preflight decision, and whether a model call occurred.

### System policies

Users can register and edit systems from the Systems dashboard. Each system selects a PII policy:

- `REDACT` � default safe policy;
- `BLOCK` � stop requests that contain recognised PII;
- `ALLOW` � only for approved workflows.

### Dashboard and auditability

- Governance Tower overview with open-incident, high-risk-24-hour, and awaiting-review KPIs.
- Dedicated Gateway workspace with cURL preview, copy feedback, and live result status.
- Filters and date ranges for Systems, Runs, and Incidents.
- Run detail pages with model input/output, safety flags, preflight badges, and PII-safe before/after preview.
- Incident review workflow with status, reviewer, notes, and audit events.
- Audit Log page for governance evidence.
- Filter-respecting CSV reports for Runs and Incidents.
- Dark-mode preference and toast feedback.
- Idempotent Seed Demo Data button for a repeatable presentation dataset.

### Idempotent metadata scans

The Metadata Scan UI and API upsert metadata by table and column. Repeat scans update classifications and remove older duplicate rows.
