import os
from decimal import Decimal

import requests

TROY_OUNCE_IN_GRAMS = Decimal("31.1034768")

API_URL = os.getenv(
    "METALPRICE_API_URL",
    "https://api.metalpriceapi.com/v1",
)

API_SYMBOLS = {
    "Gold": "XAU",
    "Silver": "XAG",
    "Platinum": "XPT",
}

PURITY_FACTORS = {
    ("Gold", "24K"): Decimal("1.000"),
    ("Gold", "22K"): Decimal("0.916"),
    ("Gold", "18K"): Decimal("0.750"),
    ("Gold", "14K"): Decimal("0.585"),
    ("Silver", "925"): Decimal("0.925"),
    ("Platinum", "950"): Decimal("0.950"),
}


class MetalRateAPIError(Exception):
    pass


def fetch_pure_metal_rates():
    api_key = os.getenv("METALPRICE_API_KEY")

    if not api_key:
        raise MetalRateAPIError(
            "METALPRICE_API_KEY is not configured."
        )

    try:
        response = requests.get(
            f"{API_URL}/latest",
            headers={
                "X-API-KEY": api_key,
                "Content-Type": "application/json",
            },
            params={
                "base": "INR",
                "currencies": "XAU,XAG,XPT",
            },
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise MetalRateAPIError(
            f"MetalpriceAPI request failed: {exc}"
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise MetalRateAPIError(
            "MetalpriceAPI returned invalid JSON."
        ) from exc

    if payload.get("success") is False:
        raise MetalRateAPIError(
            str(payload.get("error") or "API request failed.")
        )

    rates = payload.get("rates") or {}
    result = {}

    for metal, symbol in API_SYMBOLS.items():
        raw_rate = rates.get(symbol)

        if raw_rate is None:
            raise MetalRateAPIError(
                f"API response is missing {symbol}."
            )

        metal_units_per_inr = Decimal(str(raw_rate))

        if metal_units_per_inr <= 0:
            raise MetalRateAPIError(
                f"API returned an invalid {symbol} value."
            )

        inr_per_troy_ounce = Decimal("1") / metal_units_per_inr

        result[metal] = (
            inr_per_troy_ounce / TROY_OUNCE_IN_GRAMS
        ).quantize(Decimal("0.01"))

    return result
