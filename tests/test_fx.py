from decimal import Decimal
from unittest.mock import MagicMock

import pytest
import requests

from backend import fx


@pytest.fixture(autouse=True)
def clean_cache(monkeypatch):
    fx._cache.clear()
    monkeypatch.setenv("FX_API_KEY", "test-key")
    yield
    fx._cache.clear()


def api_returns(monkeypatch, payload):
    response = MagicMock()
    response.json.return_value = payload
    get = MagicMock(return_value=response)
    monkeypatch.setattr(fx.requests, "get", get)
    return get


def test_same_currency_does_not_call_api(monkeypatch):
    get = api_returns(monkeypatch, {})
    assert fx.get_rate("usd", "USD") == Decimal("1")
    get.assert_not_called()


def test_rates_are_cached(monkeypatch):
    get = api_returns(monkeypatch, {"result": "success", "conversion_rates": {"JPY": 150.5}})
    assert fx.get_rate("USD", "JPY") == Decimal("150.5")
    assert fx.get_rate("usd", "jpy") == Decimal("150.5")
    assert get.call_count == 1


def test_cache_expires_after_ttl(monkeypatch):
    get = api_returns(monkeypatch, {"result": "success", "conversion_rates": {"JPY": 150}})
    clock = iter([0, fx.CACHE_TTL_SECONDS + 1])
    monkeypatch.setattr(fx.time, "monotonic", lambda: next(clock))
    fx.get_rate("USD", "JPY")
    fx.get_rate("USD", "JPY")
    assert get.call_count == 2


def test_missing_api_key_is_a_server_error(monkeypatch):
    monkeypatch.delenv("FX_API_KEY")
    with pytest.raises(fx.FXError) as exc:
        fx.get_rate("USD", "JPY")
    assert exc.value.status_code == 500


def test_unsupported_base_currency(monkeypatch):
    api_returns(monkeypatch, {"result": "error", "error-type": "unsupported-code"})
    with pytest.raises(fx.FXError) as exc:
        fx.get_rate("ZZZ", "USD")
    assert exc.value.status_code == 400


def test_unsupported_target_currency(monkeypatch):
    api_returns(monkeypatch, {"result": "success", "conversion_rates": {"JPY": 150}})
    with pytest.raises(fx.FXError) as exc:
        fx.get_rate("USD", "ZZZ")
    assert exc.value.status_code == 400


def test_other_api_errors_are_bad_gateway(monkeypatch):
    api_returns(monkeypatch, {"result": "error", "error-type": "quota-reached"})
    with pytest.raises(fx.FXError, match="quota-reached") as exc:
        fx.get_rate("USD", "JPY")
    assert exc.value.status_code == 502


def test_network_failure_is_bad_gateway(monkeypatch):
    monkeypatch.setattr(fx.requests, "get", MagicMock(side_effect=requests.ConnectionError()))
    with pytest.raises(fx.FXError) as exc:
        fx.get_rate("USD", "JPY")
    assert exc.value.status_code == 502


def test_convert_rounds_half_up_to_cents(monkeypatch):
    api_returns(monkeypatch, {"result": "success", "conversion_rates": {"USD": 0.006259}})
    # 45000 * 0.006259 = 281.655
    assert fx.convert(Decimal("45000"), "JPY", "USD") == (Decimal("281.66"), Decimal("0.006259"))
