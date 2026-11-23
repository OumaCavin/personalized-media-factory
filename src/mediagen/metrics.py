"""The run metrics schema and the provenance rules that go with it.

Two ideas are kept together here on purpose.

First, a run is measured in three different currencies: the time the machine
takes to start, the time a model takes to load, and the time each asset takes.
Only the third one is per asset.

Second, every metrics file says where it came from. A file that was measured
by someone else is not the same thing as a file that was measured by you, and a
cost number without that distinction is a guess with a decimal point.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

#: Provenance values the analysis understands.
OWN_RUN = "own-run"
COURSE_REFERENCE_RUN = "course-reference-run"


@dataclass(frozen=True)
class Provenance:
    """Where a measurement came from."""

    source: str
    measured_by: str
    measured_at: str
    license: str = ""
    url: str = ""
    note: str = ""

    @property
    def is_own_run(self) -> bool:
        return self.source == OWN_RUN

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "measured_by": self.measured_by,
            "measured_at": self.measured_at,
            "license": self.license,
            "url": self.url,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Provenance":
        return cls(
            source=data.get("source", "unknown"),
            measured_by=data.get("measured_by", "unknown"),
            measured_at=data.get("measured_at", "unknown"),
            license=data.get("license", ""),
            url=data.get("url", ""),
            note=data.get("note", ""),
        )


def new_provenance(
    source: str = OWN_RUN,
    measured_by: str = "Cavin Otieno",
    measured_at: str = "",
    license: str = "",
    url: str = "",
    note: str = "",
) -> Provenance:
    """Build a provenance record."""
    return Provenance(
        source=source,
        measured_by=measured_by,
        measured_at=measured_at,
        license=license,
        url=url,
        note=note,
    )


def new_step() -> dict[str, Any]:
    """An empty step record.

    ``latency_s`` is keyed by record id, so a step can be traced back to the
    asset that produced it.
    """
    return {"load_s": None, "latency_s": {}, "median_s": None, "total_s": None}


def new_metrics(
    mode: str,
    gpu: str,
    region: str,
    platform: str,
    preset: str,
    billing: str,
    config: dict[str, Any],
    provenance: Provenance | None = None,
) -> dict[str, Any]:
    """An empty metrics document for a run."""
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "provenance": (provenance or new_provenance()).to_dict(),
        "gpu": gpu,
        "region": region,
        "platform": platform,
        "preset": preset,
        "billing": billing,
        "started_at": None,
        "finished_at": None,
        "runtime_s": None,
        "startup_s": None,
        "steps": {},
        "config": config,
        "env": {},
        "assets": [],
        "status": "running",
    }


def _sidecar_path(path: Path) -> Path:
    return path.with_name(path.name + ".provenance.json")


def load_metrics(path: str | Path) -> tuple[dict[str, Any], Provenance]:
    """Read a metrics file and the provenance that goes with it.

    Provenance is looked for in the metrics document first, then in a
    ``<file>.provenance.json`` sidecar. That is what lets the published course
    run files be used byte for byte, with their provenance kept next to them
    instead of inside them.
    """
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if "provenance" in data:
        return data, Provenance.from_dict(data["provenance"])
    sidecar = _sidecar_path(path)
    if sidecar.is_file():
        return data, Provenance.from_dict(json.loads(sidecar.read_text(encoding="utf-8")))
    return data, Provenance.from_dict(
        {
            "source": "unknown",
            "measured_by": "unknown",
            "measured_at": "unknown",
            "note": "No provenance file found next to the metrics file.",
        }
    )


def save_metrics(data: dict[str, Any], path: str | Path) -> Path:
    """Write a metrics document."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def write_provenance(provenance: Provenance, path: str | Path) -> Path:
    """Write a provenance sidecar next to a metrics file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    target = _sidecar_path(path)
    target.write_text(json.dumps(provenance.to_dict(), indent=2) + "\n", encoding="utf-8")
    return target


def warn_if_not_own_run(provenance: Provenance, stream=None) -> None:
    """Print a warning when a measurement did not come from an own run."""
    if provenance.is_own_run:
        return
    import sys

    stream = stream or sys.stdout
    print(
        "WARNING: these measurements were not produced by an own run.\n"
        f"         provenance: {provenance.source} "
        f"({provenance.measured_by}, {provenance.measured_at})\n"
        "         Run scripts/run_job.sh on a Nebius account to replace them.",
        file=stream,
    )
