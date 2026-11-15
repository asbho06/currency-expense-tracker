import os
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from . import crud
from .expenses_table import Base
from .schemas import ExpenseCreate, ExpenseRead, ExpenseSummary

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Absolute path so the same database is used no matter where the app is started from
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'expenses.db'}")
SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() in ("1", "true", "yes")

engine = create_engine(DATABASE_URL, echo=SQL_ECHO)
SessionLocal = sessionmaker(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Currency Expense Tracker", lifespan=lifespan)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/expenses", response_model=ExpenseRead)
def add_expense(expense: ExpenseCreate, db: Session = Depends(get_db)):
    return crud.create_expense(db, expense)


@app.get("/expenses", response_model=list[ExpenseRead])
def list_expenses(db: Session = Depends(get_db)):
    return crud.get_expenses(db)


@app.get("/expenses/filter", response_model=list[ExpenseRead])
def filter_expenses(
    category: Optional[str] = None,
    currency: Optional[str] = None,
    min_amount: Optional[Decimal] = None,
    max_amount: Optional[Decimal] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    return crud.filter_expenses(
        db, category, currency, min_amount, max_amount, start_date, end_date
    )


@app.get("/expenses/category/{category}", response_model=list[ExpenseRead])
def get_by_category(category: str, db: Session = Depends(get_db)):
    return crud.get_expenses_by_category(db, category)


@app.get("/expenses/summary/by-category", response_model=list[ExpenseSummary])
def summary_by_category(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    rows = crud.get_summary_by_category(db, start_date, end_date)
    return [
        {"category": category, "total_base_usd": total}
        for category, total in rows
    ]
