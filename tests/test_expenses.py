import pytest


def test_expense_defaults_to_local_currency_and_converts(make_trip, add_expense):
    trip = make_trip()
    expense = add_expense(trip["id"], amount=15000, category="hotel", note="  Shinjuku  ")
    assert expense["currency_original"] == "JPY"
    assert expense["amount_base"] == 97.5        # 15000 * 0.0065
    assert expense["base_currency"] == "USD"
    assert expense["fx_rate"] == 0.0065
    assert expense["status"] == "spent"
    assert expense["note"] == "Shinjuku"


def test_expense_in_home_currency_is_not_converted(make_trip, add_expense):
    trip = make_trip()
    expense = add_expense(trip["id"], amount=30, currency="usd")
    assert expense["amount_base"] == 30
    assert expense["fx_rate"] == 1


@pytest.mark.parametrize("fields", [
    {"amount": -5},
    {"amount": 0},
    {"amount": 10, "category": "flights"},
    {"amount": 10, "status": "maybe"},
    {"amount": 10.001},  # more than 2 decimal places
])
def test_expense_rejects_invalid_input(client, make_trip, fields):
    trip = make_trip()
    payload = {"category": "food", **fields}
    assert client.post(f"/trips/{trip['id']}/expenses", json=payload).status_code == 422


def test_expense_on_missing_trip_is_404(client):
    assert client.post("/trips/999/expenses", json={"amount": 10, "category": "food"}).status_code == 404


def test_paying_a_planned_expense_reconverts_at_todays_rate(client, monkeypatch, rates, make_trip, add_expense):
    trip = make_trip()
    planned = add_expense(trip["id"], amount=20000, category="hotel", status="planned")
    assert planned["amount_base"] == 130  # 20000 * 0.0065

    monkeypatch.setitem(rates["JPY"], "USD", 0.007)  # the yen moved before we paid
    res = client.patch(f"/trips/{trip['id']}/expenses/{planned['id']}",
                       json={"status": "spent", "amount": 21000})
    paid = res.json()
    assert res.status_code == 200
    assert paid["status"] == "spent"
    assert paid["amount_original"] == 21000
    assert paid["amount_base"] == 147  # 21000 * 0.007
    assert paid["fx_rate"] == 0.007


def test_editing_only_the_note_keeps_the_original_rate(client, monkeypatch, rates, make_trip, add_expense):
    trip = make_trip()
    expense = add_expense(trip["id"], amount=10000)
    monkeypatch.setitem(rates["JPY"], "USD", 0.009)
    res = client.patch(f"/trips/{trip['id']}/expenses/{expense['id']}", json={"note": "ramen"})
    assert res.json()["note"] == "ramen"
    assert res.json()["amount_base"] == 65
    assert res.json()["fx_rate"] == 0.0065


def test_list_trip_expenses_newest_first(client, make_trip, add_expense):
    trip = make_trip()
    add_expense(trip["id"], amount=100, expense_date="2026-05-01T12:00:00")
    add_expense(trip["id"], amount=200, expense_date="2026-05-03T12:00:00")
    amounts = [e["amount_original"] for e in client.get(f"/trips/{trip['id']}/expenses").json()]
    assert amounts == [200, 100]


def test_expense_routes_check_the_trip(client, make_trip, add_expense):
    trip = make_trip()
    other = make_trip(name="Other")
    expense = add_expense(trip["id"], amount=100)
    url = f"/trips/{other['id']}/expenses/{expense['id']}"
    assert client.patch(url, json={"note": "x"}).status_code == 404
    assert client.delete(url).status_code == 404


def test_delete_expense(client, make_trip, add_expense):
    trip = make_trip()
    expense = add_expense(trip["id"], amount=100)
    assert client.delete(f"/trips/{trip['id']}/expenses/{expense['id']}").status_code == 204
    assert client.get(f"/trips/{trip['id']}/expenses").json() == []


def test_cross_trip_category_summary_counts_only_spent(client, make_trip, add_expense):
    trip = make_trip()
    add_expense(trip["id"], amount=10, currency="USD", category="food")
    add_expense(trip["id"], amount=99, currency="USD", category="food", status="planned")
    assert client.get("/expenses/summary/by-category").json() == [{"category": "food", "total_base_usd": 10}]
