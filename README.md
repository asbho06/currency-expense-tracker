#  Multi-Currency Expense Tracker (FastAPI + SQLite + Streamlit)

A full-stack personal budgeting tool that lets users log expenses in **any currency**, automatically converts them into a chosen base currency using live FX rates, and displays summaries + dashboards.

Built with:
- **FastAPI** (backend API)
- **SQLAlchemy + SQLite** (data storage + ORM)
- **Requests + ExchangeRate API** (currency conversion)
- **Streamlit** (visual dashboard)

---

##  Features

 Log expenses with:
- Amount  
- Currency (e.g., EUR, JPY, GBP)  
- Category  
- Date  
- Notes  

 Automatic FX conversion to a base currency (default: USD)  
 View stored expenses through API or dashboard  
 SQLite local storage  
 API auto-documentation using Swagger (`/docs`)  
 Easy backend → dashboard pipeline

---

##  Project Structure

```bash
currency-expense-tracker/
├── backend/
│   ├── main.py              # FastAPI app & routes
│   ├── expenses_table.py    # SQLAlchemy model
│   ├── schemas.py           # (optional) Pydantic models
│
├── dashboard/
│   └── app.py               # Streamlit UI
│
├── data/
│   └── expenses.db          # SQLite DB (ignored in git)
│
├── .gitignore
├── requirements.txt
└── README.md
