from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from openai import OpenAI

from db import get_session, init_db
from models import AiSystem
from governance import governance_gateway
from safety import detect_pii
from mock_table import MOCK_TABLE
from governance import scan_table_for_pii
from models import TableMetadata
from sqlalchemy.orm import Session
from fastapi import Depends

import os
from dotenv import load_dotenv

from dashboard.dashboard_api import dashboard

app = FastAPI(title="AI Governance Control Tower")

#Mount dashboard
app.include_router(dashboard, prefix="/dashboard")


# Add redirect for root URL
@app.get("/")
def root():
    return RedirectResponse(url="/dashboard")


load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))



class GatewayRequest(BaseModel):
    system_name: str
    input_payload: dict
    safety_flags: dict


class GatewayResponse(BaseModel):
    request_id: str
    risk_score: float
    risk_level: str
    requires_review: bool
    incident_id: int | None


@app.on_event("startup")
def startup():
    init_db()


@app.post("/gateway/run", response_model=GatewayResponse)
def route(payload: GatewayRequest, session: Session = Depends(get_session)):

    # -----------------------------
    # Validate system
    # -----------------------------
    system = session.query(AiSystem).filter_by(name=payload.system_name).first()
    if not system:
        raise HTTPException(status_code=404, detail="AI system not registered")

    USE_MOCK_MODEL = True

    # -----------------------------
    # MODEL CALL (REAL OR MOCK)
    # -----------------------------
    if USE_MOCK_MODEL:
        model_output_text = (
            "Mock response: This appears to contain harmful or policy-violating content."
        )

        safety_flags = {
            "pii_detected": True,
            "toxicity_score": 0.9,
            "policy_violation": True,
            "mock": True
        }

    else:
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "user", "content": payload.input_payload.get("message", "")}
                ]
            )

            model_output_text = response.choices[0].message.content

            safety_flags = {
                "pii_detected": detect_pii(
                    payload.input_payload.get("prompt")
                    or payload.input_payload.get("message", "")
                ),
                "toxicity_score": 0.0,
                "policy_violation": False
            }

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"OpenAI API error: {str(e)}"
            )

    # -----------------------------
    # GOVERNANCE ENGINE
    # -----------------------------
    run, incident = governance_gateway(
        session=session,
        system=system,
        input_payload=payload.input_payload,
        model_output={"text": model_output_text},
        safety_flags=safety_flags,
        actor="api"
    )

    return GatewayResponse(
        request_id=run.request_id,
        risk_score=run.risk_score,
        risk_level=run.risk_level,
        requires_review=run.requires_review,
        incident_id=incident.id if incident else None
    )


@app.post("/governance/scan-table")
def scan_table(session: Session = Depends(get_session)):
    # Run governance scan
    results = scan_table_for_pii(MOCK_TABLE)

    # Store metadata in DB
    for r in results:
        meta = TableMetadata(
            table_name=MOCK_TABLE["name"],
            column_name=r["column"],
            column_type=r["type"],
            tags=",".join(r["tags"])
        )
        session.add(meta)

    session.commit()

    return {
        "table": MOCK_TABLE["name"],
        "results": results
    }
