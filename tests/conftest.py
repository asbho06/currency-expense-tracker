import os
import tempfile
from pathlib import Path

# Point the app at a throwaway database and a fake API key *before* backend is imported.
# load_dotenv() never overrides variables that are already set, so .env is ignored here.
_TMP_DIR = Path(tempfile.mkdtemp(prefix="triptrack-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DIR / 'test.db'}"
os.environ["FX_API_KEY"] = "test-key"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend import fx  # noqa: E402
from backend.db import engine  # noqa: E402
from backend.main import app  # noqa: E402
from backend.models import Base  # noqa: E402

# Fixed rates so tests are deterministic and never call the real API
FAKE_RATES = {
    "USD": {"USD": 1, "JPY": 150, "EUR": 0.9},
    "JPY": {"JPY": 1, "USD": 0.0065, "EUR": 0.006},
    "EUR": {"EUR": 1, "USD": 1.1, "JPY": 165},
}


@pytest.fixture
def rates(monkeypatch):
    """Fake exchange rates. Tests can change them with monkeypatch.setitem(rates["JPY"], "USD", ...)."""
    def latest_rates(base):
        if base not in FAKE_RATES:
            raise fx.FXError(f"Unsupported currency: {base}", status_code=400)
        return FAKE_RATES[base]

    monkeypatch.setattr(fx, "_latest_rates", latest_rates)
    return FAKE_RATES


@pytest.fixture
def client(rates):
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:  # entering runs the lifespan, which recreates the tables
        yield c


@pytest.fixture
def make_trip(client):
    def make(**fields):
        payload = {"name": "Japan", "local_currency": "JPY", "budget": 1000, **fields}
        res = client.post("/trips", json=payload)
        assert res.status_code == 201, res.text
        return res.json()
    return make


@pytest.fixture
def add_expense(client):
    def add(trip_id, **fields):
        payload = {"category": "food", **fields}
        res = client.post(f"/trips/{trip_id}/expenses", json=payload)
        assert res.status_code == 201, res.text
        return res.json()
    return add
