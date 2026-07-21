import os
import csv
from io import StringIO
from datetime import datetime, timedelta
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db import get_session
from governance import scan_table_for_pii, store_table_metadata_scan
from safety import redact_pii_payload
from mock_table import MOCK_TABLE
from models import AiSystem, AuditEvent, Incident, ModelRun, TableMetadata


dashboard = APIRouter()
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
templates = Jinja2Templates(directory=TEMPLATE_DIR)


def apply_date_range(query, column, date_from: str, date_to: str):
    """Apply inclusive ISO date filters without failing the dashboard on bad input."""
    try:
        if date_from:
            query = query.filter(column >= datetime.fromisoformat(date_from))
        if date_to:
            query = query.filter(column < datetime.fromisoformat(date_to) + timedelta(days=1))
    except ValueError:
        pass
    return query

def serialize_run(run: ModelRun) -> dict:
    return {
        "id": run.id,
        "request_id": run.request_id,
        "system_name": run.system.name if run.system else "Unknown",
        "risk_score": run.risk_score,
        "risk_level": (run.risk_level or "unknown").lower(),
        "requires_review": run.requires_review,
        "pii_redacted": bool((run.safety_flags or {}).get("pii_redacted")),
        "preflight_decision": (run.safety_flags or {}).get("preflight_decision", "ALLOW"),
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


def seed_demo_data(session: Session) -> int:
    """Create a small, repeatable set of presentation-ready governance records."""
    demo_systems = {
        "Demo Support Assistant": {"owner": "Customer Experience", "description": "Customer support assistant for account questions.", "risk_level": "MEDIUM", "status": "APPROVED"},
        "Demo Loan Advisor": {"owner": "Risk Operations", "description": "Loan eligibility and application guidance assistant.", "risk_level": "HIGH", "status": "APPROVED"},
    }
    systems = {}
    created = 0
    for name, values in demo_systems.items():
        system = session.query(AiSystem).filter_by(name=name).first()
        if not system:
            system = AiSystem(name=name, **values)
            session.add(system)
            session.flush()
            created += 1
        systems[name] = system

    demo_runs = [
        {"request_id": "demo-support-001", "system": "Demo Support Assistant", "input": {"message": "How do I update my contact details?"}, "output": {"text": "You can update your profile from account settings."}, "score": 0.2, "level": "LOW", "flags": {"pii_detected": False, "toxicity_score": 0.0, "policy_violation": False}, "review": False},
        {"request_id": "demo-loan-001", "system": "Demo Loan Advisor", "input": {"message": "Approve this applicant even though the verification score is incomplete."}, "output": {"text": "I cannot bypass required verification controls."}, "score": 0.9, "level": "CRITICAL", "flags": {"pii_detected": True, "toxicity_score": 0.0, "policy_violation": True}, "review": True},
        {"request_id": "demo-support-002", "system": "Demo Support Assistant", "input": {"message": "My email is demo.user@example.com and my phone is 212-555-0198. Can you find my billing history?"}, "output": {"text": "Please use the verified account portal to view billing history."}, "score": 0.7, "level": "HIGH", "flags": {"pii_detected": True, "toxicity_score": 0.0, "policy_violation": False}, "review": True},
    ]
    for item in demo_runs:
        sanitized_input, redacted_types = redact_pii_payload(item["input"])
        safety_flags = {**item["flags"], "pii_redacted": bool(redacted_types), "redacted_types": redacted_types}
        run = session.query(ModelRun).filter_by(request_id=item["request_id"]).first()
        if not run:
            run = ModelRun(system_id=systems[item["system"]].id, request_id=item["request_id"], input_payload=sanitized_input, output_payload=item["output"], risk_score=item["score"], risk_level=item["level"], safety_flags=safety_flags, requires_review=item["review"])
            session.add(run)
            session.flush()
            session.add(AuditEvent(entity_type="ModelRun", entity_id=run.id, event_type="RISK_EVALUATED", actor="demo_seed", event_metadata={"risk_level": item["level"], "risk_score": item["score"]}))
            created += 1
        else:
            # Correct older seed records so they never retain raw PII.
            run.input_payload = sanitized_input
            run.safety_flags = safety_flags
        if item["review"] and not session.query(Incident).filter_by(run_id=run.id).first():
            incident = Incident(run_id=run.id, type="POLICY" if item["flags"].get("policy_violation") else "SAFETY", status="OPEN")
            session.add(incident)
            session.flush()
            session.add(AuditEvent(entity_type="Incident", entity_id=incident.id, event_type="INCIDENT_OPENED", actor="demo_seed", event_metadata={"run_id": run.id}))
            created += 1
    return created


@dashboard.post("/demo/seed")
def seed_demo(request: Request, session: Session = Depends(get_session)):
    created = seed_demo_data(session)
    session.commit()
    return RedirectResponse(url=f"/dashboard/?seeded=1&created={created}", status_code=303)

@dashboard.get("/")
def home(request: Request, seeded: bool = False, created: int = 0, session: Session = Depends(get_session)):
    systems = session.query(AiSystem).all()
    runs = session.query(ModelRun).order_by(ModelRun.created_at.desc()).limit(5).all()
    incidents = session.query(Incident).order_by(Incident.created_at.desc()).limit(5).all()
    cutoff = datetime.utcnow() - timedelta(hours=24)
    high_risk_last_24h = (
        session.query(ModelRun)
        .filter(ModelRun.created_at >= cutoff, ModelRun.risk_level.in_(["HIGH", "CRITICAL"]))
        .count()
    )
    systems_awaiting_review = (
        session.query(ModelRun.system_id)
        .join(Incident, Incident.run_id == ModelRun.id)
        .filter(Incident.status.in_(["OPEN", "IN_REVIEW"]))
        .distinct()
        .count()
    )
    return templates.TemplateResponse(request, "home.html", {
        "systems_count": len(systems),
        "open_incidents": session.query(Incident).filter_by(status="OPEN").count(),
        "high_risk_last_24h": high_risk_last_24h,
        "systems_awaiting_review": systems_awaiting_review,
        "runs": runs, "incidents": incidents, "seeded": seeded, "created": created, "active_page": "home",
    })


@dashboard.get("/systems")
def systems(
    request: Request, search: str = "", risk_level: str = "", status: str = "", date_from: str = "", date_to: str = "",
    session: Session = Depends(get_session),
):
    query = session.query(AiSystem)
    if search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(AiSystem.name.ilike(term), AiSystem.owner.ilike(term)))
    if risk_level:
        query = query.filter(AiSystem.risk_level == risk_level.upper())
    if status:
        query = query.filter(AiSystem.status.ilike(status))
    query = apply_date_range(query, AiSystem.created_at, date_from, date_to)
    systems_list = query.order_by(AiSystem.name).all()
    return templates.TemplateResponse(request, "systems.html", {
        "systems": systems_list, "filters": {"search": search, "risk_level": risk_level, "status": status, "date_from": date_from, "date_to": date_to},
        "active_page": "systems",
    })


