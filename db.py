from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session
from models import Base

DATABASE_URL = "sqlite:///./governance.db"

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def init_db():
    Base.metadata.create_all(bind=engine)
    existing_columns = {
        column["name"] for column in inspect(engine).get_columns("ai_systems")
    }
    migrations = []
    if "status" not in existing_columns:
        migrations.append(
            "ALTER TABLE ai_systems ADD COLUMN status VARCHAR(32) DEFAULT 'APPROVED'"
        )
    if "created_at" not in existing_columns:
        migrations.append("ALTER TABLE ai_systems ADD COLUMN created_at DATETIME")

    if migrations:
        with engine.begin() as connection:
            for statement in migrations:
                connection.execute(text(statement))

def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
