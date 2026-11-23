# The cost model

How much does one animated origin card cost, and when is it cheaper to rent a
GPU than to pay a per call API? This document is the whole derivation. Every
figure in it is produced by `scripts/analyze.sh` from the files in `data/`, and
the test suite checks the engine against published results before it is used
for anything new.

## The shape of the problem

A run has two kinds of cost and they behave completely differently.

```text
cost of one asset in a run of N assets  =  F / N  +  c
```

`F` is the fixed part, paid once per run: the machine starts, the container is
pulled, the model weights are downloaded and loaded. It does not care how many
assets the run makes, so spread over `N` assets it contributes `F / N` to each
one.

`c` is the marginal part, paid once per asset: the generation itself. It is the
same for asset 1 and asset 10,000.

Three things get confused with each other, so they are worth naming:

| Term | What it actually is | Measured as |
| --- | --- | --- |
| Startup | Creating the Job until the container is running | Job `created_at` to `started_at` |
| Load | Getting the weights into GPU memory | wall clock around `from_pretrained` |
| Readiness | The server answering requests | `GET /v1/models` returning a model list |

Startup is not visible to the worker: the worker is inside the container and
the Job is outside it. It is measured from the Job metadata afterwards and
added to the run with `mediagen annotate-startup`. In this project it is
**157.7 s**, measured by the course authors on one H100 Job on 2026-11-14 and
used for every GPU in the course's own cost tables.

## The numbers for one run

Ten origins, one H100, one Job. The clip stage is the asset, because it is
what the per call API also sells.

| Quantity | Value | Where it comes from |
| --- | ---: | --- |
| Startup | 157.7 s | `data/reference_runs/course_startup_h100_2026-11-14.json` |
| Clip model load | 1,045.976 s | `course_h100_20kids_2026-11-14.json`, step `clip` |
| Median clip | 76.675 s | same file, step `clip` |
| Median illustration | 0.784 s | same file, step `illustration` |
| Median CPU step | 0.361 s | same file, step `card` |
| H100 regular price | $4.50 per GPU hour | `data/prices/nebius_2026-11-23.json` |
| H100 live spot price | $0.79 per GPU hour | same file, read 2026-11-23 04:11 UTC |
| fal.ai 480p rate | $0.04 per video second | `data/prices/per_call_api_2026-11-23.json` |
| Video length | 81 frames / 16 fps = 5.0625 s | `mediagen.specs.VIDEO_SETTINGS` |

Derived at the regular price:

```text
c = 76.675 s x $4.50 / 3600        = $0.095844 per asset
F = (157.7 + 1045.976) s x $4.50 / 3600 = $1.504595 per run
```

| Assets per run | 1 | 10 | 100 | 1,000 |
| --- | ---: | ---: | ---: | ---: |
| Cost per asset | $1.6004 | $0.2463 | $0.1109 | $0.0973 |
| Fixed part as a share | 94% | 61% | 13% | 1.5% |

The shape of that curve is the lesson. At N = 10 the fixed part is most of the
bill and the only thing worth attacking is the weight download. At N = 1,000
the fixed part is noise and the only thing worth attacking is the generation
time. **The optimisation target inverts.** A team that spends its time making
the model faster before it has solved the download has optimised the wrong
term for its batch size.

## The breakeven against a per call API

fal.ai sells the same model at the same resolution:
`fal-ai/wan/v2.2-a14b/image-to-video`, $0.04 per video second at 480p, 16
frames counted as one second. One clip is 5.0625 video seconds, so **$0.2025
per clip**.

```text
breakeven N = ceil( F / (p - c) )
            = ceil( $1.504595 / ($0.2025 - $0.095844) )
            = ceil(14.11)
            = 15 assets per run
```

| H100 price | `c` per asset | `F` per run | Breakeven N |
| --- | ---: | ---: | ---: |
| $4.50 regular (on demand) | $0.0958 | $1.5046 | **15** |
| $2.07 spot snapshot, 2026-11-14 | $0.0441 | $0.6921 | **5** |
| $0.79 live spot price, 2026-11-23 | $0.0168 | $0.2641 | **2** |

Two things fall out of that table, and both are counter-intuitive.

**The breakeven is set by `F`, not by `c`.** Moving from the regular price to
the spot price cuts `F` by 54%, and the breakeven falls from 15 to 5, because
the API price and the marginal cost barely move relative to the fixed part.
Making the model twice as fast halves `c`, but `c` is only 19% of `p`, so the
breakeven barely moves. **Caching the weights moves it a lot; a faster model
does not.**

**The same workload has three defensible answers.** The breakeven is not a
property of the model, it is a property of the model at a price at a batch
size. Spot prices are dynamic, they can change every 15 minutes, and they are
not capped above the regular price, so any published breakeven is a projection
against a dated snapshot. Use regular prices to compare and plan, and Billing
to Usage to find out what a run actually cost.

## Cross-checks

The engine was checked against results the course published, on three different
GPUs, before being used for anything here.

| GPU | Regular price | Median clip | Breakeven, this engine | Breakeven, published |
| --- | ---: | ---: | ---: | ---: |
| H100 | $4.50 | 76.7 s | 15 | 15 |
| H200 | $5.40 | 74.6 s | 12 | 12 |
| RTX PRO 6000 | $1.80 | 123.6 s | 3 | 3 |

