from fastapi import FastAPI, Depends
from fastapi.requests import Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from db import get_session
from models import AiSystem, ModelRun, Incident
from fastapi import Request, Depends
from sqlalchemy.orm import Session
from mock_table import MOCK_TABLE
from governance import scan_table_for_pii
from models import TableMetadata

import os

from fastapi import APIRouter
dashboard = APIRouter()

# Correct template directory
TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "templates"
)

templates = Jinja2Templates(directory=TEMPLATE_DIR)

print(">>> LOADED DASHBOARD API FROM:", __file__)


def serialize_run(run: ModelRun) -> dict:
    """Return the fields the dashboard can safely render and serialize to JSON."""
    return {
        "request_id": run.request_id,
        "system_name": run.system.name if run.system else "Unknown",
        "risk_score": run.risk_score,
        "risk_level": (run.risk_level or "unknown").lower(),
        "requires_review": run.requires_review,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


@dashboard.get("/")
def home(request: Request, session: Session = Depends(get_session)):
    systems = session.query(AiSystem).all()
    return templates.TemplateResponse(
        request,
        "systems.html",
        {"systems": systems, "active_page": "systems"},
    )



@dashboard.get("/systems")
def systems(request: Request, session: Session = Depends(get_session)):
    systems = session.query(AiSystem).all()
    return templates.TemplateResponse(
        request,
        "systems.html",
        {"systems": systems, "active_page": "systems"},
    )


@dashboard.get("/runs")
def runs(request: Request, session: Session = Depends(get_session)):
    runs = (
        session.query(ModelRun)
        .order_by(ModelRun.created_at.desc())
        .limit(50)
        .all()
    )
    run_rows = [serialize_run(run) for run in runs]
    return templates.TemplateResponse(
        request,
        "runs.html",
        {"runs": run_rows, "active_page": "runs"},
    )


@dashboard.get("/incidents")
def incidents(request: Request, session: Session = Depends(get_session)):
    incidents = (
        session.query(Incident)
        .order_by(Incident.created_at.desc())
        .limit(50)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "incidents.html",
        {"incidents": incidents, "active_page": "incidents"},
    )


@dashboard.get("/systems/{system_id}")
def system_detail(system_id: int, request: Request, session: Session = Depends(get_session)):
    system = session.query(AiSystem).filter_by(id=system_id).first()
    if not system:
        return templates.TemplateResponse(
            request,
            "not_found.html",
            {},
        )

    runs = (
        session.query(ModelRun)
        .filter_by(system_id=system.id)
        .order_by(ModelRun.created_at.desc())
        .limit(20)
        .all()
    )

    incidents = (
        session.query(Incident)
        .join(ModelRun)
        .filter(ModelRun.system_id == system.id)
        .order_by(Incident.created_at.desc())
        .limit(20)
        .all()
    )

    return templates.TemplateResponse(
        request,
        "system_detail.html",
        {
            "system": system,
            "runs": runs,
            "incidents": incidents,
            "active_page": "systems",
        },
    )


@dashboard.get("/incidents/{incident_id}")

def incident_detail(incident_id: int, request: Request, session: Session = Depends(get_session)):
    incident = session.query(Incident).filter_by(id=incident_id).first()
    if not incident:
        return templates.TemplateResponse(
            request,
            "not_found.html",
            {},
        )

    run = session.query(ModelRun).filter_by(id=incident.run_id).first()

    return templates.TemplateResponse(
        request,
        "incident_detail.html",
        {
            "incident": incident,
            "run": run,
            "active_page": "incidents",
        },
    )


@dashboard.get("/metadata")
def metadata_page(request: Request, session: Session = Depends(get_session)):
    return templates.TemplateResponse(
        request,
        "table_metadata.html",
        {
            "metadata": session.query(TableMetadata).all(),
            "active_page": "metadata",
            "scanned": False,
        },
    )

@dashboard.get("/metadata/scan")
def scan_table_ui(request: Request, session: Session = Depends(get_session)):
    # Run scan
    results = scan_table_for_pii(MOCK_TABLE)

    # Store metadata
    for r in results:
        meta = TableMetadata(
            table_name=MOCK_TABLE["name"],
            column_name=r["column"],
            column_type=r["type"],
            tags=",".join(r["tags"])
        )
        session.add(meta)

    session.commit()

    # Redirect to metadata page
    return templates.TemplateResponse(
        request,
        "table_metadata.html",
        {
            "metadata": session.query(TableMetadata).all(),
            "active_page": "metadata",
            "scanned": True,
        },
    )

@dashboard.get("/documents")
def documents_page(request: Request):
    with open("judge.md", "r", encoding="utf-8") as f:
        judge_md = f.read()

    with open("readme.md", "r", encoding="utf-8") as f:
        readme_md = f.read()

    return templates.TemplateResponse(
        request,
        "documents.html",
        {
            "judge_md": judge_md,
            "readme_md": readme_md,
            "active_page": "documents",
        },
    )

@dashboard.get("/diagrams")
def diagrams_page(request: Request):
    return templates.TemplateResponse(
        request,
        "diagrams.html",
        {"active_page": "diagrams"},
    )
