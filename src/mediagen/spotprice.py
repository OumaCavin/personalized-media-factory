"""Live spot prices for preemptible GPUs.

Spot prices are the price of a preemptible GPU hour right now, in a specific
region. They change every fifteen minutes, they differ between regions, and
they are not capped above the on-demand rate, so any cost projection built on a
spot price is a projection against a snapshot.

Nebius publishes the current prices through a public endpoint that needs no
login:

    https://api.nebius.cloud/billing/v1alpha1/spot-price

Reading the live price is the difference between quoting a number that was
true this morning and quoting one that is true now.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable

SPOT_PRICE_URL = "https://api.nebius.cloud/billing/v1alpha1/spot-price"


@dataclass(frozen=True)
class SpotPrice:
    """One preemptible price for one platform in one region."""

    platform: str
    region: str
    price_per_hour: float
    effective_at: str
    title: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "region": self.region,
            "price_per_hour": self.price_per_hour,
            "effective_at": self.effective_at,
            "title": self.title,
        }


def parse_spot_prices(payload: dict[str, Any]) -> list[SpotPrice]:
    """Turn the API payload into a list of prices.

    Kept separate from the fetch so it can be tested without a network.
    """
    prices: list[SpotPrice] = []
    for item in payload.get("items", []):
        compute = item.get("computeInstance") or {}
        price = item.get("price") or {}
        if not compute.get("platform"):
            continue
        try:
            value = float(price.get("value"))
        except (TypeError, ValueError):
            continue
        prices.append(
            SpotPrice(
                platform=compute["platform"],
                region=item.get("region", ""),
                price_per_hour=value,
                effective_at=item.get("effectiveTime", ""),
                title=item.get("productTitle", ""),
            )
        )
    prices.sort(key=lambda price: (price.platform, price.region))
    return prices


def fetch_spot_prices(url: str = SPOT_PRICE_URL, timeout: int = 20) -> list[SpotPrice]:
    """Read the current spot prices. No authentication needed."""
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "mediagen-spot-price/0.1 (+https://github.com/OumaCavin/personalized-media-factory)",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    return parse_spot_prices(payload)


def find_price(
    prices: Iterable[SpotPrice], platform: str, region: str | None = None
) -> SpotPrice | None:
    """The price for one platform, optionally narrowed to one region.

    Returns ``None`` when the platform has no published spot price, which is
    the usual signal that there is no preemptible capacity for it right now.
    """
    matches = [price for price in prices if price.platform == platform]
    if region:
        matches = [price for price in matches if price.region == region]
    if not matches:
        return None
    return min(matches, key=lambda price: price.price_per_hour)


def platform_regions(prices: Iterable[SpotPrice], platform: str) -> list[str]:
    """Every region that currently publishes a spot price for a platform."""
    return sorted({price.region for price in prices if price.platform == platform})
