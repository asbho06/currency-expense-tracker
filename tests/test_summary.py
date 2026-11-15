from datetime import date, timedelta

import pytest


def summary(client, trip):
    res = client.get(f"/trips/{trip['id']}/summary")
    assert res.status_code == 200, res.text
    return res.json()


def category(s, name):
    return next(c for c in s["by_category"] if c["category"] == name)


def test_empty_trip(client, make_trip):
    s = summary(client, make_trip())
    assert s["exchange_rate"] == 150
    assert s["budget_local"] == 150000
    assert s["spent_home"] == s["planned_home"] == 0
    assert s["remaining_home"] == 1000
    assert s["remaining_local"] == 150000
    assert s["warnings"] == []
    assert {c["category"] for c in s["by_category"]} == {
        "hotel", "food", "transport", "activities", "shopping", "misc",
    }


def test_spent_and_planned_totals(client, make_trip, add_expense):
    trip = make_trip(category_budgets={"hotel": 400, "food": 250})
    add_expense(trip["id"], amount=45000, category="hotel")                       # 292.50 USD
    add_expense(trip["id"], amount=20000, category="hotel", status="planned")     # 130.00 USD
    add_expense(trip["id"], amount=30, currency="USD", category="food")           #  30.00 USD

    s = summary(client, trip)
    assert s["spent_home"] == 322.5
    assert s["planned_home"] == 130
    assert s["remaining_home"] == 547.5          # 1000 - 322.50 - 130
    assert s["spent_local"] == 49500             # 45000 JPY as paid + 30 USD * 150
    assert s["planned_local"] == 20000
    assert s["remaining_local"] == 80500         # 150000 - 49500 - 20000
    assert s["percent_spent"] == pytest.approx(32.25, abs=0.1)
    assert s["percent_used"] == pytest.approx(45.25, abs=0.1)
    assert s["over_budget"] is False

    hotel = category(s, "hotel")
    assert hotel["spent_home"] == 292.5
    assert hotel["planned_home"] == 130
    assert hotel["spent_local"] == 45000         # paid in yen, so exactly what was paid
    assert category(s, "food")["spent_local"] == 4500  # paid in USD, shown at today's rate
    assert hotel["remaining_home"] == -22.5
    assert hotel["over_budget"] is True
    assert category(s, "food")["remaining_home"] == 220
    assert category(s, "misc")["allocated_home"] is None
    assert s["warnings"] == ["Hotel is over its budget by 22.50 USD."]


def test_near_limit_warning(client, make_trip, add_expense):
    trip = make_trip(budget=100)
    add_expense(trip["id"], amount=95, currency="USD")
    assert summary(client, trip)["warnings"] == ["You've used 95% of your budget."]


def test_planned_costs_count_toward_near_limit(client, make_trip, add_expense):
    trip = make_trip(budget=100)
    add_expense(trip["id"], amount=50, currency="USD")
    add_expense(trip["id"], amount=45, currency="USD", status="planned")
    assert summary(client, trip)["warnings"] == ["You've used 95% of your budget (including planned costs)."]


def test_over_total_budget(client, make_trip, add_expense):
    trip = make_trip(budget=100)
    add_expense(trip["id"], amount=120, currency="USD")
    s = summary(client, trip)
    assert s["over_budget"] is True
    assert s["remaining_home"] == -20
    assert s["warnings"] == ["Your spending is over the total budget by 20.00 USD."]
    assert s["daily_allowance_home"] is None


def test_daily_allowance_during_trip(client, make_trip):
    today = date.today()
    trip = make_trip(start_date=str(today - timedelta(days=2)), end_date=str(today + timedelta(days=4)))
    s = summary(client, trip)
    assert s["days_left"] == 5                      # today through the end date
    assert s["daily_allowance_home"] == 200         # 1000 / 5
    assert s["daily_allowance_local"] == 30000


def test_daily_allowance_before_trip_starts(client, make_trip):
    today = date.today()
    trip = make_trip(start_date=str(today + timedelta(days=10)), end_date=str(today + timedelta(days=13)))
    assert summary(client, trip)["days_left"] == 4


def test_no_daily_allowance_after_trip_ends(client, make_trip):
    today = date.today()
    trip = make_trip(start_date=str(today - timedelta(days=10)), end_date=str(today - timedelta(days=3)))
    s = summary(client, trip)
    assert s["days_left"] is None
    assert s["daily_allowance_home"] is None


def test_missing_trip_summary_is_404(client):
    assert client.get("/trips/999/summary").status_code == 404
