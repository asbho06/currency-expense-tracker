import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from .models import Base

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Absolute path so the same database is used no matter where the app is started from
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'expenses.db'}")
SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() in ("1", "true", "yes")

engine = create_engine(DATABASE_URL, echo=SQL_ECHO)
SessionLocal = sessionmaker(bind=engine)


def init_db(bind=None) -> None:
    bind = bind or engine
    Base.metadata.create_all(bind)

    # create_all() only creates missing tables, it never adds columns to existing ones,
    # so databases from older versions of the app get their new columns added here.
    columns = {col["name"] for col in inspect(bind).get_columns("expenses")}
    with bind.begin() as conn:
        if "trip_id" not in columns:
            conn.execute(text("ALTER TABLE expenses ADD COLUMN trip_id INTEGER REFERENCES trips(id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_expenses_trip_id ON expenses (trip_id)"))
        if "status" not in columns:
            conn.execute(text("ALTER TABLE expenses ADD COLUMN status VARCHAR NOT NULL DEFAULT 'spent'"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
