"""TripTrack dashboard: plan a trip budget in your own currency and track spending in theirs."""
import os
from datetime import date, datetime, time

import pandas as pd
import requests
import streamlit as st

API_BASE = os.getenv("TRIPTRACK_API", "http://127.0.0.1:8000")

CURRENCIES = [
    "USD", "JPY", "EUR", "GBP", "CAD", "AUD", "NZD", "CHF", "CNY", "HKD", "KRW", "TWD",
    "SGD", "THB", "VND", "IDR", "MYR", "PHP", "INR", "MXN", "BRL", "ZAR", "AED", "TRY",
]
# Currencies that don't use cents
ZERO_DECIMAL_CURRENCIES = {"JPY", "KRW", "VND", "IDR", "CLP", "ISK"}

# Keys must match the backend's Category enum
CATEGORIES = {
    "hotel": "🏨 Hotel",
    "food": "🍜 Food",
    "transport": "🚆 Transport",
    "activities": "🎟️ Activities",
    "shopping": "🛍️ Shopping",
    "misc": "📦 Misc",
}

STATUSES = {"spent": "✅ Paid", "planned": "🗓️ Planned"}


# ---------- API helpers ----------

class APIError(Exception):
    pass


def api(method: str, path: str, **kwargs):
    try:
        res = requests.request(method, f"{API_BASE}{path}", timeout=15, **kwargs)
    except requests.ConnectionError:
        raise APIError(f"Can't reach the API at {API_BASE}. Is `uvicorn backend.main:app` running?")
    if res.status_code >= 400:
        try:
            detail = res.json().get("detail", res.text)
        except ValueError:
            detail = res.text
        if isinstance(detail, list):  # FastAPI validation errors
            detail = "; ".join(err.get("msg", "") for err in detail)
        raise APIError(detail)
    return res.json() if res.content else None


@st.cache_data(ttl=600, show_spinner=False)
def convert(amount: float, from_currency: str, to_currency: str) -> dict:
    return api("GET", "/convert", params={
        "amount": amount, "from_currency": from_currency, "to_currency": to_currency,
    })


# ---------- Formatting ----------

def decimals(currency: str) -> int:
    return 0 if currency in ZERO_DECIMAL_CURRENCIES else 2


def money(amount, currency: str) -> str:
    if amount is None:
        return "—"
    return f"{amount:,.{decimals(currency)}f} {currency}"


def number_format(currency: str) -> str:
    return f"%.{decimals(currency)}f"


def flash(message: str) -> None:
    """Show a success message after the next rerun."""
    st.session_state["flash"] = message


def show_flash() -> None:
    message = st.session_state.pop("flash", None)
    if message:
        st.success(message)


def allocation_inputs(key_prefix: str, budget: float, currency: str, defaults: dict = None) -> dict:
    """Number inputs for splitting the budget by category. Returns only non-zero amounts."""
    defaults = defaults or {}
    allocations = {}
    cols = st.columns(3)
    for i, (key, label) in enumerate(CATEGORIES.items()):
        with cols[i % 3]:
            allocations[key] = st.number_input(
                f"{label} ({currency})",
                min_value=0.0,
                value=float(defaults.get(key, 0.0)),
                step=10.0,
                key=f"{key_prefix}_{key}",
            )
    total = sum(allocations.values())
    if total > budget:
        st.error(f"Category budgets add up to {money(total, currency)}, "
                 f"more than the {money(budget, currency)} total.")
    elif total:
        st.caption(f"Allocated {money(total, currency)} · unallocated {money(budget - total, currency)}")
    return {k: str(round(v, 2)) for k, v in allocations.items() if v > 0}


# ---------- New trip ----------

