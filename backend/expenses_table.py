from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, Numeric, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True)
    # Numeric instead of Float so money values don't pick up rounding errors
    amount_original = Column(Numeric(12, 2), nullable=False)
    currency_original = Column(String(3), nullable=False)
    amount_base = Column(Numeric(12, 2), nullable=False)
    base_currency = Column(String(3), nullable=False)
    fx_rate = Column(Numeric(18, 8), nullable=False)
    category = Column(String)
    expense_date = Column(DateTime)
    note = Column(String)
    created_at = Column(DateTime, default=utcnow)
