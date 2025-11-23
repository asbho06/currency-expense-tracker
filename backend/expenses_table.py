from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base # our database
from datetime import datetime

Base = declarative_base()

class Expense(Base):
    __tablename__ = 'expenses'
    id = Column(Integer, primary_key=True)
    amount_original = Column(Float, nullable=False)
    currency_original = Column(String, nullable=False)
    amount_base = Column(Float, nullable=False)
    base_currency = Column(String, nullable=False)
    fx_rate = Column(Float, nullable=False)
    category = Column(String)
    expense_date = Column(DateTime)
    note = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
