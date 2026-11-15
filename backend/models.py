from datetime import datetime, timezone

from sqlalchemy import JSON, Column, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    home_currency = Column(String(3), nullable=False)   # currency the budget is in, e.g. USD
    local_currency = Column(String(3), nullable=False)  # currency at the destination, e.g. JPY
    budget = Column(Numeric(12, 2), nullable=False)     # total budget, in home_currency
    # Optional per-category limits in home_currency, e.g. {"hotel": "400.00", "food": "250.00"}
    category_budgets = Column(JSON, nullable=False, default=dict)
    start_date = Column(Date)
    end_date = Column(Date)
    created_at = Column(DateTime, default=utcnow)

    expenses = relationship(
        "Expense",
        back_populates="trip",
        cascade="all, delete-orphan",
        order_by="Expense.expense_date",
    )


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), index=True)
    # Numeric instead of Float so money values don't pick up rounding errors
    amount_original = Column(Numeric(12, 2), nullable=False)
    currency_original = Column(String(3), nullable=False)
    amount_base = Column(Numeric(12, 2), nullable=False)  # converted to base_currency
    base_currency = Column(String(3), nullable=False)
    fx_rate = Column(Numeric(18, 8), nullable=False)       # rate used at the time of entry
    category = Column(String)
    # "planned" = expected cost not paid yet, "spent" = actually paid
    status = Column(String, nullable=False, default="spent", server_default="spent")
    expense_date = Column(DateTime)
    note = Column(String)
    created_at = Column(DateTime, default=utcnow)

    trip = relationship("Trip", back_populates="expenses")