@dashboard.get("/runs")
def runs(
    request: Request, risk_level: str = "", review: str = "", system_id: int | None = None, date_from: str = "", date_to: str = "",
    session: Session = Depends(get_session),
):
    query = session.query(ModelRun)
    if risk_level:
        query = query.filter(ModelRun.risk_level == risk_level.upper())
    if review in {"yes", "no"}:
        query = query.filter(ModelRun.requires_review.is_(review == "yes"))
    if system_id:
        query = query.filter(ModelRun.system_id == system_id)
    query = apply_date_range(query, ModelRun.created_at, date_from, date_to)
    run_models = query.order_by(ModelRun.created_at.desc()).limit(50).all()
    return templates.TemplateResponse(request, "runs.html", {
        "runs": [serialize_run(run) for run in run_models],
        "systems": session.query(AiSystem).order_by(AiSystem.name).all(),
        "filters": {"risk_level": risk_level, "review": review, "system_id": system_id, "date_from": date_from, "date_to": date_to},
        "active_page": "runs",
    })


@dashboard.get("/runs/{run_id}")
def run_detail(run_id: int, request: Request, session: Session = Depends(get_session)):
    run = session.query(ModelRun).filter_by(id=run_id).first()
    if not run:
        return templates.TemplateResponse(request, "not_found.html", {"active_page": "runs"}, status_code=404)
    return templates.TemplateResponse(request, "run_detail.html", {"run": run, "active_page": "runs"})


