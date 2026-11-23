"""Tests for the live spot price reader.

The parsing is separated from the network call so it can be checked against a
recorded payload.
"""

from __future__ import annotations

from mediagen import spotprice

PAYLOAD = {
    "items": [
        {
            "skuId": "sku-1",
            "productTitle": "Preemptible NVIDIA H100 NVLink",
            "region": "eu-north1",
            "computeInstance": {"platform": "gpu-h100-sxm"},
            "price": {"value": "2.37", "currency": "usd", "unitTitle": "GPU hour"},
            "effectiveTime": "2026-11-23T18:56:00Z",
        },
        {
            "skuId": "sku-2",
            "productTitle": "Preemptible NVIDIA H200 NVLink",
            "region": "eu-west1",
            "computeInstance": {"platform": "gpu-h200-sxm"},
            "price": {"value": "1.3", "currency": "usd", "unitTitle": "GPU hour"},
            "effectiveTime": "2026-11-23T20:41:00Z",
        },
        {
            "skuId": "sku-3",
            "region": "eu-north1",
            "computeInstance": {},
            "price": {"value": "9.99"},
        },
    ]
}


def test_parse_reads_platform_region_and_price():
    prices = spotprice.parse_spot_prices(PAYLOAD)
    assert len(prices) == 2
    h100 = prices[0]
    assert h100.platform == "gpu-h100-sxm"
    assert h100.region == "eu-north1"
    assert h100.price_per_hour == 2.37
    assert h100.effective_at == "2026-11-23T18:56:00Z"


def test_entries_without_a_platform_are_skipped():
    prices = spotprice.parse_spot_prices(PAYLOAD)
    assert all(price.platform for price in prices)


def test_find_price_picks_the_cheapest_match():
    prices = spotprice.parse_spot_prices(PAYLOAD)
    found = spotprice.find_price(prices, "gpu-h200-sxm")
    assert found is not None
    assert found.region == "eu-west1"
    assert found.price_per_hour == 1.3


def test_find_price_returns_none_when_the_region_has_no_price():
    prices = spotprice.parse_spot_prices(PAYLOAD)
    assert spotprice.find_price(prices, "gpu-h100-sxm", "eu-west2") is None


def test_platform_regions_lists_every_region_with_a_price():
    prices = spotprice.parse_spot_prices(PAYLOAD)
    assert spotprice.platform_regions(prices, "gpu-h100-sxm") == ["eu-north1"]


def test_an_empty_payload_yields_no_prices():
    assert spotprice.parse_spot_prices({"items": []}) == []