def new_trip_page() -> None:
    st.header("Plan a new trip")

    name = st.text_input("Trip name", placeholder="Japan 2026")
    c1, c2, c3 = st.columns(3)
    home = c1.selectbox("Your currency", CURRENCIES, index=CURRENCIES.index("USD"))
    local = c2.selectbox("Destination currency", CURRENCIES, index=CURRENCIES.index("JPY"))
    budget = c3.number_input(f"Total budget ({home})", min_value=1.0, value=1000.0, step=50.0)
    d1, d2 = st.columns(2)
    start = d1.date_input("Start date (optional)", value=None)
    end = d2.date_input("End date (optional)", value=None)

    if home != local:
        try:
            conv = convert(budget, home, local)
            st.info(f"💱 {money(budget, home)} ≈ **{money(conv['converted'], local)}** "
                    f"at today's rate (1 {home} = {conv['rate']:,.4f} {local})")
        except APIError as e:
            st.warning(f"Couldn't get the exchange rate: {e}")

    with st.expander("Split the budget by category (optional)"):
        allocations = allocation_inputs("new", budget, home)

    if st.button("Create trip", type="primary", disabled=not name.strip()):
        payload = {
            "name": name.strip(),
            "home_currency": home,
            "local_currency": local,
            "budget": str(round(budget, 2)),
            "start_date": start.isoformat() if start else None,
            "end_date": end.isoformat() if end else None,
            "category_budgets": allocations,
        }
        try:
            trip = api("POST", "/trips", json=payload)
        except APIError as e:
            st.error(e)
            return
        # Can't set the sidebar widget's value after it's drawn; apply it on the next run
        st.session_state["select_trip"] = trip["id"]
        flash(f"Created “{trip['name']}”. Start adding expenses below.")
        st.rerun()


# ---------- Trip page sections ----------

def overview(summary: dict) -> None:
    trip = summary["trip"]
    home, local = trip["home_currency"], trip["local_currency"]

    dates = " → ".join(d for d in (trip["start_date"], trip["end_date"]) if d)
    rate = f"1 {home} = {summary['exchange_rate']:,.4f} {local} today" if home != local else ""
    st.caption(" · ".join(part for part in (dates, rate) if part))

    metrics = [
        ("Budget", "budget", None),
        ("Spent", "spent", "Money you've already paid"),
        ("Planned", "planned", "Costs you expect but haven't paid yet"),
        ("Left", "remaining", "Budget minus spent and planned"),
    ]
    for col, (label, key, help_text) in zip(st.columns(4), metrics):
        col.metric(label, money(summary[f"{key}_home"], home), help=help_text)
        if home != local:
            col.caption(f"≈ {money(summary[f'{key}_local'], local)}")

    progress_text = f"{summary['percent_spent']:.0f}% spent"
    if summary["planned_home"]:
        progress_text += f" · {summary['percent_used']:.0f}% including planned"
    st.progress(min(summary["percent_used"] / 100, 1.0), text=progress_text)

    for warning in summary["warnings"]:
        st.warning(warning)

    if summary["days_left"] and summary["daily_allowance_home"]:
        local_part = f" (≈ {money(summary['daily_allowance_local'], local)})" if home != local else ""
        st.info(f"📅 {summary['days_left']} day(s) left: you can spend about "
                f"**{money(summary['daily_allowance_home'], home)}**{local_part} per day.")