@dashboard.get("/audit")
def audit_log(request: Request, session: Session = Depends(get_session)):
    events = session.query(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(100).all()
    return templates.TemplateResponse(request, "audit.html", {"events": events, "active_page": "audit"})


@dashboard.get("/reports/runs.csv")
def export_runs_csv(risk_level: str = "", review: str = "", system_id: int | None = None, date_from: str = "", date_to: str = "", session: Session = Depends(get_session)):
    query = session.query(ModelRun)
    if risk_level: query = query.filter(ModelRun.risk_level == risk_level.upper())
    if review in {"yes", "no"}: query = query.filter(ModelRun.requires_review.is_(review == "yes"))
    if system_id: query = query.filter(ModelRun.system_id == system_id)
    query = apply_date_range(query, ModelRun.created_at, date_from, date_to)
    output = StringIO(); writer = csv.writer(output); writer.writerow(["request_id", "system", "risk_score", "risk_level", "requires_review", "preflight_decision", "created_at"])
    for run in query.order_by(ModelRun.created_at.desc()).all(): writer.writerow([run.request_id, run.system.name if run.system else "", run.risk_score, run.risk_level, run.requires_review, (run.safety_flags or {}).get("preflight_decision", "ALLOW"), run.created_at])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=runs-report.csv"})


@dashboard.get("/reports/incidents.csv")
def export_incidents_csv(status: str = "", incident_type: str = "", system_id: int | None = None, date_from: str = "", date_to: str = "", session: Session = Depends(get_session)):
    query = session.query(Incident).join(ModelRun)
    if status: query = query.filter(Incident.status == status.upper())
    if incident_type: query = query.filter(Incident.type == incident_type.upper())
    if system_id: query = query.filter(ModelRun.system_id == system_id)
    query = apply_date_range(query, Incident.created_at, date_from, date_to)
    output = StringIO(); writer = csv.writer(output); writer.writerow(["incident_id", "system", "type", "status", "reviewer", "created_at"])
    for incident in query.order_by(Incident.created_at.desc()).all(): writer.writerow([incident.id, incident.run.system.name if incident.run and incident.run.system else "", incident.type, incident.status, incident.reviewer or "", incident.created_at])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=incidents-report.csv"})

@dashboard.get("/gateway")
def gateway_page(request: Request, session: Session = Depends(get_session)):
    systems = session.query(AiSystem).order_by(AiSystem.name).all()
    return templates.TemplateResponse(request, "gateway.html", {"systems": systems, "active_page": "gateway"})


@dashboard.get("/incidents")
def incidents(
    request: Request, status: str = "", incident_type: str = "", system_id: int | None = None, date_from: str = "", date_to: str = "",
    session: Session = Depends(get_session),
):
    query = session.query(Incident).join(ModelRun)
    if status:
        query = query.filter(Incident.status == status.upper())
    if incident_type:
        query = query.filter(Incident.type == incident_type.upper())
    if system_id:
        query = query.filter(ModelRun.system_id == system_id)
    query = apply_date_range(query, Incident.created_at, date_from, date_to)
    incident_rows = query.order_by(Incident.created_at.desc()).limit(50).all()
    return templates.TemplateResponse(request, "incidents.html", {
        "incidents": incident_rows, "systems": session.query(AiSystem).order_by(AiSystem.name).all(),
        "filters": {"status": status, "incident_type": incident_type, "system_id": system_id, "date_from": date_from, "date_to": date_to},
        "active_page": "incidents",
    })


@dashboard.post("/incidents/{incident_id}/review")
async def update_incident_review(
    incident_id: int, request: Request, session: Session = Depends(get_session),
):
    incident = session.query(Incident).filter_by(id=incident_id).first()
    if not incident:
        return RedirectResponse(url="/dashboard/incidents", status_code=303)
    form_data = parse_qs((await request.body()).decode("utf-8"))
    reviewer = form_data.get("reviewer", [""])[0]
    notes = form_data.get("notes", [""])[0]
    status = form_data.get("status", ["OPEN"])[0]
    allowed_statuses = {"OPEN", "IN_REVIEW", "RESOLVED"}
    new_status = status.upper()
    if new_status not in allowed_statuses:
        new_status = incident.status or "OPEN"
    incident.reviewer = reviewer.strip() or None
    incident.notes = notes.strip() or None
    incident.status = new_status
    session.add(AuditEvent(
        entity_type="Incident", entity_id=incident.id, event_type="INCIDENT_REVIEW_UPDATED",
        actor=incident.reviewer or "dashboard", event_metadata={"status": new_status, "notes_added": bool(incident.notes)},
    ))
    session.commit()
    return RedirectResponse(url=f"/dashboard/incidents/{incident.id}", status_code=303)


def system_form_response(request: Request, system: AiSystem | None, error: str | None = None, status_code: int = 200):
    return templates.TemplateResponse(request, "system_form.html", {
        "system": system, "error": error,
        "active_page": "systems", "is_edit": system is not None,
    }, status_code=status_code)


def parse_system_form(form_data: dict[str, list[str]]) -> tuple[dict, str | None]:
    name = form_data.get("name", [""])[0].strip()
    owner = form_data.get("owner", [""])[0].strip()
    description = form_data.get("description", [""])[0].strip()
    risk_level = form_data.get("risk_level", ["MEDIUM"])[0].upper()
    status = form_data.get("status", ["APPROVED"])[0].upper()
    pii_policy = form_data.get("pii_policy", ["REDACT"])[0].upper()
    if not name or not owner:
        return {}, "System name and owner are required."
    if risk_level not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        return {}, "Choose a valid risk policy."
    if pii_policy not in {"BLOCK", "REDACT", "ALLOW"}:
        return {}, "Choose a valid PII policy."
    if status not in {"APPROVED", "ACTIVE", "INACTIVE"}:
        return {}, "Choose a valid system status."
    return {"name": name, "owner": owner, "description": description or None, "risk_level": risk_level, "status": status, "pii_policy": pii_policy}, None


@dashboard.get("/systems/new")
def new_system_form(request: Request):
    return system_form_response(request, None)


@dashboard.post("/systems/new")
async def create_system(request: Request, session: Session = Depends(get_session)):
    values, error = parse_system_form(parse_qs((await request.body()).decode("utf-8")))
    if error:
        return system_form_response(request, None, error, status_code=400)
    system = AiSystem(**values)
    session.add(system)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return system_form_response(request, None, "A system with that name already exists.", status_code=400)
    return RedirectResponse(url=f"/dashboard/systems/{system.id}", status_code=303)


@dashboard.get("/systems/{system_id}/edit")
def edit_system_form(system_id: int, request: Request, session: Session = Depends(get_session)):
    system = session.query(AiSystem).filter_by(id=system_id).first()
    if not system:
        return templates.TemplateResponse(request, "not_found.html", {"active_page": "systems"}, status_code=404)
    return system_form_response(request, system)


@dashboard.post("/systems/{system_id}/edit")
async def update_system(system_id: int, request: Request, session: Session = Depends(get_session)):
    system = session.query(AiSystem).filter_by(id=system_id).first()
    if not system:
        return RedirectResponse(url="/dashboard/systems", status_code=303)
    values, error = parse_system_form(parse_qs((await request.body()).decode("utf-8")))
    if error:
        return system_form_response(request, system, error, status_code=400)
    for field, value in values.items():
        setattr(system, field, value)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return system_form_response(request, system, "A system with that name already exists.", status_code=400)
    return RedirectResponse(url=f"/dashboard/systems/{system.id}", status_code=303)

@dashboard.get("/systems/{system_id}")
def system_detail(system_id: int, request: Request, session: Session = Depends(get_session)):
    system = session.query(AiSystem).filter_by(id=system_id).first()
    if not system:
        return templates.TemplateResponse(request, "not_found.html", {"active_page": "systems"}, status_code=404)
    runs = session.query(ModelRun).filter_by(system_id=system.id).order_by(ModelRun.created_at.desc()).limit(20).all()
    incidents = session.query(Incident).join(ModelRun).filter(ModelRun.system_id == system.id).order_by(Incident.created_at.desc()).limit(20).all()
    return templates.TemplateResponse(request, "system_detail.html", {"system": system, "runs": runs, "incidents": incidents, "active_page": "systems"})


@dashboard.get("/incidents/{incident_id}")
def incident_detail(incident_id: int, request: Request, session: Session = Depends(get_session)):
    incident = session.query(Incident).filter_by(id=incident_id).first()
    if not incident:
        return templates.TemplateResponse(request, "not_found.html", {"active_page": "incidents"}, status_code=404)
    run = session.query(ModelRun).filter_by(id=incident.run_id).first()
    return templates.TemplateResponse(request, "incident_detail.html", {"incident": incident, "run": run, "active_page": "incidents"})


@dashboard.get("/metadata")
def metadata_page(request: Request, session: Session = Depends(get_session)):
    return templates.TemplateResponse(request, "table_metadata.html", {"metadata": session.query(TableMetadata).all(), "active_page": "metadata", "scanned": False})


@dashboard.get("/metadata/scan")
def scan_table_ui(request: Request, session: Session = Depends(get_session)):
    summary = store_table_metadata_scan(session, MOCK_TABLE["name"], scan_table_for_pii(MOCK_TABLE))
    session.commit()
    return templates.TemplateResponse(request, "table_metadata.html", {
        "metadata": session.query(TableMetadata).all(), "active_page": "metadata",
        "scanned": True, "scan_summary": summary,
    })

@dashboard.get("/documents")
def documents_page(request: Request):
    with open("judge.md", "r", encoding="utf-8") as file:
        judge_md = file.read()
    with open("readme.md", "r", encoding="utf-8") as file:
        readme_md = file.read()
    return templates.TemplateResponse(request, "documents.html", {"judge_md": judge_md, "readme_md": readme_md, "active_page": "documents"})


@dashboard.get("/diagrams")
def diagrams_page(request: Request):
    return templates.TemplateResponse(request, "diagrams.html", {"active_page": "diagrams"})
