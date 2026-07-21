from uuid import uuid4
from typing import Dict, Any
from sqlalchemy.orm import Session
from models import ModelRun, Incident, AuditEvent, RiskLevel, TableMetadata


PII_COLUMN_TERMS = {
    "email": "EMAIL",
    "phone": "PHONE",
    "address": "ADDRESS",
    "ssn": "SSN",
    "social_security": "SSN",
    "passport": "PASSPORT",
    "driver_license": "DRIVER_LICENSE",
    "date_of_birth": "DATE_OF_BIRTH",
    "dob": "DATE_OF_BIRTH",
    "credit_card": "CREDIT_CARD",
    "bank_account": "BANK_ACCOUNT",
}


def scan_table_for_pii(table: Dict[str, Any]) -> list[Dict[str, Any]]:
    """Classify the supplied table metadata using PII-related column names."""
    results = []
    for column in table.get("columns", []):
        name = column["name"]
        normalized_name = name.lower().replace("-", "_").replace(" ", "_")
        tags = [
            tag
            for term, tag in PII_COLUMN_TERMS.items()
            if term in normalized_name
        ]
        results.append(
            {
                "column": name,
                "type": column.get("type", "unknown"),
                "tags": tags or ["NON_PII"],
            }
        )
    return results

def store_table_metadata_scan(session: Session, table_name: str, results: list[Dict[str, Any]]) -> dict[str, int]:
    """Upsert metadata by table/column and remove legacy duplicate rows."""
    created = updated = duplicates_removed = 0
    for result in results:
        records = (
            session.query(TableMetadata)
            .filter_by(table_name=table_name, column_name=result["column"])
            .order_by(TableMetadata.id)
            .all()
        )
        tags = ",".join(result["tags"])
        if records:
            metadata = records[0]
            metadata.column_type = result["type"]
            metadata.tags = tags
            updated += 1
            for duplicate in records[1:]:
                session.delete(duplicate)
                duplicates_removed += 1
        else:
            session.add(TableMetadata(table_name=table_name, column_name=result["column"], column_type=result["type"], tags=tags))
            created += 1
    return {"created": created, "updated": updated, "duplicates_removed": duplicates_removed}

def simple_risk_engine(system_risk_level: str, safety_flags: Dict[str, Any]):
    base = {
        "LOW": 0.2,
        "MEDIUM": 0.5,
        "HIGH": 0.7,
        "CRITICAL": 0.9,
    }.get(system_risk_level, 0.5)

    if safety_flags.get("pii_detected"):
        base += 0.2
    if safety_flags.get("toxicity_score", 0) > 0.7:
        base += 0.2

    score = min(base, 1.0)

    if score < 0.3:
        level = RiskLevel.LOW
    elif score < 0.6:
        level = RiskLevel.MEDIUM
    elif score < 0.8:
        level = RiskLevel.HIGH
    else:
        level = RiskLevel.CRITICAL

    return score, level

def should_route_to_review(risk_level: RiskLevel, safety_flags: Dict[str, Any]):
    if risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
        return True
    if safety_flags.get("pii_detected"):
        return True
    if safety_flags.get("policy_violation"):
        return True
    return False

def log_audit(session: Session, entity_type: str, entity_id: int, event_type: str, actor: str, metadata: Dict[str, Any]):
    event = AuditEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        event_type=event_type,
        actor=actor,
        event_metadata=metadata,
    )
    session.add(event)

def governance_gateway(session: Session, system, input_payload, model_output, safety_flags, actor="gateway"):
    request_id = str(uuid4())

    risk_score, risk_level = simple_risk_engine(system.risk_level, safety_flags)
    requires_review = should_route_to_review(risk_level, safety_flags)

    run = ModelRun(
        system_id=system.id,
        request_id=request_id,
        input_payload=input_payload,
        output_payload=model_output,
        risk_score=risk_score,
        risk_level=risk_level.value,
        safety_flags=safety_flags,
        requires_review=requires_review,
    )
    session.add(run)
    session.flush()

    log_audit(session, "ModelRun", run.id, "RISK_EVALUATED", actor, {
        "risk_score": risk_score,
        "risk_level": risk_level.value,
        "safety_flags": safety_flags,
    })

    incident = None
    if requires_review:
        incident = Incident(
            run_id=run.id,
            type="POLICY" if safety_flags.get("policy_violation") else "SAFETY",
            status="OPEN",
        )
        session.add(incident)
        session.flush()

        log_audit(session, "Incident", incident.id, "INCIDENT_OPENED", actor, {
            "run_id": run.id,
        })

    session.commit()
    return run, incident