def add_expense_form(trip: dict) -> None:
    home, local = trip["home_currency"], trip["local_currency"]
    st.subheader("Add an expense")
    with st.form("add_expense", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        category = c1.selectbox("Category", list(CATEGORIES), format_func=CATEGORIES.get)
        status = c2.radio("Status", list(STATUSES), format_func=STATUSES.get, horizontal=True,
                          help="Planned = a cost you expect (e.g. a booked hotel) but haven't paid yet")
        currency = c3.radio("Currency", list(dict.fromkeys([local, home])), horizontal=True)
        amount = st.number_input("Amount", min_value=0.0, step=1.0)
        note = st.text_input("What was it?", placeholder="Ramen in Shinjuku")
        when = st.date_input("Date", value=date.today())
        submitted = st.form_submit_button("Add expense", type="primary")

    if not submitted:
        return
    if amount <= 0:
        st.error("Enter an amount greater than 0.")
        return
    payload = {
        "amount": str(round(amount, 2)),
        "currency": currency,
        "category": category,
        "status": status,
        "note": note.strip() or None,
        "expense_date": datetime.combine(when, time(12)).isoformat(),
    }
    try:
        expense = api("POST", f"/trips/{trip['id']}/expenses", json=payload)
    except APIError as e:
        st.error(e)
        return
    converted = ""
    if expense["currency_original"] != home:
        converted = f" (≈ {money(expense['amount_base'], home)})"
    kind = "planned cost" if status == "planned" else "expense"
    flash(f"Added {kind} {money(expense['amount_original'], expense['currency_original'])}{converted} "
          f"to {CATEGORIES[category]}.")
    st.rerun()


def converter(home: str, local: str) -> None:
    st.subheader("💱 Quick converter")
    pairs = [(home, local), (local, home)]
    src, dst = st.radio("Direction", pairs, format_func=lambda p: f"{p[0]} → {p[1]}",
                        horizontal=True, label_visibility="collapsed")
    amount = st.number_input(f"Amount in {src}", min_value=0.0,
                             value=1000.0 if src in ZERO_DECIMAL_CURRENCIES else 10.0,
                             step=1.0, key=f"convert_{src}_{dst}")
    if amount > 0:
        try:
            result = convert(amount, src, dst)
            st.markdown(f"### {money(result['converted'], dst)}")
        except APIError as e:
            st.warning(e)


def category_section(summary: dict, home: str, local: str) -> None:
    df = pd.DataFrame(summary["by_category"])
    has_allocations = df["allocated_home"].notna().any()

    has_planned = df["planned_home"].sum() > 0
    spent_col, spent_local_col = f"Spent ({home})", f"Spent ({local})"
    planned_col = f"Planned ({home})"
    budget_col, left_col = f"Budgeted ({home})", f"Left ({home})"

    table = pd.DataFrame({
        "Category": df["category"].map(CATEGORIES).fillna(df["category"]),
        spent_col: df["spent_home"],
    })
    if home != local:
        table[spent_local_col] = df["spent_local"]
    if has_planned:
        table[planned_col] = df["planned_home"]
    if has_allocations:
        table[budget_col] = df["allocated_home"]
        table[left_col] = df["remaining_home"]

    if df["spent_home"].sum() == 0 and not has_planned and not has_allocations:
        st.caption("No spending yet.")
        return

    chart_cols = [spent_col] + ([planned_col] if has_planned else []) + ([budget_col] if has_allocations else [])
    st.bar_chart(table.set_index("Category")[chart_cols], stack=False)
    st.dataframe(
        table,
        hide_index=True,
        column_config={
            col: st.column_config.NumberColumn(format=number_format(local if col == spent_local_col else home))
            for col in table.columns if col != "Category"
        },
    )


def expenses_section(trip_id: int, expenses: list, home: str) -> None:
    if not expenses:
        st.caption("No expenses yet. Add your first one above.")
        return

    df = pd.DataFrame(expenses)
    in_home = f"In {home}"
    table = pd.DataFrame({
        "Date": pd.to_datetime(df["expense_date"], format="ISO8601").dt.date,
        "Status": df["status"].map(STATUSES).fillna(df["status"]),
        "Category": df["category"].map(CATEGORIES).fillna(df["category"]),
        "What": df["note"].fillna(""),
        "Amount": [money(a, c) for a, c in zip(df["amount_original"], df["currency_original"])],
        in_home: df["amount_base"],
    })
    st.dataframe(table, hide_index=True,
                 column_config={in_home: st.column_config.NumberColumn(format=number_format(home))})

    planned = [e for e in expenses if e["status"] == "planned"]
    if planned:
        mark_paid_section(trip_id, planned)

    labels = {
        e["id"]: " · ".join(filter(None, [
            e["expense_date"][:10],
            CATEGORIES.get(e["category"], e["category"]),
            e["note"],
            money(e["amount_original"], e["currency_original"]),
        ]))
        for e in expenses
    }
    c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
    to_delete = c1.selectbox("Remove an expense", list(labels), format_func=labels.get,
                             index=None, placeholder="Pick an expense to remove")
    if c2.button("Remove", disabled=to_delete is None):
        try:
            api("DELETE", f"/trips/{trip_id}/expenses/{to_delete}")
        except APIError as e:
            st.error(e)
            return
        flash("Expense removed.")
        st.rerun()


def mark_paid_section(trip_id: int, planned: list) -> None:
    st.markdown("**✅ Mark a planned cost as paid**")
    by_id = {e["id"]: e for e in planned}
    c1, c2, c3 = st.columns([3, 2, 1], vertical_alignment="bottom")
    expense_id = c1.selectbox(
        "Planned cost",
        list(by_id),
        format_func=lambda i: " · ".join(filter(None, [
            CATEGORIES.get(by_id[i]["category"], by_id[i]["category"]),
            by_id[i]["note"],
            money(by_id[i]["amount_original"], by_id[i]["currency_original"]),
        ])),
    )
    chosen = by_id[expense_id]
    actual = c2.number_input(
        f"Actual amount ({chosen['currency_original']})",
        min_value=0.0,
        value=float(chosen["amount_original"]),
        step=1.0,
        key=f"actual_{expense_id}",  # new key per expense so the default follows the selection
    )
    if c3.button("Mark paid", type="primary", disabled=actual <= 0):
        try:
            api("PATCH", f"/trips/{trip_id}/expenses/{expense_id}",
                json={"status": "spent", "amount": str(round(actual, 2))})
        except APIError as e:
            st.error(e)
            return
        flash(f"Marked as paid: {money(actual, chosen['currency_original'])}.")
        st.rerun()


def settings_section(trip: dict) -> None:
    home = trip["home_currency"]
    with st.form(f"trip_settings_{trip['id']}"):
        name = st.text_input("Trip name", value=trip["name"])
        budget = st.number_input(f"Total budget ({home})", min_value=1.0,
                                 value=float(trip["budget"]), step=50.0)
        d1, d2 = st.columns(2)
        start = d1.date_input("Start date", value=date.fromisoformat(trip["start_date"]) if trip["start_date"] else None)
        end = d2.date_input("End date", value=date.fromisoformat(trip["end_date"]) if trip["end_date"] else None)
        st.markdown("**Category budgets**")
        allocations = allocation_inputs(f"edit_{trip['id']}", budget, home, trip["category_budgets"])
        save = st.form_submit_button("Save changes")

    if save:
        payload = {
            "name": name.strip() or trip["name"],
            "budget": str(round(budget, 2)),
            "start_date": start.isoformat() if start else None,
            "end_date": end.isoformat() if end else None,
            "category_budgets": allocations,
        }
        try:
            api("PATCH", f"/trips/{trip['id']}", json=payload)
        except APIError as e:
            st.error(e)
        else:
            flash("Trip updated.")
            st.rerun()

    st.divider()
    confirm = st.checkbox("I want to delete this trip and all its expenses",
                          key=f"confirm_delete_{trip['id']}")
    if st.button("Delete trip", disabled=not confirm):
        try:
            api("DELETE", f"/trips/{trip['id']}")
        except APIError as e:
            st.error(e)
            return
        flash(f"Deleted “{trip['name']}”.")
        st.rerun()


def trip_page(trip_id: int) -> None:
    try:
        summary = api("GET", f"/trips/{trip_id}/summary")
        expenses = api("GET", f"/trips/{trip_id}/expenses")
    except APIError as e:
        st.error(e)
        return

    trip = summary["trip"]
    home, local = trip["home_currency"], trip["local_currency"]

    st.header(trip["name"])
    overview(summary)

    if home != local:
        left, right = st.columns([3, 2], gap="large")
        with left:
            add_expense_form(trip)
        with right:
            converter(home, local)
    else:
        add_expense_form(trip)

    st.subheader("By category")
    category_section(summary, home, local)

    st.subheader("Expenses")
    expenses_section(trip_id, expenses, home)

    with st.expander("⚙️ Trip settings"):
        settings_section(trip)


# ---------- Page ----------

st.set_page_config(page_title="TripTrack", page_icon="✈️", layout="wide")
st.title("✈️ TripTrack")
st.caption("Plan a trip budget in your own currency and see it in theirs.")
show_flash()

try:
    trips = api("GET", "/trips")
except APIError as e:
    st.error(e)
    st.stop()

trip_ids = [t["id"] for t in trips]
trip_names = {t["id"]: f"{t['name']} · {t['local_currency']}" for t in trips}
if "select_trip" in st.session_state:
    st.session_state["trip_id"] = st.session_state.pop("select_trip")
current = st.session_state.get("trip_id", "unset")
if current == "unset" or (current is not None and current not in trip_ids):
    st.session_state["trip_id"] = trip_ids[0] if trip_ids else None

st.sidebar.selectbox(
    "Your trips",
    [*trip_ids, None],
    format_func=lambda i: trip_names.get(i, "➕ Plan a new trip"),
    key="trip_id",
)

if st.session_state["trip_id"] is None:
    new_trip_page()
else:
    trip_page(st.session_state["trip_id"])
