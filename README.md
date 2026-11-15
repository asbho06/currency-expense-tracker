#  ✈️ TripTrack: Multi-Currency Trip Budgeter (FastAPI + SQLite + Streamlit)

Plan a trip budget in **your own currency** and see it in **theirs**. Set a budget (say 1,000 USD for Japan), split it across hotel, food, transport, activities, shopping and misc, then log expenses in yen or dollars. TripTrack converts everything with live FX rates and tells you what's left, per category and per day.

Built with:
- **FastAPI** (backend API)
- **SQLAlchemy + SQLite** (data storage + ORM)
- **Requests + ExchangeRate API** (currency conversion, cached for an hour)
- **Streamlit** (dashboard)

---

##  Features

- Create trips with a home currency, destination currency, total budget and optional dates
- See your budget converted at today's rate (e.g. 1,000 USD ≈ 159,779 JPY)
- Optionally split the budget by category: 🏨 hotel, 🍜 food, 🚆 transport, 🎟️ activities, 🛍️ shopping, 📦 misc
- Log expenses in either currency; each is converted at the rate on the day you enter it
- Mark costs as **planned** (e.g. a booked hotel you'll pay at check-in) or **paid**; mark planned costs as paid later, with the actual amount
- Budget / spent / planned / left in both currencies, plus a per-day allowance when the trip has an end date
- Warnings when you're near or over your total budget or a category budget
- Quick currency converter
- API auto-documentation using Swagger (`/docs`)

---

##  Project Structure

```bash
currency-expense-tracker/
├── backend/
│   ├── main.py      # FastAPI app & routes
│   ├── models.py    # SQLAlchemy models (Trip, Expense)
│   ├── schemas.py   # Pydantic request/response models
│   ├── crud.py      # DB queries + budget calculations
│   ├── fx.py        # Exchange rates (cached)
│   └── db.py        # Engine, sessions, startup migration
│
├── tests/           # pytest suite (fake FX rates, throwaway DB)
│
├── dashboard/
│   └── app.py       # Streamlit UI
│
├── data/
│   └── expenses.db  # SQLite DB (ignored in git)
│
├── .env.example     # Copy to .env and add your API key
├── requirements.txt
├── requirements-dev.txt  # + pytest, httpx
└── README.md
```

---

##  API

| Method | Path | What it does |
|---|---|---|
| `POST` | `/trips` | Create a trip |
| `GET` | `/trips` | List trips |
| `GET` / `PATCH` / `DELETE` | `/trips/{id}` | Get, edit or delete a trip |
| `GET` | `/trips/{id}/summary` | Budget, spent, remaining, per-category breakdown, warnings |
| `POST` / `GET` | `/trips/{id}/expenses` | Add or list a trip's expenses |
| `PATCH` / `DELETE` | `/trips/{id}/expenses/{expense_id}` | Edit an expense (e.g. `{"status": "spent", "amount": 47000}` to mark a planned cost as paid) or remove it |
| `GET` | `/convert?amount=1000&from_currency=USD&to_currency=JPY` | Convert an amount |
| `GET` | `/categories` | List expense categories |

---

##  Running Locally

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then put your ExchangeRate API key in .env

# from the project root:
uvicorn backend.main:app --reload     # API at http://127.0.0.1:8000/docs
streamlit run dashboard/app.py        # dashboard
```

---

##  Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Tests use a temporary database and fixed fake exchange rates, so they never touch `data/expenses.db` or your API quota.
