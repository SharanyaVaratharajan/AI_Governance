from datetime import datetime
from enum import Enum
from sqlalchemy import (
Column, Integer, String, DateTime, Text, Boolean, Float, ForeignKey, JSON
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class AiSystem(Base):
    __tablename__ = "ai_systems"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    owner = Column(String(255), nullable=False)
    description = Column(Text)
    risk_level = Column(String(32), default=RiskLevel.MEDIUM.value)
    status = Column(String(32), default="APPROVED")
    created_at = Column(DateTime, default=datetime.utcnow)

    runs = relationship("ModelRun", back_populates="system")

class ModelRun(Base):
    __tablename__ = "model_runs"

    id = Column(Integer, primary_key=True)
    system_id = Column(Integer, ForeignKey("ai_systems.id"), nullable=False)
    request_id = Column(String(64), unique=True, nullable=False)
    input_payload = Column(JSON, nullable=False)
    output_payload = Column(JSON)
    risk_score = Column(Float)
    risk_level = Column(String(32))
    safety_flags = Column(JSON)
    requires_review = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    system = relationship("AiSystem", back_populates="runs")
    incident = relationship(
        "Incident",
        back_populates="run",
        foreign_keys="Incident.run_id",
        uselist=False,
    )

class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("model_runs.id"), nullable=False)
    type = Column(String(64))
    status = Column(String(32), default="OPEN")
    reviewer = Column(String(255))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    run = relationship(
        "ModelRun",
        back_populates="incident",
        foreign_keys=[run_id],
    )

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True)
    entity_type = Column(String(64))
    entity_id = Column(Integer, nullable=False)
    event_type = Column(String(64))
    actor = Column(String(255))
    event_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class TableMetadata(Base):
    __tablename__ = "table_metadata"

    id = Column(Integer, primary_key=True)
    table_name = Column(String(255), nullable=False)
    column_name = Column(String(255), nullable=False)
    column_type = Column(String(64), nullable=False)
    tags = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
