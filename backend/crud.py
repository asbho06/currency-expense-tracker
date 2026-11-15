import os
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

import requests
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Query, Session

from .expenses_table import Expense, utcnow
from .schemas import ExpenseCreate

BASE_CURRENCY = "USD"
FX_API_BASE = "https://v6.exchangerate-api.com/v6"
CENTS = Decimal("0.01")


def get_fx_rate(from_currency: str, to_currency: str) -> Decimal:
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    if from_currency == to_currency:
        return Decimal("1")

    # Read at call time so the key is picked up after load_dotenv() runs
    api_key = os.getenv("FX_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="FX_API_KEY is not set")

    url = f"{FX_API_BASE}/{api_key}/latest/{from_currency}"

    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Failed to fetch exchange rates")

    rate = data.get("conversion_rates", {}).get(to_currency)
    if rate is None:
        raise HTTPException(status_code=502, detail="Exchange rate not available")

    # str() avoids carrying float binary noise into the Decimal
    return Decimal(str(rate))


def convert_currency(amount: Decimal, currency: str) -> tuple[Decimal, Decimal]:
    fx_rate = get_fx_rate(currency, BASE_CURRENCY)
    amount_base = (amount * fx_rate).quantize(CENTS, rounding=ROUND_HALF_UP)
    return amount_base, fx_rate


def create_expense(db: Session, expense: ExpenseCreate) -> Expense:
    amount_base, fx_rate = convert_currency(expense.amount, expense.currency)

    db_expense = Expense(
        amount_original=expense.amount,
        currency_original=expense.currency.upper(),
        amount_base=amount_base,
        base_currency=BASE_CURRENCY,
        fx_rate=fx_rate,
        category=expense.category,
        expense_date=expense.expense_date or utcnow(),
        note=expense.note,
    )

    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense


def _apply_date_range(query: Query, start_date: Optional[date], end_date: Optional[date]) -> Query:
    if start_date:
        query = query.filter(Expense.expense_date >= datetime.combine(start_date, time.min))
    if end_date:
        # Exclusive upper bound on the next day so the whole end date is included
        query = query.filter(
            Expense.expense_date < datetime.combine(end_date + timedelta(days=1), time.min)
        )
    return query


def get_expenses(db: Session) -> list[Expense]:
    return db.query(Expense).all()


def get_expenses_by_category(db: Session, category: str) -> list[Expense]:
    return db.query(Expense).filter(Expense.category == category).all()


def filter_expenses(
    db: Session,
    category: Optional[str] = None,
    currency: Optional[str] = None,
    min_amount: Optional[Decimal] = None,
    max_amount: Optional[Decimal] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> list[Expense]:
    query = db.query(Expense)
    if category:
        query = query.filter(Expense.category == category)
    if currency:
        query = query.filter(Expense.currency_original == currency.upper())
    if min_amount is not None:
        query = query.filter(Expense.amount_original >= min_amount)
    if max_amount is not None:
        query = query.filter(Expense.amount_original <= max_amount)
    return _apply_date_range(query, start_date, end_date).all()


def get_summary_by_category(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    query = db.query(
        Expense.category,
        func.sum(Expense.amount_base).label("total_base_usd"),
    )
    query = _apply_date_range(query, start_date, end_date)
    return query.group_by(Expense.category).all()
