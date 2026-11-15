from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


class Category(str, Enum):
    HOTEL = "hotel"
    FOOD = "food"
    TRANSPORT = "transport"
    ACTIVITIES = "activities"
    SHOPPING = "shopping"
    MISC = "misc"


class ExpenseStatus(str, Enum):
    PLANNED = "planned"  # expected cost, not paid yet
    SPENT = "spent"      # actually paid


CURRENCY_PATTERN = r"^[A-Za-z]{3}$"
CurrencyCode = Annotated[str, Field(pattern=CURRENCY_PATTERN), AfterValidator(str.upper)]
Money = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
Allocation = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


# ---------- Trips ----------

class TripCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    home_currency: CurrencyCode = "USD"
    local_currency: CurrencyCode
    budget: Money
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    category_budgets: dict[Category, Allocation] = Field(default_factory=dict)


class TripUpdate(BaseModel):
    # Currencies can't change after creation: stored expenses were converted with them
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    budget: Optional[Money] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    category_budgets: Optional[dict[Category, Allocation]] = None


class TripRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    home_currency: str
    local_currency: str
    budget: float
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    category_budgets: dict[str, float]
    created_at: datetime


class CategoryBreakdown(BaseModel):
    category: str
    spent_home: float
    spent_local: float
    planned_home: float
    planned_local: float
    allocated_home: Optional[float] = None
    remaining_home: Optional[float] = None
    over_budget: bool


class TripSummary(BaseModel):
    trip: TripRead
    exchange_rate: float  # 1 home_currency = exchange_rate local_currency, today
    budget_home: float
    budget_local: float
    spent_home: float
    spent_local: float
    planned_home: float
    planned_local: float
    # Budget not yet spent or planned: budget - spent - planned
    remaining_home: float
    remaining_local: float
    percent_spent: float
    percent_used: float  # spent + planned, as % of budget
    over_budget: bool
    days_left: Optional[int] = None
    daily_allowance_home: Optional[float] = None
    daily_allowance_local: Optional[float] = None
    by_category: list[CategoryBreakdown]
    warnings: list[str]


# ---------- Expenses ----------

class ExpenseCreate(BaseModel):
    amount: Money
    # Defaults to the trip's local currency (e.g. JPY) when left out
    currency: Optional[CurrencyCode] = None
    category: Category
    status: ExpenseStatus = ExpenseStatus.SPENT
    note: Optional[str] = Field(None, max_length=200)
    expense_date: Optional[datetime] = None


class ExpenseUpdate(BaseModel):
    # e.g. {"status": "spent", "amount": 47000} when a planned cost is actually paid
    amount: Optional[Money] = None
    currency: Optional[CurrencyCode] = None
    category: Optional[Category] = None
    status: Optional[ExpenseStatus] = None
    note: Optional[str] = Field(None, max_length=200)
    expense_date: Optional[datetime] = None


class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trip_id: Optional[int] = None
    # Returned as JSON numbers (not strings) so the dashboard can do math on them
    amount_original: float
    currency_original: str
    amount_base: float
    base_currency: str
    fx_rate: float
    category: Optional[str] = None
    status: str = ExpenseStatus.SPENT.value
    expense_date: Optional[datetime] = None
    note: Optional[str] = None
    created_at: datetime


class ExpenseSummary(BaseModel):
    category: Optional[str]
    total_base_usd: float


# ---------- Currency conversion ----------

class Conversion(BaseModel):
    amount: float
    from_currency: str
    to_currency: str
    rate: float
    converted: float
