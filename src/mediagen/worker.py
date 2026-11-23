"""The GPU worker: ten origins in, ten animations out, with the timings written down.

This module runs inside the container, on the GPU, inside a Nebius Serverless AI
Job. It does four things and nothing else:

1. read the origin records,
2. draw one illustration per origin with Sana,
3. turn each illustration into a five second clip with Wan2.2,
4. write the assets and a metrics file that records every second spent.

The GPU heavy imports are inside the functions, so this module can be imported
on a laptop without a GPU. That matters, because the analysis and the tests run
on a laptop and the worker does not.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mediagen import metrics as metrics_mod
from mediagen.records import Origin, load_records
from mediagen.specs import (
    H100,
    IMAGE_SETTINGS,
    L40S,
    SANA,
    VIDEO_SETTINGS,
    WAN_I2V,
)

#: The steps the worker can run, in the order it runs them.
STEPS = ("illustration", "first_frame", "clip")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record_step(step: dict[str, Any], key: str, seconds: float) -> None:
    step["latency_s"][key] = round(seconds, 3)
    values = list(step["latency_s"].values())
    step["median_s"] = round(sorted(values)[len(values) // 2], 3) if len(values) % 2 else None
    if values:
        ordered = sorted(values)
        middle = len(ordered) // 2
        if len(ordered) % 2:
            step["median_s"] = round(ordered[middle], 3)
        else:
            step["median_s"] = round((ordered[middle - 1] + ordered[middle]) / 2, 3)
    step["total_s"] = round(sum(values), 3)


def load_sana_pipeline():
    """Load Sana onto the GPU.

    The Sana recipe needs the transformer in fp16 and the text encoder and VAE
    in bf16, otherwise the output is black.
    """
    import torch
    from diffusers import SanaPipeline

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available; this worker needs a GPU runtime")
    pipe = SanaPipeline.from_pretrained(
        SANA.repo_id,
        revision=SANA.revision,
        variant="fp16",
        torch_dtype=torch.float16,
    ).to("cuda")
    pipe.text_encoder.to(torch.bfloat16)
    pipe.vae.to(torch.bfloat16)
    pipe.set_progress_bar_config(disable=True)
    return pipe


def load_wan_pipeline():
    """Load Wan2.2 image to video onto the GPU."""
    import torch
    from diffusers import WanImageToVideoPipeline

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available; this worker needs a GPU runtime")
    pipe = WanImageToVideoPipeline.from_pretrained(
        WAN_I2V.repo_id,
        revision=WAN_I2V.revision,
        torch_dtype=torch.bfloat16,
    ).to("cuda")
    pipe.set_progress_bar_config(disable=True)
    return pipe


def make_first_frame(illustration_path: Path, target: Path) -> float:
    """Crop the square illustration to the clip aspect ratio and resize it.

    The crop is a centre crop to the clip's shape followed by a resize. It runs
    on the CPU, but it runs on the GPU machine, so it is billed at the GPU
    price and is counted in the per asset time.
    """
    from PIL import Image

    started = time.perf_counter()
    target_width, target_height = VIDEO_SETTINGS.width, VIDEO_SETTINGS.height
    with Image.open(illustration_path) as image:
        image = image.convert("RGB")
        source_ratio = image.width / image.height
        target_ratio = target_width / target_height
        if source_ratio > target_ratio:
            new_width = int(round(image.height * target_ratio))
            left = (image.width - new_width) // 2
            image = image.crop((left, 0, left + new_width, image.height))
        else:
            new_height = int(round(image.width / target_ratio))
            top = (image.height - new_height) // 2
            image = image.crop((0, top, image.width, top + new_height))
        image = image.resize((target_width, target_height), Image.LANCZOS)
        image.save(target, format="PNG")
    return time.perf_counter() - started


def stage_copy(source: Path, target: Path) -> None:
    """Copy a finished file into place.

    Object storage mounts do not support the seeking writes that MP4 and WAV
    writers do, so those files are written to local disk first and copied over
    once they are complete.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def run(
    records_path: str | Path,
    out_dir: str | Path,
    limit: int = 10,
    steps: tuple[str, ...] = STEPS,
    gpu: str = H100.gpu,
    region: str = H100.region,
    platform: str = H100.platform,
    preset: str = H100.preset,
    billing: str = "preemptible",
    run_id: str = "",
) -> dict[str, Any]:
    """Run the pipeline and write the metrics."""
    records = load_records(records_path)[:limit]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    provenance = metrics_mod.new_provenance(
        source=metrics_mod.OWN_RUN,
        measured_by="Cavin Otieno",
        measured_at=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        license="MIT",
        url="",
        note=(
            "Measured by scripts/run_job.sh on Nebius Serverless AI. The startup is "
            "filled in afterwards with 'mediagen annotate-startup'."
        ),
    )
    document = metrics_mod.new_metrics(
        mode="job",
        gpu=gpu,
        region=region,
        platform=platform,
        preset=preset,
        billing=billing,
        config={
            "illustration_model": SANA.pinned_id,
            "clip_model": WAN_I2V.pinned_id,
            "image": {
                "width": IMAGE_SETTINGS.width,
                "height": IMAGE_SETTINGS.height,
                "num_inference_steps": IMAGE_SETTINGS.num_inference_steps,
                "guidance_scale": IMAGE_SETTINGS.guidance_scale,
            },
            "video": {
                "width": VIDEO_SETTINGS.width,
                "height": VIDEO_SETTINGS.height,
                "num_frames": VIDEO_SETTINGS.num_frames,
                "fps": VIDEO_SETTINGS.fps,
                "video_seconds": VIDEO_SETTINGS.video_seconds,
                "num_inference_steps": VIDEO_SETTINGS.num_inference_steps,
            },
            "records": str(records_path),
            "run_id": run_id,
        },
        provenance=provenance,
    )
    for step in steps:
        document["steps"][step] = metrics_mod.new_step()

    document["started_at"] = _now()
    started = time.perf_counter()
    print(f"records: {len(records)} from {records_path}", flush=True)
    print(f"out: {out}", flush=True)

    try:
        import torch

        document["env"] = {
            "driver": torch.version.cuda,
            "torch": torch.__version__,
            "gpu": gpu,
        }
    except Exception as exc:  # pragma: no cover - torch is absent off-GPU
        document["env"] = {"error": repr(exc)}

    try:
        if "illustration" in steps:
            _run_illustration_stage(records, out, document)
        if "first_frame" in steps:
            _run_first_frame_stage(records, out, document)
        if "clip" in steps:
            _run_clip_stage(records, out, document)
        document["status"] = "completed"
    except Exception as exc:
        document["status"] = "failed"
        document["error"] = repr(exc)
        raise
    finally:
        document["finished_at"] = _now()
        document["runtime_s"] = round(time.perf_counter() - started, 3)
        metrics_mod.save_metrics(document, out / "metrics.json")

    print(f"done: {out} (metrics: {out / 'metrics.json'})", flush=True)
    return document