It also reproduces the published $0.10 per clip at N = 200 on an H100, and the
published run cost of about $2.60 for ten cards at the regular price and about
$1.20 at the spot snapshot. These are in `tests/test_costs.py`, and they run on
a laptop in under a second.

## The same work on three GPUs

Cost per asset is price times time, so the cheapest GPU is not the fastest one.

| GPU | Price/h | Median clip | Load | `c` per asset | `F` per run | Cost at N = 20 | Breakeven N |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| H100 | $4.50 | 76.7 s | 1,046.0 s | $0.0958 | $1.5046 | $0.1711 | 15 |
| H200 | $5.40 | 74.6 s | 533.9 s | $0.1119 | $1.0373 | $0.1637 | 12 |
| RTX PRO 6000 | $1.80 | 123.6 s | 531.3 s | $0.0618 | $0.3445 | $0.0790 | 3 |

The RTX PRO 6000 is 1.6x slower per clip than the H100 and 2.5x cheaper per
hour, so its clip is 54% cheaper at N = 20, and it breaks even three times
faster. The H200 is the fastest per clip and the most expensive per hour, and
it is beaten at small batches. Its advantage only shows up at large batches,
where the fixed part stops mattering and the marginal cost decides.

Reproduce it:

```bash
python -m mediagen compare \
  --runs gpu-h100-sxm=data/reference_runs/course_h100_20kids_2026-11-14.json \
  --runs gpu-h200-sxm=data/reference_runs/course_h200_20kids_2026-11-14.json \
  --runs gpu-rtx6000-a=data/reference_runs/course_rtxpro6000_20kids_2026-11-14.json \
  --startup-s 157.7
```

## What the projection leaves out

Every number above is a projection from measured times and a published price.
What a run actually cost is in Billing to Usage. The gaps are:

- **The container disk.** It bills alongside the GPU. A 500 GB disk is about
  $0.05 per hour, around 1% of an H100 at the regular price.
- **The warm up.** The first asset of each model is several times slower than
  the rest. It is paid once per run, and it is one reason the median is the
  right statistic for the per asset time.
- **Everything around the run.** Failed runs, retries, engineering time, bucket
  storage and egress, and the difference in quality against an API. Each of
  these makes self hosting look cheaper than it is.
- **Interruption.** A preemptible Job that is preempted ends in `ERROR` and is
  not retried. The rerun pays the startup and the 1,046 s weight load again,
  and starts again from the first origin.
- **Spot prices move.** A projection against a snapshot is not a prediction of
  what the run paid, and a spot price can rise above the regular price during
  a run unless a pricing policy caps it.

## The prices, and where they come from

| Source | Read | Used for |
| --- | --- | --- |
| [Compute pricing](https://docs.nebius.com/compute/resources/pricing) | 2026-11-23 | H100 $4.50, L40S $1.35 on demand; H100 spot from $0.79; L40S preemptible flat $0.65 |
| [Nebius price list](https://nebius.com/prices) | 2026-11-23 | cross check |
| [Spot price API](https://api.nebius.cloud/billing/v1alpha1/spot-price) | 2026-11-23 04:11 UTC | live H100 spot price, $0.79 |
| [fal.ai model page](https://fal.ai/models/fal-ai/wan/v2.2-a14b/image-to-video) | 2026-11-23 | $0.04 per video second at 480p |
| [fal.ai pricing](https://fal.ai/pricing) | 2026-11-23 | $0.001 per megapixel for Sana, $0.005 for Z-Image-Turbo, $0.003 for FLUX.1 schnell |
| [Replicate pricing](https://replicate.com/pricing) | 2026-11-23 | $0.025 for FLUX.1 dev, $0.04 for FLUX1.1 pro, $3.00 per 1,000 for schnell |

**One conflict worth recording.** Nebius publishes the L40S on demand price
twice: $1.35 in the per platform compute pricing table and "from $1.55" on the
marketing price list. The per platform table is used here because it names
each platform and its CPU and RAM components, while the marketing list quotes
the cheapest configuration in a family and carries no date. The same split
appears in the preemptible rate: $0.65 against "from $0.74". The H100 and H200
agree on both pages.

Billing granularity: one second, priced per hour, so a run is charged for
exactly the seconds it used.

## The other comparison worth having

The illustration stage is a second, smaller comparison. fal.ai sells Sana at
$0.001 per megapixel, which at 512x512 is a fraction of a cent per image.
Self hosting that stage on an H100 costs about $0.0010 per image in marginal
terms alone, so the per call API is already at or below the marginal cost of
generating it.

This is worth stating plainly rather than hiding: **for this one stage, the
per call API is simply the better deal, and self hosting it is not a cost
saving.** The pipeline still draws its own illustrations because the clip needs
a specific first frame, because the illustration and the clip have to match,
and because producing ten of them inside one run shares a single weight
download. Whether that sharing pays for itself is exactly what the breakeven
calculation answers.

## Reproducing everything here

```bash
./scripts/analyze.sh                 # regenerate docs/homework-answers.generated.md
python -m mediagen analyze           # the clip stage at the regular price
python -m mediagen analyze --price-per-hour 0.79
python -m mediagen compare --runs ... # the GPU table
python -m pytest tests -q            # 28 tests, including the cross checks
```
