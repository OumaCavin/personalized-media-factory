"""The fixed and marginal cost model.

A run has two kinds of cost and they behave differently.

``F`` is paid once per run: the machine starts, the container pulls, the model
weights are downloaded and loaded. It is paid no matter how many assets the run
makes, so spread over ``N`` assets it contributes ``F / N`` to each one.

``c`` is paid once per asset: the generation itself. It does not get cheaper
when the batch gets bigger.

So the cost of one asset in a run of ``N`` assets is::

    cost_per_asset(N) = F / N + c

The per call API alternative charges ``p`` per asset and has no fixed part at
all. Self hosting wins from the first ``N`` where ``F / N + c`` drops below
``p``::

    breakeven_N = ceil(F / (p - c))

If ``p <= c`` there is no such ``N``: the API is cheaper per asset than the
marginal cost of generating it, so self hosting never wins no matter how large
the batch is. The convention used here for that case is ``0``.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

SECONDS_PER_HOUR = 3600.0


def rate_per_second(price_per_hour: float) -> float:
    """The price of one second of GPU time."""
    if price_per_hour <= 0:
        raise ValueError("price per hour must be positive")
    return price_per_hour / SECONDS_PER_HOUR


def marginal_cost_usd(price_per_hour: float, median_seconds: float) -> float:
    """``c``: what one more asset costs, in USD."""
    return rate_per_second(price_per_hour) * median_seconds


def fixed_cost_usd(price_per_hour: float, startup_s: float, load_s: float) -> float:
    """``F``: what the run costs before it makes any asset, in USD."""
    return rate_per_second(price_per_hour) * (startup_s + load_s)


def cost_per_asset_usd(fixed_usd: float, marginal_usd: float, n_assets: int) -> float:
    """The projected cost of one asset in a run of ``n_assets`` assets."""
    if n_assets < 1:
        raise ValueError("n_assets must be at least 1")
    return fixed_usd / n_assets + marginal_usd


def breakeven_assets(
    fixed_usd: float, marginal_usd: float, api_price_per_asset: float
) -> int:
    """The number of assets per run from which self hosting wins.

    Returns ``0`` when the per call API is cheaper per asset than the marginal
    cost of generating one, because in that case self hosting never wins.
    """
    if api_price_per_asset <= marginal_usd:
        return 0
    if fixed_usd <= 0:
        return 1
    return max(1, math.ceil(fixed_usd / (api_price_per_asset - marginal_usd)))


def projected_run_seconds(
    metrics: dict[str, Any],
    n_assets: int,
    startup_s: float | None = None,
    steps: Sequence[str] | None = None,
) -> float:
    """How many seconds a run of ``n_assets`` assets takes.

    Startup plus every model load, plus the median time of each asset in each
    step. This is the number a price has to be multiplied by to get the cost of
    a run.
    """
    available = metrics.get("steps") or {}
    chosen = list(steps) if steps else list(available)
    startup = float(
        startup_s if startup_s is not None else metrics.get("startup_s") or 0.0
    )
    total = startup
    for name in chosen:
        step = available.get(name)
        if not step:
            continue
        total += float(step.get("load_s") or 0.0)
        total += n_assets * step_median_seconds(step)
    return total


def step_median_seconds(step: dict[str, Any]) -> float:
    """The median time of one step, in seconds.

    The median is used rather than the mean on purpose: the first asset of a
    model is a warm up and is several times slower than the rest, and it is
    paid once per run, not once per asset.
    """
    median = step.get("median_s")
    if median is not None:
        return float(median)
    latencies = list((step.get("latency_s") or {}).values())
    if not latencies:
        raise ValueError("step has no latency measurements")
    return float(statistics.median(latencies))


@dataclass
class StepAnalysis:
    """The cost picture for one step of one run."""

    step: str
    load_s: float
    median_s: float
    price_per_hour: float
    marginal_usd: float
    fixed_usd: float
    api_price_per_asset: float | None = None
    breakeven_assets: int | None = None
    cost_by_n: dict[int, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "load_s": self.load_s,
            "median_s": self.median_s,
            "price_per_hour": self.price_per_hour,
            "marginal_usd": self.marginal_usd,
            "fixed_usd": self.fixed_usd,
            "api_price_per_asset": self.api_price_per_asset,
            "breakeven_assets": self.breakeven_assets,
            "cost_by_n": {str(n): value for n, value in sorted(self.cost_by_n.items())},
        }


def analyze_step(
    metrics: dict[str, Any],
    step: str,
    price_per_hour: float,
    api_price_per_asset: float | None = None,
    startup_s: float | None = None,
    n_values: Sequence[int] = (1, 10, 100, 1000),
    include_startup_in_fixed: bool = True,
) -> StepAnalysis:
    """Analyse one step of a run.

    ``include_startup_in_fixed`` decides whether the machine startup is part of
    ``F``. It should be for a complete run. It is turned off when a step is
    compared with a per call API on its own, because then the comparison is
    about that step rather than about the whole pipeline.
    """
    steps = metrics.get("steps") or {}
    if step not in steps:
        raise KeyError(
            f"step {step!r} not found in the run; available steps: "
            f"{', '.join(sorted(steps)) or 'none'}"
        )
    step_data = steps[step]
    load_s = float(step_data.get("load_s") or 0.0)
    median_s = step_median_seconds(step_data)
    startup = float(startup_s if startup_s is not None else metrics.get("startup_s") or 0.0)

    fixed = fixed_cost_usd(
        price_per_hour,
        startup if include_startup_in_fixed else 0.0,
        load_s,
    )
    marginal = marginal_cost_usd(price_per_hour, median_s)

    analysis = StepAnalysis(
        step=step,
        load_s=load_s,
        median_s=median_s,
        price_per_hour=price_per_hour,
        marginal_usd=marginal,
        fixed_usd=fixed,
        api_price_per_asset=api_price_per_asset,
    )
    if api_price_per_asset is not None:
        analysis.breakeven_assets = breakeven_assets(fixed, marginal, api_price_per_asset)
    for n in n_values:
        analysis.cost_by_n[n] = cost_per_asset_usd(fixed, marginal, n)
    return analysis


def api_price_for_clip(
    service_entry: dict[str, Any],
    num_frames: int,
    fps: int,
    resolution: str = "480p",
) -> float:
    """What a per call API charges for one clip of this length.

    The per call APIs bill video seconds and count ``fps`` frames as one
    second, so the price is ``frames / fps`` times the per second rate.
    """
    rate = None
    for candidate in service_entry.get("rates", []):
        if candidate.get("resolution") == resolution:
            rate = candidate.get("price_per_video_second")
            break
    if rate is None:
        raise KeyError(f"no {resolution} rate in the price snapshot")
    return (num_frames / fps) * float(rate)


def summarise(
    analyses: Iterable[StepAnalysis],
    totals: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Collect a set of step analyses into one document."""
    analyses = list(analyses)
    result: dict[str, Any] = {
        "steps": [analysis.as_dict() for analysis in analyses],
    }
    if totals:
        result["totals"] = totals
    return result
