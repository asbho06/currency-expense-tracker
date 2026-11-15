"""Exchange rates from exchangerate-api.com, cached in memory."""
import os
import threading
import time
from decimal import ROUND_HALF_UP, Decimal

import requests

FX_API_BASE = "https://v6.exchangerate-api.com/v6"
CACHE_TTL_SECONDS = 60 * 60  # rates only update daily on the free plan; an hour is plenty
CENTS = Decimal("0.01")

_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()


class FXError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _latest_rates(base: str) -> dict:
    now = time.monotonic()
    with _lock:
        cached = _cache.get(base)
        if cached and now - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]

    # Read at call time so the key is picked up after load_dotenv() runs
    api_key = os.getenv("FX_API_KEY")
    if not api_key:
        raise FXError("FX_API_KEY is not set", status_code=500)

    try:
        response = requests.get(f"{FX_API_BASE}/{api_key}/latest/{base}", timeout=5)
        data = response.json()
    except (requests.RequestException, ValueError):
        raise FXError("Failed to fetch exchange rates")

    if data.get("result") != "success":
        error = data.get("error-type", "unknown-error")
        if error == "unsupported-code":
            raise FXError(f"Unsupported currency: {base}", status_code=400)
        raise FXError(f"Exchange rate API error: {error}")

    rates = data["conversion_rates"]
    with _lock:
        _cache[base] = (now, rates)
    return rates


def get_rate(from_currency: str, to_currency: str) -> Decimal:
    """How many `to_currency` you get for 1 `from_currency`."""
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()
    if from_currency == to_currency:
        return Decimal("1")

    rate = _latest_rates(from_currency).get(to_currency)
    if rate is None:
        raise FXError(f"Unsupported currency: {to_currency}", status_code=400)
    # str() avoids carrying float binary noise into the Decimal
    return Decimal(str(rate))


def convert(amount: Decimal, from_currency: str, to_currency: str) -> tuple[Decimal, Decimal]:
    """Returns (converted amount rounded to cents, rate used)."""
    rate = get_rate(from_currency, to_currency)
    return (amount * rate).quantize(CENTS, rounding=ROUND_HALF_UP), rate
