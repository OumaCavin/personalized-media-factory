"""Tests that the documentation still matches the code.

The homework answers are the artefact a grader reads, and they are full of
numbers. These tests recompute those numbers and look for them in the prose,
which catches the case where a price or a measurement changes and the
document does not.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mediagen import costs, metrics as metrics_mod

REPO_ROOT = Path(__file__).resolve().parents[1]
HOMEWORK = REPO_ROOT / "docs" / "module-1-homework.md"
COST_MODEL = REPO_ROOT / "docs" / "cost-model.md"
WALKTHROUGH = REPO_ROOT / "docs" / "module-1-walkthrough.md"

PRICE_PER_HOUR = 4.50
STARTUP_S = 157.7
API_PRICE = 0.2025


@pytest.fixture(scope="module")
def clip():
    document, _ = metrics_mod.load_metrics(
        REPO_ROOT
        / "data"
        / "reference_runs"
        / "course_h100_20kids_2026-11-14.json"
    )
    return costs.analyze_step(
        document,
        step="clip",
        price_per_hour=PRICE_PER_HOUR,
        api_price_per_asset=API_PRICE,
        startup_s=STARTUP_S,
        n_values=(1, 10, 100, 1000),
    )


def test_homework_quotes_the_computed_median(clip):
    assert f"{clip.median_s:.1f} s" in HOMEWORK.read_text(encoding="utf-8")


def test_homework_quotes_the_computed_marginal_cost(clip):
    assert f"${clip.marginal_usd:.4f}" in HOMEWORK.read_text(encoding="utf-8")


def test_homework_quotes_the_computed_cost_at_n_1000(clip):
    assert f"${clip.cost_by_n[1000]:.4f}" in HOMEWORK.read_text(encoding="utf-8")


def test_homework_quotes_the_computed_fixed_cost(clip):
    assert f"${clip.fixed_usd:.4f}" in HOMEWORK.read_text(encoding="utf-8")


def test_homework_quotes_the_computed_breakeven(clip):
    text = HOMEWORK.read_text(encoding="utf-8")
    assert f"{clip.breakeven_assets} assets per run" in text


def test_homework_quotes_the_api_price():
    assert "$0.2025" in HOMEWORK.read_text(encoding="utf-8")


def test_homework_answers_the_modality_question():
    assert "Which modality" in HOMEWORK.read_text(encoding="utf-8")


def test_homework_maps_both_question_sets():
    text = HOMEWORK.read_text(encoding="utf-8")
    assert "Course instructions" in text
    assert "Submission form" in text


def test_cost_model_quotes_the_same_headline_numbers(clip):
    text = COST_MODEL.read_text(encoding="utf-8")
    assert f"${clip.marginal_usd:.4f}" in text
    assert f"${clip.fixed_usd:.4f}" in text
    assert f"{clip.breakeven_assets}" in text


def test_walkthrough_covers_every_instruction_of_the_homework():
    text = WALKTHROUGH.read_text(encoding="utf-8")
    for phrase in (
        "prompts",
        "one startup",
        "preemptible",
        "N = 1000",
        "Learning in Public",
        "Billing -> Usage",
    ):
        assert phrase.lower() in text.lower(), phrase


def test_documented_prices_match_the_price_snapshot():
    prices = json.loads(
        (REPO_ROOT / "data" / "prices" / "nebius_2026-11-23.json").read_text(
            encoding="utf-8"
        )
    )
    h100 = next(
        entry for entry in prices["gpu_prices"] if entry["platform"] == "gpu-h100-sxm"
    )
    assert h100["on_demand_per_hour"] == PRICE_PER_HOUR
    assert f"${PRICE_PER_HOUR:.2f}" in COST_MODEL.read_text(encoding="utf-8")
