"""The ten origin records and the prompts built from them.

A record is the unit the whole pipeline is built around: one row becomes one
illustration, one animation and one card. Nothing in the pipeline knows what a
coffee origin is, so the same code runs over ten rows in Module 1 and over a
full catalogue later.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

#: Shared across every record so the ten assets read as one series.
#:
#: This is the cheap half of consistency. The same style suffix plus one fixed
#: seed per record gives a set that looks related; a real character or a real
#: house style needs a reference image or a trained adapter.
STYLE_SUFFIX = (
    "warm editorial illustration, soft painterly texture, muted palette of deep "
    "green, terracotta and cream, gentle depth of field, natural light, "
    "no people, no text, no lettering, no watermark, no logo"
)

#: What the camera does in the clip. Kept identical across records so the set
#: animates as one series too.
MOTION_PROMPT = (
    "slow camera drift forward, gentle movement in the leaves and branches, "
    "drifting mist or steam, soft shifting light, one continuous shot, no cuts, "
    "no text"
)

#: Base seed. Each record adds its index, so the seeds are fixed and every run
#: starts from the same noise.
BASE_SEED = 4200

FIELDS = (
    "id",
    "origin",
    "county",
    "altitude_m",
    "varietal",
    "process",
    "tasting_notes",
    "scene",
)


@dataclass(frozen=True)
class Origin:
    """One coffee origin and everything the prompts need."""

    id: str
    origin: str
    county: str
    altitude_m: int
    varietal: str
    process: str
    tasting_notes: str
    scene: str
    index: int = 0

    @property
    def seed(self) -> int:
        """A fixed seed per record, so a rerun reproduces the same assets."""
        return BASE_SEED + self.index

    @property
    def title(self) -> str:
        """The line that goes on the card."""
        return f"{self.origin} {self.process}"

    @property
    def subtitle(self) -> str:
        """The supporting line that goes on the card."""
        return f"{self.varietal} | {self.altitude_m} m | {self.tasting_notes}"

    @property
    def image_prompt(self) -> str:
        """The text to image prompt for this origin."""
        return (
            f"{self.scene}, {self.origin} coffee growing region in Kenya, "
            f"{STYLE_SUFFIX}"
        )

    @property
    def motion_prompt(self) -> str:
        """The image to video prompt for this origin."""
        return MOTION_PROMPT


def load_records(path: str | Path) -> list[Origin]:
    """Read the origin records from a CSV file.

    The CSV holds the facts. The prompts are derived from them, so editing a
    tasting note changes the card without touching any code.
    """
    records: list[Origin] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [name for name in FIELDS if name not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"records file is missing columns: {', '.join(missing)}")
        for index, row in enumerate(reader):
            records.append(
                Origin(
                    id=row["id"].strip(),
                    origin=row["origin"].strip(),
                    county=row["county"].strip(),
                    altitude_m=int(row["altitude_m"]),
                    varietal=row["varietal"].strip(),
                    process=row["process"].strip(),
                    tasting_notes=row["tasting_notes"].strip(),
                    scene=row["scene"].strip(),
                    index=index,
                )
            )
    if not records:
        raise ValueError("records file is empty")
    return records
