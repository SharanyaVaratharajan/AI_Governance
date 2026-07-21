from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from openai import OpenAI

from db import get_session, init_db
from models import AiSystem
from governance import governance_gateway
from safety import assess_phishing_risk, detect_pii, redact_pii_payload
from mock_table import MOCK_TABLE
from governance import scan_table_for_pii, store_table_metadata_scan
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
    pii_redacted: bool
    redacted_types: list[str]
    preflight_decision: str


@app.on_event("startup")
def startup():
    init_db()


@app.post("/governance/run", response_model=GatewayResponse)
@app.post("/gateway/run", response_model=GatewayResponse, include_in_schema=False)
def route(payload: GatewayRequest, session: Session = Depends(get_session)):

    # -----------------------------
    # Validate system
    # -----------------------------
    system = session.query(AiSystem).filter_by(name=payload.system_name).first()
    if not system:
        raise HTTPException(status_code=404, detail="AI system not registered")

    sanitized_input, redacted_types = redact_pii_payload(payload.input_payload)
    input_text = str(sanitized_input.get("prompt") or sanitized_input.get("message", ""))
    pii_detected = detect_pii(input_text) or bool(redacted_types)
    pii_policy = (system.pii_policy or "REDACT").upper()
    phishing_decision = assess_phishing_risk(payload.input_payload)
    preflight_decision = phishing_decision
    if phishing_decision == "ALLOW" and redacted_types:
        preflight_decision = "BLOCK" if pii_policy == "BLOCK" else ("ALLOW" if pii_policy == "ALLOW" else "REDACT")
    model_input = payload.input_payload if pii_policy == "ALLOW" and phishing_decision == "ALLOW" else sanitized_input

    USE_MOCK_MODEL = True

    # -----------------------------
    # MODEL CALL (REAL OR MOCK)
    # -----------------------------
    if preflight_decision in {"BLOCK", "REVIEW"}:
        model_output_text = f"Request {preflight_decision.lower()}ed by the governance preflight."
        safety_flags = {"pii_detected": pii_detected, "pii_redacted": bool(redacted_types), "redacted_types": redacted_types, "phishing_decision": phishing_decision, "preflight_decision": preflight_decision, "toxicity_score": 0.0, "policy_violation": True, "model_called": False}
    elif USE_MOCK_MODEL:
        model_output_text = (
            "Mock response: This appears to contain harmful or policy-violating content."
        )

        safety_flags = {
            "pii_detected": pii_detected,
            "pii_redacted": bool(redacted_types),
            "redacted_types": redacted_types,
            "toxicity_score": 0.9,
            "policy_violation": True,
            "mock": True,
            "phishing_decision": phishing_decision,
            "preflight_decision": preflight_decision,
            "model_called": True
        }

    else:
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "user", "content": model_input.get("message", "")}
                ]
            )

            model_output_text = response.choices[0].message.content

            safety_flags = {
                "pii_detected": pii_detected,
                "pii_redacted": bool(redacted_types),
                "redacted_types": redacted_types,
                "toxicity_score": 0.0,
                "policy_violation": False,
                "phishing_decision": phishing_decision,
                "preflight_decision": preflight_decision,
                "model_called": True,
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
        input_payload=sanitized_input,
        model_output={"text": model_output_text},
        safety_flags=safety_flags,
        actor="api"
    )

    return GatewayResponse(
        request_id=run.request_id,
        risk_score=run.risk_score,
        risk_level=run.risk_level,
        requires_review=run.requires_review,
        incident_id=incident.id if incident else None,
        pii_redacted=bool(redacted_types),
        redacted_types=redacted_types,
        preflight_decision=preflight_decision
    )


@app.post("/governance/scan-table")
def scan_table(session: Session = Depends(get_session)):
    # Run governance scan
    results = scan_table_for_pii(MOCK_TABLE)

    summary = store_table_metadata_scan(session, MOCK_TABLE["name"], results)
    session.commit()

    return {
        "table": MOCK_TABLE["name"],
        "results": results,
        "summary": summary,
    }
