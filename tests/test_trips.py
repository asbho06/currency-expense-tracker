import pytest


def test_create_trip_normalizes_input(make_trip):
    trip = make_trip(local_currency="jpy", category_budgets={"hotel": 400, "shopping": 0})
    assert trip["home_currency"] == "USD"
    assert trip["local_currency"] == "JPY"
    assert trip["budget"] == 1000
    assert trip["category_budgets"] == {"hotel": 400}  # zero allocations are dropped


@pytest.mark.parametrize("fields", [
    {"category_budgets": {"hotel": 800, "food": 300}},            # more than the 1000 budget
    {"start_date": "2026-05-10", "end_date": "2026-05-01"},       # ends before it starts
    {"budget": 0},
    {"local_currency": "12"},
    {"local_currency": "JPYY"},
    {"name": ""},
    {"category_budgets": {"flights": 100}},                       # unknown category
])
def test_create_trip_rejects_invalid_input(client, fields):
    payload = {"name": "Japan", "local_currency": "JPY", "budget": 1000, **fields}
    assert client.post("/trips", json=payload).status_code == 422


def test_create_trip_rejects_unsupported_currency(client):
    res = client.post("/trips", json={"name": "x", "local_currency": "ZZZ", "budget": 100})
    assert res.status_code == 400
    assert "ZZZ" in res.json()["detail"]


def test_list_and_get_trips(client, make_trip):
    first = make_trip(name="Japan")
    second = make_trip(name="Paris", local_currency="EUR")
    names = [t["name"] for t in client.get("/trips").json()]
    assert set(names) == {"Japan", "Paris"}
    assert client.get(f"/trips/{second['id']}").json()["local_currency"] == "EUR"
    assert client.get(f"/trips/{first['id'] + 100}").status_code == 404


def test_update_trip(client, make_trip):
    trip = make_trip(start_date="2026-05-01", end_date="2026-05-07")
    res = client.patch(f"/trips/{trip['id']}", json={"budget": 1500, "end_date": None})
    assert res.status_code == 200
    assert res.json()["budget"] == 1500
    assert res.json()["end_date"] is None
    assert res.json()["start_date"] == "2026-05-01"  # untouched


def test_update_trip_rejects_budget_below_allocations(client, make_trip):
    trip = make_trip(category_budgets={"hotel": 600})
    res = client.patch(f"/trips/{trip['id']}", json={"budget": 500})
    assert res.status_code == 422
    assert "more than the total budget" in res.json()["detail"]


def test_update_trip_ignores_null_name_and_budget(client, make_trip):
    trip = make_trip()
    res = client.patch(f"/trips/{trip['id']}", json={"name": None, "budget": None})
    assert res.json()["name"] == "Japan"
    assert res.json()["budget"] == 1000


def test_delete_trip_removes_its_expenses(client, make_trip, add_expense):
    trip = make_trip()
    other = make_trip(name="Other")
    add_expense(trip["id"], amount=1000)
    add_expense(other["id"], amount=1000)

    assert client.delete(f"/trips/{trip['id']}").status_code == 204
    assert client.get(f"/trips/{trip['id']}").status_code == 404
    remaining = client.get("/expenses").json()
    assert [e["trip_id"] for e in remaining] == [other["id"]]


def test_convert_endpoint(client):
    res = client.get("/convert", params={"amount": 1000, "from_currency": "usd", "to_currency": "jpy"})
    assert res.json() == {
        "amount": 1000, "from_currency": "USD", "to_currency": "JPY", "rate": 150, "converted": 150000,
    }
    assert client.get("/convert", params={"amount": 0, "from_currency": "USD", "to_currency": "JPY"}).status_code == 422
    assert client.get("/convert", params={"amount": 5, "from_currency": "US", "to_currency": "JPY"}).status_code == 422
