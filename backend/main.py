from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .expenses_table import Base, Expense 
import requests
from datetime import datetime

# TEMPORARY: hardcode config instead of using .env
DATABASE_URL = "sqlite:///expenses.db"
FX_API_KEY = "6c289e4e6d4ffe629d7edd00"
FX_API_BASE = "https://v6.exchangerate-api.com/v6"
BASE_CURRENCY = "USD"


engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(bind=engine)

app = FastAPI()

@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)

def get_fx_rate(from_currency, to_currency):
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()


    if from_currency == to_currency:
        return 1.0
    url = f"{FX_API_BASE}/{FX_API_KEY}/latest/{from_currency}"
    res = requests.get(url, timeout=5)
    data = res.json()
    rate = data.get("conversion_rates", {}).get(to_currency)
    if rate is None:
        raise HTTPException(status_code=502, detail="Exchange rate not available")
    return rate


@app.post("/expenses")
def add_expense(amount: float, currency: str, category: str = None, expense_date: str = None, note: str=None):
    session = SessionLocal()
    fx_rate = get_fx_rate(currency, BASE_CURRENCY)
    amount_base = amount * fx_rate

    exp = Expense(
        amount_original=amount,
        currency_original=currency,
        amount_base=amount_base,
        base_currency = BASE_CURRENCY,
        fx_rate=fx_rate,
        category=category,
        expense_date=datetime.fromisoformat(expense_date) if expense_date else datetime.utcnow(),
        note=note,
    )

    session.add(exp)
    session.commit()
    return {"message": "saved", "data": exp.id}

@app.get("/expenses")
def list_expenses():
    session = SessionLocal()
    return session.query(Expense).all()




print("DATABASE_URL =", DATABASE_URL)