def _run_illustration_stage(
    records: list[Origin], out: Path, document: dict[str, Any]
) -> None:
    import torch

    step = document["steps"]["illustration"]
    load_started = time.perf_counter()
    pipe = load_sana_pipeline()
    step["load_s"] = round(time.perf_counter() - load_started, 3)
    print(f"illustration model loaded in {step['load_s']} s", flush=True)

    for record in records:
        folder = out / "cards" / record.id
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / "illustration.png"
        started = time.perf_counter()
        generator = torch.Generator(device="cuda").manual_seed(record.seed)
        image = pipe(
            prompt=record.image_prompt,
            width=IMAGE_SETTINGS.width,
            height=IMAGE_SETTINGS.height,
            num_inference_steps=IMAGE_SETTINGS.num_inference_steps,
            guidance_scale=IMAGE_SETTINGS.guidance_scale,
            generator=generator,
        ).images[0]
        image.save(target)
        _record_step(step, record.id, time.perf_counter() - started)
        document["assets"].append(
            {
                "id": record.id,
                "file": str(target.relative_to(out)),
                "bytes": target.stat().st_size,
                "sha256": _sha256(target),
            }
        )
        print(f"illustration {record.id} {step['latency_s'][record.id]} s", flush=True)

    del pipe
    torch.cuda.empty_cache()


