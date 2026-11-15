from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ExpenseCreate(BaseModel):
    amount: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(..., pattern=r"^[A-Za-z]{3}$")
    category: Optional[str] = None
    expense_date: Optional[datetime] = None
    note: Optional[str] = None


class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # Returned as JSON numbers (not strings) so the dashboard can do math on them
    amount_original: float
    currency_original: str
    amount_base: float
    base_currency: str
    fx_rate: float
    category: Optional[str] = None
    expense_date: Optional[datetime] = None
    note: Optional[str] = None
    created_at: datetime


class ExpenseSummary(BaseModel):
    category: Optional[str]
    total_base_usd: float
