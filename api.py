from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from openai import OpenAI

from db import get_session, init_db
from models import AiSystem
from governance import governance_gateway
from safety import detect_pii
import os

from dotenv import load_dotenv
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI(title="AI Governance Control Tower")

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
    system = session.query(AiSystem).filter_by(name=payload.system_name).first()
    if not system:
        raise HTTPException(status_code=404, detail="AI system not registered")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": payload.input_payload["message"]}
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
