"""Tests for the ten origin records and the prompts built from them."""

from __future__ import annotations

from pathlib import Path

import pytest

from mediagen import records
from mediagen.specs import IMAGE_SETTINGS, VIDEO_SETTINGS

REPO_ROOT = Path(__file__).resolve().parents[1]
RECORDS_CSV = REPO_ROOT / "data" / "origins.csv"


@pytest.fixture(scope="module")
def rows():
    return records.load_records(RECORDS_CSV)


def test_there_are_ten_records(rows):
    assert len(rows) == 10


def test_record_ids_are_unique(rows):
    assert len({row.id for row in rows}) == len(rows)


def test_seeds_are_fixed_and_different(rows):
    seeds = [row.seed for row in rows]
    assert len(set(seeds)) == len(seeds)
    assert seeds == [records.BASE_SEED + index for index in range(len(rows))]


def test_prompts_carry_the_shared_style(rows):
    for row in rows:
        assert records.STYLE_SUFFIX in row.image_prompt
        assert row.motion_prompt == records.MOTION_PROMPT


def test_prompts_ask_for_no_text_and_no_people(rows):
    for row in rows:
        assert "no text" in row.image_prompt
        assert "no people" in row.image_prompt


def test_every_prompt_mentions_its_own_origin(rows):
    for row in rows:
        assert row.origin in row.image_prompt


def test_the_clip_settings_match_the_per_call_api_billing():
    # The per call APIs bill video seconds and count 16 frames as one second,
    # so these two numbers decide what an API charges for one clip.
    assert VIDEO_SETTINGS.num_frames == 81
    assert VIDEO_SETTINGS.fps == 16
    assert VIDEO_SETTINGS.video_seconds == pytest.approx(5.0625)


def test_the_illustration_is_square_and_the_clip_is_wide():
    assert IMAGE_SETTINGS.width == IMAGE_SETTINGS.height == 512
    assert VIDEO_SETTINGS.width == 832
    assert VIDEO_SETTINGS.height == 480


def test_loading_a_missing_column_is_an_error(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("id,origin\no1,Nyeri\n", encoding="utf-8")
    with pytest.raises(ValueError) as error:
        records.load_records(bad)
    assert "county" in str(error.value)


def test_loading_an_empty_file_is_an_error(tmp_path):
    empty = tmp_path / "empty.csv"
    empty.write_text(",".join(records.FIELDS) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        records.load_records(empty)
