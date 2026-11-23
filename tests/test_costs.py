"""Tests for the cost model.

The most important tests here are the cross checks: they feed the published
course run files through this project's own cost engine and check that it
reproduces the breakevens the course published. If the engine and the course
agree on three different GPUs, the numbers this project prints can be trusted
on a GPU the course never ran.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from mediagen import costs, metrics as metrics_mod

REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_RUNS = REPO_ROOT / "data" / "reference_runs"
PRICES = REPO_ROOT / "data" / "prices"

# The machine startup the course measured on one H100 Job on 2026-11-14, and
# used for every GPU in its own cost tables.
STARTUP_S = 157.7

# fal.ai, Wan v2.2 A14B image to video, 480p. Same model as the self hosted
# run, so the comparison is a model comparison and not a quality comparison.
API_PRICE_PER_CLIP = 0.2025


def _reference(name: str) -> dict:
    document, _ = metrics_mod.load_metrics(REFERENCE_RUNS / name)
    return document


def _price(platform: str) -> float:
    data = json.loads((PRICES / "nebius_2026-11-23.json").read_text(encoding="utf-8"))
    for entry in data["gpu_prices"]:
        if entry["platform"] == platform:
            return entry["on_demand_per_hour"]
    raise KeyError(platform)


def test_rate_per_second():
    assert costs.rate_per_second(4.5) == pytest.approx(0.00125)
    assert costs.rate_per_second(3600.0) == pytest.approx(1.0)


def test_marginal_and_fixed_costs_are_additive():
    marginal = costs.marginal_cost_usd(4.5, 76.675)
    fixed = costs.fixed_cost_usd(4.5, STARTUP_S, 1045.976)
    assert marginal == pytest.approx(0.09584375)
    assert fixed == pytest.approx(1.504595)
    # One asset in a run of one costs the fixed part plus the marginal part.
    assert costs.cost_per_asset_usd(fixed, marginal, 1) == pytest.approx(fixed + marginal)


def test_cost_per_asset_falls_with_batch_size():
    marginal = costs.marginal_cost_usd(4.5, 76.675)
    fixed = costs.fixed_cost_usd(4.5, STARTUP_S, 1045.976)
    costs_by_n = {
        n: costs.cost_per_asset_usd(fixed, marginal, n) for n in (1, 10, 100, 1000)
    }
    assert costs_by_n[1] > costs_by_n[10] > costs_by_n[100] > costs_by_n[1000]
    # At N = 1000 the fixed part is 1/1000 of what it was for a single asset.
    assert costs_by_n[1000] == pytest.approx(costs_by_n[1] / 1000 + marginal * 0.999)


def test_breakeven_is_zero_when_the_api_is_cheaper_per_asset():
    marginal = costs.marginal_cost_usd(4.5, 76.675)
    fixed = costs.fixed_cost_usd(4.5, STARTUP_S, 1045.976)
    # The API is cheaper per asset than generating one: self hosting never wins.
    assert costs.breakeven_assets(fixed, marginal, marginal) == 0
    assert costs.breakeven_assets(fixed, marginal, marginal * 0.5) == 0


def test_breakeven_is_at_least_one_asset():
    assert costs.breakeven_assets(0.0, 0.01, 0.5) == 1


@pytest.mark.parametrize(
    ("run_file", "platform", "expected"),
    [
        ("course_h100_20kids_2026-11-14.json", "gpu-h100-sxm", 15),
        ("course_h200_20kids_2026-11-14.json", "gpu-h200-sxm", 12),
        (
            "course_rtxpro6000_20kids_2026-11-14.json",
            "gpu-rtx6000-a",
            3,
        ),
    ],
)
def test_engine_reproduces_the_published_breakevens(run_file, platform, expected):
    """Cross check against the breakevens the course published.

    The course published 15 clips per run on an H100, 12 on an H200 and 3 on an
    RTX PRO 6000, all at regular prices against the same fal.ai price.
    """
    document = _reference(run_file)
    analysis = costs.analyze_step(
        document,
        step="clip",
        price_per_hour=_price(platform),
        api_price_per_asset=API_PRICE_PER_CLIP,
        startup_s=STARTUP_S,
    )
    assert analysis.breakeven_assets == expected


def test_engine_reproduces_the_published_spot_price_breakeven():
    """The course published 5 clips per run at its 2026-11-14 spot snapshot."""
    document = _reference("course_h100_20kids_2026-11-14.json")
    analysis = costs.analyze_step(
        document,
        step="clip",
        price_per_hour=2.07,
        api_price_per_asset=API_PRICE_PER_CLIP,
        startup_s=STARTUP_S,
    )
    assert analysis.breakeven_assets == 5


def test_engine_reproduces_the_published_cost_at_n_200():
    """The course published about $0.10 per clip at N = 200 on an H100."""
    document = _reference("course_h100_20kids_2026-11-14.json")
    analysis = costs.analyze_step(
        document,
        step="clip",
        price_per_hour=4.50,
        api_price_per_asset=API_PRICE_PER_CLIP,
        startup_s=STARTUP_S,
        n_values=(200,),
    )
    assert analysis.cost_by_n[200] == pytest.approx(0.10, abs=0.005)


def test_cheaper_gpu_can_beat_a_faster_one():
    """Cost per asset is price times time, not time alone.

    The RTX PRO 6000 is slower per clip than the H100 but much cheaper per
    hour, so at a small batch size it produces a cheaper clip.
    """
    h100 = costs.analyze_step(
        _reference("course_h100_20kids_2026-11-14.json"),
        step="clip",
        price_per_hour=4.50,
        startup_s=STARTUP_S,
        n_values=(20,),
    )
    rtx = costs.analyze_step(
        _reference("course_rtxpro6000_20kids_2026-11-14.json"),
        step="clip",
        price_per_hour=1.80,
        startup_s=STARTUP_S,
        n_values=(20,),
    )
    assert rtx.median_s > h100.median_s
    assert rtx.cost_by_n[20] < h100.cost_by_n[20]


def test_api_price_is_computed_from_frames_and_fps():
    api_prices = json.loads(
        (PRICES / "per_call_api_2026-11-23.json").read_text(encoding="utf-8")
    )
    service = next(
        entry
        for entry in api_prices["services"]
        if entry["endpoint_id"] == "fal-ai/wan/v2.2-a14b/image-to-video"
    )
    price = costs.api_price_for_clip(service, num_frames=81, fps=16)
    # 81 frames at 16 frames per video second is 5.0625 seconds.
    assert price == pytest.approx(5.0625 * 0.04)
    assert price == pytest.approx(API_PRICE_PER_CLIP)


def test_step_median_prefers_the_recorded_median():
    step = {"median_s": 76.675, "latency_s": {"a": 1.0, "b": 2.0}}
    assert costs.step_median_seconds(step) == pytest.approx(76.675)


def test_step_median_falls_back_to_the_latency_values():
    step = {"latency_s": {"a": 1.0, "b": 3.0, "c": 5.0}}
    assert costs.step_median_seconds(step) == pytest.approx(3.0)


def test_step_median_raises_when_there_is_nothing_to_read():
    with pytest.raises(ValueError):
        costs.step_median_seconds({"latency_s": {}})


def test_unknown_step_is_reported_with_the_available_ones():
    with pytest.raises(KeyError) as error:
        costs.analyze_step(
            _reference("course_h100_20kids_2026-11-14.json"),
            step="nope",
            price_per_hour=4.50,
        )
    assert "clip" in str(error.value)


def test_reference_runs_all_carry_provenance():
    for path in sorted(REFERENCE_RUNS.glob("*.json")):
        if path.name.endswith(".provenance.json"):
            continue
        _, provenance = metrics_mod.load_metrics(path)
        assert provenance.source == metrics_mod.COURSE_REFERENCE_RUN
        assert provenance.measured_by
        assert provenance.url


def test_own_run_provenance_does_not_warn(capsys):
    metrics_mod.warn_if_not_own_run(metrics_mod.new_provenance())
    assert capsys.readouterr().out == ""
