"""Pinned specifications: models, GPU platforms and generation settings.

Everything that changes the bytes on disk or the seconds on the clock is pinned
here on purpose. A generative media run is only reproducible when the model
revision, the resolution, the step count and the seed are all fixed, so leaving
one of them to float silently is how two runs of the same prompt end up with
different prices.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    """One model, pinned to a specific revision."""

    key: str
    repo_id: str
    revision: str
    modality: str
    license_name: str
    license_url: str
    note: str = ""

    @property
    def pinned_id(self) -> str:
        """The identifier to pass to ``from_pretrained`` so the revision is fixed."""
        return f"{self.repo_id}@{self.revision}"


SANA = ModelSpec(
    key="sana",
    repo_id="Efficient-Large-Model/Sana_1600M_1024px_diffusers",
    revision="ac0da2ff55fbe434795be0dce883042e4d49e2fc",
    modality="text-to-image",
    license_name="Apache-2.0 (the Gemma-2-2B text encoder is under the Gemma terms)",
    license_url=(
        "https://huggingface.co/Efficient-Large-Model/"
        "Sana_1600M_1024px_diffusers/blob/main/LICENSE"
    ),
    note=(
        "1648M parameters, native 1024px. Measured peak GPU memory 10.9 GB on an "
        "H100, so it also fits an L40S."
    ),
)

WAN_I2V = ModelSpec(
    key="wan2.2-i2v-a14b",
    repo_id="Wan-AI/Wan2.2-I2V-A14B-Diffusers",
    revision="596658fd9ca6b7b71d5057529bbf319ecbc61d74",
    modality="image-to-video",
    license_name="Apache-2.0",
    license_url="https://huggingface.co/Wan-AI/Wan2.2-I2V-A14B-Diffusers/blob/main/LICENSE",
    note=(
        "27B parameters in total, two experts of about 14B with 14B active per "
        "step. The model card asks for at least 80 GB of VRAM, so it needs an "
        "H100 or H200 and never fits an L40S."
    ),
)

MODELS = {model.key: model for model in (SANA, WAN_I2V)}


@dataclass(frozen=True)
class ImageSettings:
    """Settings for the illustration stage."""

    width: int = 512
    height: int = 512
    num_inference_steps: int = 20
    guidance_scale: float = 4.5
    negative_prompt: str = ""


@dataclass(frozen=True)
class VideoSettings:
    """Settings for the animation stage.

    ``num_frames`` and ``fps`` are the two numbers that decide what a per call
    API charges, because these APIs bill video seconds and count 16 frames as
    one second.
    """

    width: int = 832
    height: int = 480
    num_frames: int = 81
    fps: int = 16
    num_inference_steps: int = 20
    guidance_scale: float = 1.0
    guidance_scale_2: float = 1.0

    @property
    def video_seconds(self) -> float:
        """Length of the clip in the unit a per call API bills."""
        return self.num_frames / self.fps


IMAGE_SETTINGS = ImageSettings()
VIDEO_SETTINGS = VideoSettings()


@dataclass(frozen=True)
class GpuPlatform:
    """A Nebius Serverless AI platform, preset and region."""

    platform: str
    preset: str
    region: str
    gpu: str
    vram_gb: int


H100 = GpuPlatform(
    platform="gpu-h100-sxm",
    preset="1gpu-16vcpu-200gb",
    region="eu-north1",
    gpu="NVIDIA H100 80GB HBM3",
    vram_gb=80,
)

L40S = GpuPlatform(
    platform="gpu-l40s-a",
    preset="1gpu-8vcpu-32gb",
    region="eu-north1",
    gpu="NVIDIA L40S",
    vram_gb=48,
)

GPU_PLATFORMS = {gpu.platform: gpu for gpu in (H100, L40S)}

#: The modality of the asset this pipeline produces. The illustration stage is
#: an intermediate image: it is the first frame that the clip animates, and the
#: clip is what gets delivered.
ASSET_MODALITY = "Video (image to video)"

#: The modality of the intermediate frame.
INTERMEDIATE_MODALITY = "Image (text to image)"

#: Disk size for the worker container. The Wan weights alone are about 126 GB,
#: and a larger disk writes faster, so the download finishes sooner.
CONTAINER_DISK_SIZE = "500Gi"

#: Hard stop for the Job. Ten origins take about 35 minutes on one H100.
JOB_TIMEOUT = "2h"
