from sqlalchemy.orm import Session
from sqlalchemy import func
from expenses_table import Expense
from schemas import ExpenseCreate

BASE_CURRENCY = "USD"

def convert_currency(amount: float, currency: str) -> float:
    # placeholder logic for now
    # later you can move your live FX API call here
    if currency.upper() == BASE_CURRENCY:
        return amount
    return amount * 1.0

def create_expense(db: Session, expense: ExpenseCreate):
    converted_amount = convert_currency(expense.amount, expense.currency)

    db_expense = Expense(
        amount=expense.amount,
        currency=expense.currency.upper(),
        converted_amount=converted_amount,
        category=expense.category,
        date=expense.date,
        notes=expense.notes
    )

    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense

def get_expenses(db: Session):
    return db.query(Expense).all()

def get_expenses_by_category(db: Session, category: str):
    return db.query(Expense).filter(Expense.category == category).all()

def get_summary_by_category(db: Session):
    return (
        db.query(
            Expense.category,
            func.sum(Expense.converted_amount).label("total")
        )
        .group_by(Expense.category)
        .all()
    )