def _run_first_frame_stage(
    records: list[Origin], out: Path, document: dict[str, Any]
) -> None:
    step = document["steps"]["first_frame"]
    for record in records:
        folder = out / "cards" / record.id
        source = folder / "illustration.png"
        if not source.is_file():
            raise FileNotFoundError(f"missing illustration for {record.id}")
        target = folder / "first_frame.png"
        seconds = make_first_frame(source, target)
        _record_step(step, record.id, seconds)
    print(f"first frame: {step['median_s']} s median", flush=True)


def _run_clip_stage(
    records: list[Origin], out: Path, document: dict[str, Any]
) -> None:
    import torch

    step = document["steps"]["clip"]
    load_started = time.perf_counter()
    pipe = load_wan_pipeline()
    step["load_s"] = round(time.perf_counter() - load_started, 3)
    print(f"clip model loaded in {step['load_s']} s", flush=True)

    for record in records:
        folder = out / "cards" / record.id
        first_frame = folder / "first_frame.png"
        if not first_frame.is_file():
            raise FileNotFoundError(f"missing first frame for {record.id}")
        target = folder / "clip.mp4"
        started = time.perf_counter()
        result = pipe(
            prompt=record.motion_prompt,
            image=first_frame,
            width=VIDEO_SETTINGS.width,
            height=VIDEO_SETTINGS.height,
            num_frames=VIDEO_SETTINGS.num_frames,
            num_inference_steps=VIDEO_SETTINGS.num_inference_steps,
            guidance_scale=VIDEO_SETTINGS.guidance_scale,
            guidance_scale_2=VIDEO_SETTINGS.guidance_scale_2,
            generator=torch.Generator(device="cuda").manual_seed(record.seed),
        )
        frames = result.frames[0]
        staged = out / "cards" / record.id / "clip.staged.mp4"
        _export_video(frames, staged, VIDEO_SETTINGS.fps)
        stage_copy(staged, target)
        staged.unlink(missing_ok=True)
        _record_step(step, record.id, time.perf_counter() - started)
        document["assets"].append(
            {
                "id": record.id,
                "file": str(target.relative_to(out)),
                "bytes": target.stat().st_size,
                "sha256": _sha256(target),
            }
        )
        print(f"clip {record.id} {step['latency_s'][record.id]} s", flush=True)

    del pipe
    torch.cuda.empty_cache()


def _export_video(frames, path: Path, fps: int) -> None:
    """Write the frames to an MP4 file."""
    import numpy as np
    from diffusers.utils import export_to_video

    export_to_video(frames, str(path), fps=fps)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mediagen-worker",
        description="Generate ten living origin cards in one GPU run.",
    )
    parser.add_argument("--records", required=True, help="path to the origins CSV")
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument("--n", type=int, default=10, help="how many records to process")
    parser.add_argument(
        "--step",
        default="all",
        help="comma separated subset of: illustration, first_frame, clip",
    )
    parser.add_argument("--gpu", default=H100.gpu)
    parser.add_argument("--region", default=H100.region)
    parser.add_argument("--platform", default=H100.platform)
    parser.add_argument("--preset", default=H100.preset)
    parser.add_argument("--billing", default="preemptible")
    parser.add_argument("--run-id", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    steps = STEPS if args.step == "all" else tuple(
        part.strip() for part in args.step.split(",") if part.strip()
    )
    unknown = [step for step in steps if step not in STEPS]
    if unknown:
        raise SystemExit(f"unknown steps: {', '.join(unknown)}")
    run(
        records_path=args.records,
        out_dir=args.out,
        limit=args.n,
        steps=steps,
        gpu=args.gpu,
        region=args.region,
        platform=args.platform,
        preset=args.preset,
        billing=args.billing,
        run_id=args.run_id,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
