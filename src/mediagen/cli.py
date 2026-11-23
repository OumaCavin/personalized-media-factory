"""Command line entry point.

Four commands, one per job:

``plan``             show the ten records and the prompts they turn into
``analyze``          turn a metrics file into a cost table and a breakeven
``report``           print the homework answers, generated from the data
``annotate-startup`` fill in the machine startup a Job cannot see for itself
``verify``           check the repository against its own house rules
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mediagen import costs, metrics as metrics_mod, records
from mediagen.specs import H100, IMAGE_SETTINGS, SANA, VIDEO_SETTINGS, WAN_I2V

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECORDS = REPO_ROOT / "data" / "origins.csv"
DEFAULT_METRICS = (
    REPO_ROOT
    / "data"
    / "reference_runs"
    / "course_h100_20kids_2026-11-14.json"
)
DEFAULT_PRICES = REPO_ROOT / "data" / "prices" / "nebius_2026-11-23.json"
DEFAULT_API_PRICES = REPO_ROOT / "data" / "prices" / "per_call_api_2026-11-23.json"
DEFAULT_STARTUP = (
    REPO_ROOT
    / "data"
    / "reference_runs"
    / "course_startup_h100_2026-11-14.json"
)

#: The house rules this repository is checked against.
RULES_FILE = REPO_ROOT / "data" / "house-rules.json"

#: Ranges of characters that would mean the repository is not English only.
CJK_RANGES = (
    (0x3000, 0x303F),
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
    (0xFF00, 0xFFEF),
    (0x20000, 0x2A6DF),
)

COMMIT_PATTERN = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-z0-9._/-]+\))?: .+"
)


def _load_rules() -> dict[str, Any]:
    """The house rules, from a data file rather than from this module.

    A checker that hardcodes the strings it forbids contains them itself, so
    the rules live in ``data/house-rules.json`` and are read from there.
    """
    if not RULES_FILE.is_file():
        raise SystemExit(f"house rules file is missing: {RULES_FILE}")
    return _load_json(RULES_FILE)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_gpu_price(prices: dict[str, Any], platform: str) -> dict[str, Any]:
    for entry in prices.get("gpu_prices", []):
        if entry.get("platform") == platform:
            return entry
    raise KeyError(f"no price for platform {platform!r} in the price snapshot")


def _find_api_service(api_prices: dict[str, Any], endpoint_id: str) -> dict[str, Any]:
    for entry in api_prices.get("services", []):
        if entry.get("endpoint_id") == endpoint_id:
            return entry
    raise KeyError(f"no price for endpoint {endpoint_id!r} in the API snapshot")


def _fmt_usd(value: float, places: int = 6) -> str:
    return f"${value:.{places}f}"


# --------------------------------------------------------------------------
# plan
# --------------------------------------------------------------------------
def cmd_plan(args: argparse.Namespace) -> int:
    rows = records.load_records(args.records)
    if args.limit:
        rows = rows[: args.limit]
    print(f"{len(rows)} records from {args.records}\n")
    for row in rows:
        print(f"--- {row.id}  {row.title}")
        print(f"    subtitle : {row.subtitle}")
        print(f"    seed     : {row.seed}")
        print(f"    image    : {row.image_prompt}")
        print(f"    motion   : {row.motion_prompt}")
        print()
    print(
        f"illustration: {SANA.pinned_id} at {IMAGE_SETTINGS.width}x{IMAGE_SETTINGS.height}, "
        f"{IMAGE_SETTINGS.num_inference_steps} steps"
    )
    print(
        f"clip        : {WAN_I2V.pinned_id} at {VIDEO_SETTINGS.width}x{VIDEO_SETTINGS.height}, "
        f"{VIDEO_SETTINGS.num_frames} frames at {VIDEO_SETTINGS.fps} fps "
        f"({VIDEO_SETTINGS.video_seconds} s)"
    )
    return 0


# --------------------------------------------------------------------------
# analyze
# --------------------------------------------------------------------------
def _resolve_startup(document: dict[str, Any], args: argparse.Namespace) -> float:
    """Find the machine startup for this run.

    A Job cannot see its own startup: the worker is inside the container and
    the Job is outside it. The startup is measured from the Job metadata and
    supplied from outside, either inside the metrics file or in a separate
    startup file. An explicit ``--startup-s`` wins over both.
    """
    if args.startup_s is not None:
        return float(args.startup_s)
    if document.get("startup_s") is not None:
        return float(document["startup_s"])
    startup_file = Path(args.startup_file)
    if startup_file.is_file():
        return float(_load_json(startup_file)["startup_s"])
    return 0.0


def _analysis_inputs(
    args: argparse.Namespace,
) -> tuple[dict[str, Any], float, float, metrics_mod.Provenance, float]:
    document, provenance = metrics_mod.load_metrics(args.metrics)
    prices = _load_json(Path(args.prices))
    api_prices = _load_json(Path(args.api_prices))
    gpu = _find_gpu_price(prices, args.platform)
    price = float(args.price_per_hour if args.price_per_hour is not None else gpu["on_demand_per_hour"])
    service = _find_api_service(api_prices, args.api_endpoint)
    api_price = costs.api_price_for_clip(
        service,
        num_frames=VIDEO_SETTINGS.num_frames,
        fps=VIDEO_SETTINGS.fps,
        resolution=args.resolution,
    )
    startup = _resolve_startup(document, args)
    return document, price, api_price, provenance, startup


def cmd_analyze(args: argparse.Namespace) -> int:
    document, price, api_price, provenance, startup = _analysis_inputs(args)
    metrics_mod.warn_if_not_own_run(provenance)

    print(f"metrics : {args.metrics}")
    print(f"gpu     : {document.get('gpu')} ({document.get('platform')}, {document.get('region')})")
    print(f"price   : {_fmt_usd(price, 2)} per GPU hour")
    print(f"api     : {_fmt_usd(api_price)} per asset\n")

    for step in args.step:
        analysis = costs.analyze_step(
            document,
            step=step,
            price_per_hour=price,
            api_price_per_asset=api_price,
            startup_s=startup,
        )
        print(f"step: {step}")
        print(f"  load time          : {analysis.load_s:.3f} s")
        print(f"  median per asset   : {analysis.median_s:.3f} s")
        print(f"  marginal cost c    : {_fmt_usd(analysis.marginal_usd)} per asset")
        print(f"  fixed cost F       : {_fmt_usd(analysis.fixed_usd)} per run")
        if analysis.breakeven_assets is not None:
            if analysis.breakeven_assets == 0:
                print("  breakeven N        : never (0)")
            else:
                print(f"  breakeven N        : {analysis.breakeven_assets} assets per run")
        print("  projected cost per asset:")
        for n, value in sorted(analysis.cost_by_n.items()):
            print(f"    N = {n:<5} {_fmt_usd(value)}")
        print()
    return 0


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------
def cmd_report(args: argparse.Namespace) -> int:
    document, price, api_price, provenance, startup = _analysis_inputs(args)
    api_prices = _load_json(Path(args.api_prices))
    service = _find_api_service(api_prices, args.api_endpoint)
    clip = costs.analyze_step(
        document,
        step=args.step[0],
        price_per_hour=price,
        api_price_per_asset=api_price,
        startup_s=startup,
    )
    # The CPU stage is called "first_frame" in this pipeline and "card" in the
    # published course runs. Pick whichever the run actually has.
    pipeline_steps = ["illustration", "first_frame", "clip"]
    available = document.get("steps") or {}
    if "first_frame" not in available and "card" in available:
        pipeline_steps = ["illustration", "card", "clip"]
    pipeline = costs.analyze_step(
        document,
        step=args.step[0],
        price_per_hour=price,
        api_price_per_asset=None,
        startup_s=args.startup_s,
    )
    pipeline_marginal = 0.0
    pipeline_fixed = 0.0
    pipeline_seconds = 0.0
    for name in pipeline_steps:
        if name not in (document.get("steps") or {}):
            continue
        step_analysis = costs.analyze_step(
            document,
            step=name,
            price_per_hour=price,
            api_price_per_asset=None,
            startup_s=startup if name == pipeline_steps[0] else 0.0,
            include_startup_in_fixed=(name == pipeline_steps[0]),
        )
        pipeline_marginal += step_analysis.marginal_usd
        pipeline_fixed += step_analysis.fixed_usd
        pipeline_seconds += step_analysis.median_s

    print("## Module 1 answers\n")
    print(
        f"Generated by `mediagen report` on "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}. "
        f"Provenance of the measurements: `{provenance.source}` "
        f"({provenance.measured_by}, {provenance.measured_at}).\n"
    )
    print("| Question | Answer |")
    print("| --- | --- |")
    print(
        f"| 5. Median generation time per asset | "
        f"{clip.median_s:.1f} s ({args.step[0]} stage) |"
    )
    print(f"| 6. Marginal compute cost per asset, c | {_fmt_usd(clip.marginal_usd)} |")
    print(
        f"| 7. Per call API compared | {service['service']}, "
        f"{service['endpoint_id']}, {_fmt_usd(api_price)} per asset |"
    )
    breakeven = clip.breakeven_assets
    print(
        f"| 8. Self host breakeven N | "
        f"{breakeven if breakeven else 'never (0)'} assets per run |"
    )
    print()
    print("### Cost of one asset\n")
    print("| N assets per run | Cost per asset |")
    print("| ---: | ---: |")
    for n, value in sorted(clip.cost_by_n.items()):
        print(f"| {n} | {_fmt_usd(value)} |")
    print()
    print(
        f"Full pipeline marginal cost per origin card: "
        f"{_fmt_usd(pipeline_marginal)} "
        f"({pipeline_seconds:.1f} s of generation across the illustration, first frame "
        f"and clip stages). "
        f"Fixed cost per run across the whole pipeline: {_fmt_usd(pipeline_fixed)}."
    )
    return 0


# --------------------------------------------------------------------------
# compare
# --------------------------------------------------------------------------
def cmd_compare(args: argparse.Namespace) -> int:
    """Compare the same step across several GPUs."""
    prices = _load_json(Path(args.prices))
    rows = []
    for item in args.runs:
        if "=" not in item:
            raise SystemExit(f"--runs entries look like platform=path, got {item!r}")
        platform, path = item.split("=", 1)
        document, provenance = metrics_mod.load_metrics(path)
        price = float(
            args.price_per_hour
            if args.price_per_hour is not None
            else _find_gpu_price(prices, platform)["on_demand_per_hour"]
        )
        startup = _resolve_startup(document, args)
        analysis = costs.analyze_step(
            document,
            step=args.step,
            price_per_hour=price,
            api_price_per_asset=args.api_price,
            startup_s=startup,
            n_values=tuple(args.n_values),
        )
        rows.append((platform, price, analysis, provenance.source))

    print("| GPU platform | Price/h | Median s | Load s | c per asset | F per run | cost at N=20 | Breakeven N |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for platform, price, analysis, source in rows:
        breakeven = analysis.breakeven_assets
        breakeven_text = "never (0)" if breakeven == 0 else str(breakeven)
        cost_20 = analysis.cost_by_n.get(20)
        cost_text = f"${cost_20:.4f}" if cost_20 is not None else "-"
        print(
            f"| {platform} | ${price:.2f} | {analysis.median_s:.1f} | {analysis.load_s:.1f} | "
            f"${analysis.marginal_usd:.4f} | ${analysis.fixed_usd:.4f} | {cost_text} | {breakeven_text} |"
        )
    print()
    print(f"Per call API price used: ${args.api_price} per asset. Measurements: "
          + ", ".join(sorted({row[3] for row in rows})) + ".")
    return 0


# --------------------------------------------------------------------------
# annotate-startup
# --------------------------------------------------------------------------
def cmd_annotate_startup(args: argparse.Namespace) -> int:
    document, _ = metrics_mod.load_metrics(args.metrics)
    created = datetime.fromisoformat(args.created_at)
    started = datetime.fromisoformat(args.started_at)
    startup_s = (started - created).total_seconds()
    document["startup_s"] = round(startup_s, 3)
    metrics_mod.save_metrics(document, Path(args.metrics))
    print(f"startup_s = {startup_s:.3f} written to {args.metrics}")
    return 0


# --------------------------------------------------------------------------
# verify
# --------------------------------------------------------------------------
def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    ).stdout.strip()


def cmd_verify(args: argparse.Namespace) -> int:
    problems: list[str] = []
    rules = _load_rules()

    name = _git("config", "user.name")
    email = _git("config", "user.email")
    if name != rules["git_user_name"]:
        problems.append(
            f"git user.name is {name!r}, expected {rules['git_user_name']!r}"
        )
    if email != rules["git_user_email"]:
        problems.append(
            f"git user.email is {email!r}, expected {rules['git_user_email']!r}"
        )
    print(f"git user.name  : {name}")
    print(f"git user.email : {email}")

    subjects = [
        line for line in _git("log", "--format=%s").splitlines() if line.strip()
    ]
    pattern = re.compile(rules["commit_pattern"])
    bad_subjects = [s for s in subjects if not pattern.match(s)]
    print(f"commits checked: {len(subjects)}")
    for subject in subjects:
        print(f"  {subject}")
    if bad_subjects:
        problems.append(
            "commit messages that do not match <type>(<scope>): <description>: "
            + "; ".join(bad_subjects)
        )

    tracked = _git("ls-files").splitlines()
    exempt = {entry["path"]: entry.get("reason", "") for entry in rules.get("exempt_files", [])}
    for relative in tracked:
        path = REPO_ROOT / relative
        if not path.is_file():
            continue
        if relative in exempt:
            print(f"exempt: {relative} ({exempt[relative]})")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        lowered = text.lower()
        for forbidden in rules["forbidden_strings"]:
            if forbidden.lower() in lowered:
                problems.append(f"{relative} contains the forbidden string {forbidden!r}")
        for char in text:
            code = ord(char)
            if any(low <= code <= high for low, high in CJK_RANGES):
                problems.append(f"{relative} contains a CJK character {char!r}")
                break

    print(f"files checked  : {len(tracked)}")
    if problems:
        print("\nFAILED:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\nAll checks passed.")
    return 0


# --------------------------------------------------------------------------
# parser
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mediagen", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="show the records and the prompts")
    plan.add_argument("--records", default=str(DEFAULT_RECORDS))
    plan.add_argument("--limit", type=int, default=0)
    plan.set_defaults(func=cmd_plan)

    for name, help_text in (
        ("analyze", "turn a metrics file into a cost table"),
        ("report", "print the homework answers"),
    ):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--metrics", default=str(DEFAULT_METRICS))
        command.add_argument("--prices", default=str(DEFAULT_PRICES))
        command.add_argument("--api-prices", default=str(DEFAULT_API_PRICES))
        command.add_argument("--platform", default=H100.platform)
        command.add_argument("--price-per-hour", type=float, default=None)
        command.add_argument(
            "--api-endpoint", default="fal-ai/wan/v2.2-a14b/image-to-video"
        )
        command.add_argument("--resolution", default="480p")
        command.add_argument("--startup-s", type=float, default=None)
        command.add_argument("--startup-file", default=str(DEFAULT_STARTUP))
        command.add_argument(
            "--step", action="append", default=None, help="step to analyse"
        )
        if name == "report":
            command.set_defaults(func=cmd_report, step=["clip"])
        else:
            command.set_defaults(func=cmd_analyze, step=["clip"])

    compare = sub.add_parser("compare", help="compare one step across several GPUs")
    compare.add_argument("--runs", action="append", required=True,
                          help="platform=path/to/metrics.json")
    compare.add_argument("--prices", default=str(DEFAULT_PRICES))
    compare.add_argument("--platform", default=H100.platform)
    compare.add_argument("--price-per-hour", type=float, default=None)
    compare.add_argument("--step", default="clip")
    compare.add_argument("--api-price", type=float, default=0.2025)
    compare.add_argument("--startup-s", type=float, default=None)
    compare.add_argument("--startup-file", default=str(DEFAULT_STARTUP))
    compare.add_argument("--n-values", type=int, action="append", default=None)
    compare.set_defaults(func=cmd_compare)

    annotate = sub.add_parser("annotate-startup", help="fill in the machine startup")
    annotate.add_argument("--metrics", required=True)
    annotate.add_argument("--created-at", required=True)
    annotate.add_argument("--started-at", required=True)
    annotate.set_defaults(func=cmd_annotate_startup)

    verify = sub.add_parser("verify", help="check the repository against its house rules")
    verify.set_defaults(func=cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command in ("analyze", "report") and args.step is None:
        args.step = ["clip"]
    if args.command == "compare" and not args.n_values:
        args.n_values = [20]
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
