from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class ExpenseCreate(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str
    category: str
    date: date
    notes: Optional[str] = None

class ExpenseRead(BaseModel):
    id: int
    amount: float
    currency: str
    category: str
    date: date
    notes: Optional[str] = None

    class Config:
        orm_mode = True
class ExpenseSummary(BaseModel):
    category: str
    total: float
