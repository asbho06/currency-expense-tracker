from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from . import crud, fx
from .db import get_db, init_db
from .schemas import (
    Category,
    CURRENCY_PATTERN,
    Conversion,
    ExpenseCreate,
    ExpenseRead,
    ExpenseSummary,
    ExpenseUpdate,
    TripCreate,
    TripRead,
    TripSummary,
    TripUpdate,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="TripTrack", lifespan=lifespan)


# ---------- Error handling ----------

@app.exception_handler(fx.FXError)
async def fx_error_handler(request: Request, exc: fx.FXError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.exception_handler(crud.NotFoundError)
async def not_found_handler(request: Request, exc: crud.NotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(crud.InvalidRequestError)
async def invalid_request_handler(request: Request, exc: crud.InvalidRequestError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


# ---------- Trips ----------

@app.post("/trips", response_model=TripRead, status_code=201)
def create_trip(trip: TripCreate, db: Session = Depends(get_db)):
    return crud.create_trip(db, trip)


@app.get("/trips", response_model=list[TripRead])
def list_trips(db: Session = Depends(get_db)):
    return crud.list_trips(db)


@app.get("/trips/{trip_id}", response_model=TripRead)
def get_trip(trip_id: int, db: Session = Depends(get_db)):
    return crud.get_trip(db, trip_id)


@app.patch("/trips/{trip_id}", response_model=TripRead)
def update_trip(trip_id: int, changes: TripUpdate, db: Session = Depends(get_db)):
    return crud.update_trip(db, trip_id, changes)


@app.delete("/trips/{trip_id}", status_code=204)
def delete_trip(trip_id: int, db: Session = Depends(get_db)):
    crud.delete_trip(db, trip_id)


@app.get("/trips/{trip_id}/summary", response_model=TripSummary)
def trip_summary(trip_id: int, db: Session = Depends(get_db)):
    return crud.trip_summary(db, trip_id)


@app.post("/trips/{trip_id}/expenses", response_model=ExpenseRead, status_code=201)
def add_trip_expense(trip_id: int, expense: ExpenseCreate, db: Session = Depends(get_db)):
    return crud.add_trip_expense(db, trip_id, expense)


@app.get("/trips/{trip_id}/expenses", response_model=list[ExpenseRead])
def list_trip_expenses(trip_id: int, db: Session = Depends(get_db)):
    return crud.list_trip_expenses(db, trip_id)


@app.patch("/trips/{trip_id}/expenses/{expense_id}", response_model=ExpenseRead)
def update_trip_expense(trip_id: int, expense_id: int, changes: ExpenseUpdate, db: Session = Depends(get_db)):
    return crud.update_trip_expense(db, trip_id, expense_id, changes)


@app.delete("/trips/{trip_id}/expenses/{expense_id}", status_code=204)
def delete_trip_expense(trip_id: int, expense_id: int, db: Session = Depends(get_db)):
    crud.delete_trip_expense(db, trip_id, expense_id)


# ---------- Helpers ----------

@app.get("/categories", response_model=list[str])
def list_categories():
    return [c.value for c in Category]


@app.get("/convert", response_model=Conversion)
def convert(
    amount: Decimal = Query(..., gt=0),
    from_currency: str = Query(..., pattern=CURRENCY_PATTERN),
    to_currency: str = Query(..., pattern=CURRENCY_PATTERN),
):
    from_currency, to_currency = from_currency.upper(), to_currency.upper()
    converted, rate = fx.convert(amount, from_currency, to_currency)
    return {
        "amount": amount,
        "from_currency": from_currency,
        "to_currency": to_currency,
        "rate": rate,
        "converted": converted,
    }


# ---------- All expenses (across trips) ----------

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
