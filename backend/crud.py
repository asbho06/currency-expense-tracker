from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Query, Session

from . import fx
from .models import Expense, Trip, utcnow
from .schemas import (
    Category,
    ExpenseCreate,
    ExpenseStatus,
    ExpenseUpdate,
    TripCreate,
    TripRead,
    TripUpdate,
)

ZERO = Decimal("0")
CENTS = Decimal("0.01")
NEAR_LIMIT_PERCENT = 90


class NotFoundError(Exception):
    pass


class InvalidRequestError(Exception):
    pass


# ---------- Trips ----------

def _check_trip_fields(budget, category_budgets: dict, start_date, end_date) -> None:
    if start_date and end_date and end_date < start_date:
        raise InvalidRequestError("end_date must be on or after start_date")
    allocated = sum((Decimal(str(v)) for v in category_budgets.values()), ZERO)
    if allocated > budget:
        raise InvalidRequestError(
            f"Category budgets add up to {allocated:,.2f}, more than the total budget of {budget:,.2f}"
        )


def _serialize_allocations(allocations: dict) -> dict[str, str]:
    # Stored as JSON, which can't hold Decimals; zero allocations are dropped
    return {Category(k).value: str(v) for k, v in allocations.items() if Decimal(str(v)) > 0}


def create_trip(db: Session, data: TripCreate) -> Trip:
    _check_trip_fields(data.budget, data.category_budgets, data.start_date, data.end_date)
    # Fail now, not on the first expense, if the currency pair isn't supported
    fx.get_rate(data.home_currency, data.local_currency)

    trip = Trip(
        name=data.name.strip(),
        home_currency=data.home_currency,
        local_currency=data.local_currency,
        budget=data.budget,
        category_budgets=_serialize_allocations(data.category_budgets),
        start_date=data.start_date,
        end_date=data.end_date,
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


def list_trips(db: Session) -> list[Trip]:
    return db.query(Trip).order_by(Trip.created_at.desc()).all()


def get_trip(db: Session, trip_id: int) -> Trip:
    trip = db.get(Trip, trip_id)
    if trip is None:
        raise NotFoundError(f"Trip {trip_id} not found")
    return trip


def update_trip(db: Session, trip_id: int, data: TripUpdate) -> Trip:
    trip = get_trip(db, trip_id)
    # Dates may be cleared with an explicit null; name and budget may not
    changes = {
        k: v
        for k, v in data.model_dump(exclude_unset=True).items()
        if v is not None or k in ("start_date", "end_date")
    }

    _check_trip_fields(
        changes.get("budget", trip.budget),
        changes.get("category_budgets", trip.category_budgets or {}),
        changes.get("start_date", trip.start_date),
        changes.get("end_date", trip.end_date),
    )

    if "category_budgets" in changes:
        changes["category_budgets"] = _serialize_allocations(changes["category_budgets"])
    if "name" in changes:
        changes["name"] = changes["name"].strip()

    for field, value in changes.items():
        setattr(trip, field, value)
    db.commit()
    db.refresh(trip)
    return trip


def delete_trip(db: Session, trip_id: int) -> None:
    db.delete(get_trip(db, trip_id))
    db.commit()


def _cents(amount: Decimal) -> Decimal:
    return amount.quantize(CENTS)


def trip_summary(db: Session, trip_id: int) -> dict:
    trip = get_trip(db, trip_id)
    home, local = trip.home_currency, trip.local_currency
    rate = fx.get_rate(home, local)  # today's rate, for showing home amounts in local currency

    budget = Decimal(trip.budget)
    # totals[status][category] = (home amount, local amount)
    totals = {status.value: {c.value: (ZERO, ZERO) for c in Category} for status in ExpenseStatus}
    for expense in trip.expenses:
        home_amount = Decimal(expense.amount_base)
        # Something paid in the local currency counts at its exact local amount (¥3,000 stays ¥3,000);
        # anything else is shown in local currency at today's rate
        if expense.currency_original == local:
            local_amount = Decimal(expense.amount_original)
        else:
            local_amount = home_amount * rate
        by_cat = totals[expense.status]
        prev_home, prev_local = by_cat.get(expense.category, (ZERO, ZERO))
        by_cat[expense.category] = (prev_home + home_amount, prev_local + local_amount)
    spent_by_category = totals[ExpenseStatus.SPENT.value]
    planned_by_category = totals[ExpenseStatus.PLANNED.value]

    def total(by_cat: dict) -> tuple:
        return (sum((h for h, _ in by_cat.values()), ZERO), sum((l for _, l in by_cat.values()), ZERO))

    (spent, spent_local), (planned, planned_local) = total(spent_by_category), total(planned_by_category)
    remaining = budget - spent - planned
    remaining_local = budget * rate - spent_local - planned_local
    percent_spent = float(spent / budget * 100)
    percent_used = float((spent + planned) / budget * 100)
    allocations = {k: Decimal(str(v)) for k, v in (trip.category_budgets or {}).items()}

    warnings = []
    if remaining < 0:
        what = "spending and plans are" if planned else "spending is"
        warnings.append(f"Your {what} over the total budget by {-remaining:,.2f} {home}.")
    elif percent_used >= NEAR_LIMIT_PERCENT:
        warnings.append(f"You've used {percent_used:.0f}% of your budget"
                        + (" (including planned costs)." if planned else "."))

    by_category = []
    for category in dict.fromkeys([*spent_by_category, *planned_by_category]):
        cat_spent, cat_spent_local = spent_by_category.get(category, (ZERO, ZERO))
        cat_planned, cat_planned_local = planned_by_category.get(category, (ZERO, ZERO))
        allocated = allocations.get(category)
        cat_remaining = allocated - cat_spent - cat_planned if allocated is not None else None
        over = cat_remaining is not None and cat_remaining < 0
        if over:
            warnings.append(f"{category.title()} is over its budget by {-cat_remaining:,.2f} {home}.")
        by_category.append({
            "category": category,
            "spent_home": cat_spent,
            "spent_local": _cents(cat_spent_local),
            "planned_home": cat_planned,
            "planned_local": _cents(cat_planned_local),
            "allocated_home": allocated,
            "remaining_home": cat_remaining,
            "over_budget": over,
        })

    days_left = None
    today = date.today()
    if trip.end_date and trip.end_date >= today:
        first_day = max(today, trip.start_date or today)
        days_left = (trip.end_date - first_day).days + 1
    has_daily = bool(days_left) and remaining > 0
    daily = _cents(remaining / days_left) if has_daily else None
    daily_local = _cents(remaining_local / days_left) if has_daily else None

    return {
        "trip": TripRead.model_validate(trip),
        "exchange_rate": rate,
        "budget_home": budget,
        "budget_local": _cents(budget * rate),
        "spent_home": spent,
        "spent_local": _cents(spent_local),
        "planned_home": planned,
        "planned_local": _cents(planned_local),
        "remaining_home": remaining,
        "remaining_local": _cents(remaining_local),
        "percent_spent": round(percent_spent, 1),
        "percent_used": round(percent_used, 1),
        "over_budget": remaining < 0,
        "days_left": days_left,
        "daily_allowance_home": daily,
        "daily_allowance_local": daily_local,
        "by_category": by_category,
        "warnings": warnings,
    }


# ---------- Trip expenses ----------

def add_trip_expense(db: Session, trip_id: int, data: ExpenseCreate) -> Expense:
    trip = get_trip(db, trip_id)
    currency = data.currency or trip.local_currency
    amount_base, rate = fx.convert(data.amount, currency, trip.home_currency)

    expense = Expense(
        trip_id=trip.id,
        amount_original=data.amount,
        currency_original=currency,
        amount_base=amount_base,
        base_currency=trip.home_currency,
        fx_rate=rate,
        category=data.category.value,
        status=data.status.value,
        expense_date=data.expense_date or utcnow(),
        note=data.note.strip() if data.note else None,
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


def list_trip_expenses(db: Session, trip_id: int) -> list[Expense]:
    get_trip(db, trip_id)
    return (
        db.query(Expense)
        .filter(Expense.trip_id == trip_id)
        .order_by(Expense.expense_date.desc(), Expense.id.desc())
        .all()
    )


def _get_trip_expense(db: Session, trip_id: int, expense_id: int) -> Expense:
    expense = db.get(Expense, expense_id)
    if expense is None or expense.trip_id != trip_id:
        raise NotFoundError(f"Expense {expense_id} not found on trip {trip_id}")
    return expense


def update_trip_expense(db: Session, trip_id: int, expense_id: int, data: ExpenseUpdate) -> Expense:
    expense = _get_trip_expense(db, trip_id, expense_id)
    changes = data.model_dump(exclude_unset=True)

    amount = changes.get("amount") or Decimal(expense.amount_original)
    currency = changes.get("currency") or expense.currency_original
    now_paid = changes.get("status") == ExpenseStatus.SPENT and expense.status == ExpenseStatus.PLANNED.value
    # Re-convert when the money changes, or when a planned cost is paid (use the rate on the day it's paid)
    if "amount" in changes or "currency" in changes or now_paid:
        amount_base, rate = fx.convert(amount, currency, expense.base_currency)
        expense.amount_original = amount
        expense.currency_original = currency
        expense.amount_base = amount_base
        expense.fx_rate = rate

    if changes.get("category"):
        expense.category = changes["category"].value
    if changes.get("status"):
        expense.status = changes["status"].value
    if "note" in changes:
        expense.note = changes["note"].strip() if changes["note"] else None
    if changes.get("expense_date"):
        expense.expense_date = changes["expense_date"]

    db.commit()
    db.refresh(expense)
    return expense


def delete_trip_expense(db: Session, trip_id: int, expense_id: int) -> None:
    db.delete(_get_trip_expense(db, trip_id, expense_id))
    db.commit()


# ---------- All expenses (across trips) ----------

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
    ).filter(Expense.status == ExpenseStatus.SPENT.value)
    query = _apply_date_range(query, start_date, end_date)
    return query.group_by(Expense.category).all()
