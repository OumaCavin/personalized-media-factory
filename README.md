# Living Origin Cards

Batch generative media on serverless GPUs, with the unit economics attached.

Ten Kenyan coffee origins go in. Ten animated origin cards come out, plus a
cost model that says what one card costs, what 1,000 cards cost, and from how
many cards it is cheaper to rent a GPU than to pay per call.

This is the Module 1 deliverable for **Production AI Agents for Generative
Media** (DataTalks.Club and Nebius). It is built to grow: Module 2 adds an
agent loop, Module 3 adds batch scale, Module 4 adds evaluation and tracing.

Picking this up for the first time? Start with the
[Module 1 walkthrough](docs/module-1-walkthrough.md). It turns the course's
Module 1 README, its Setup section and the capstone proposal template into the
concrete steps for this repository, and it covers the two things the course
team added by email on 23 November 2026: redeeming the Nebius credits, and
running Homework 1 on your own GPU instead of on Nebius.

---

## The idea

A specialty roaster sells origin, not just coffee. The origin story is the
product: which county, which varietal, what it tastes like, and a picture of
the place the cherry grew. A small roaster can draw one origin card by hand.
It cannot draw two hundred.

So: a record per origin, an illustration of that origin's landscape, and five
seconds of that illustration coming alive, as a silent loop for social. The
illustration is drawn with **Sana**; the animation is **Wan2.2 image-to-video**.
Both run in one batch on one GPU.

The question this repository answers is not "can it make a card". It is
**"what does one card cost, and when is renting a GPU better than paying per
call?"**

## Results at a glance

One run of ten origins, one H100, one Job. Measured times from the course's
published reference run, projected at the published prices.

| | |
| --- | --- |
| Model | Wan2.2-I2V-A14B (image to video), fed by a Sana illustration |
| Run on | Nebius Serverless AI **Job**, one NVIDIA H100 80GB |
| Median generation time per asset | **76.7 s** |
| Marginal compute cost per asset, `c` | **$0.0958** at the H100 regular price of $4.50/GPU-hour |
| Fixed cost per run, `F` | **$1.5046** (157.7 s startup + 1,046.0 s of weight loading) |
| Per call API compared | **fal.ai**, same model, **$0.2025** per 480p clip |
| Self host breakeven | **15 assets per run** at the regular price, 5 at the spot snapshot |

A spot price is a moving target: the H100 in eu-north1 was $0.79 per GPU hour
at 04:11 UTC on 23 November 2026 and $2.37 at 20:57 UTC the same day, and the
breakeven moved from 2 assets per run to 6 over that window with no change to
the model, the code or the run. Quote the price of the region you actually
used, and date it. `mediagen spot-price` reads the live price and prints what
it does to this run.

Cost of one asset as the batch grows:

| Assets per run | 1 | 10 | 100 | 1,000 |
| --- | ---: | ---: | ---: | ---: |
| Cost per asset | $1.6004 | $0.2463 | $0.1109 | $0.0973 |

At N = 10 the fixed part is 84% of the bill. At N = 1,000 it is 3%. The
optimisation target inverts between those two points, which is the single most
useful thing this repository teaches.

Full derivation, sources and caveats: [docs/cost-model.md](docs/cost-model.md).
Copy-paste answers for the homework form, with a table mapping every question
of the course's homework instructions and of the submission form onto the
place this repository answers it: [docs/module-1-homework.md](docs/module-1-homework.md).
Step-by-step for the course's own instructions: [docs/module-1-walkthrough.md](docs/module-1-walkthrough.md).

## How it runs

```text
data/origins.csv
        |
        v
  +-------------------------------------------+
  |  Nebius Serverless AI Job, one H100      |
  |                                           |
  |  1. illustration  Sana        512x512    |  GPU   ~0.8 s each
  |  2. first frame   Pillow      832x480    |  CPU   ~0.4 s each
  |  3. clip          Wan2.2 I2V  832x480    |  GPU  ~76.7 s each
  |            81 frames at 16 fps = 5.06 s   |
  +-------------------------------------------+
        |
        v
  /data/runs/<run id>/cards/<origin id>/{illustration.png,first_frame.png,clip.mp4}
  /data/runs/<run id>/metrics.json   <- every second spent, and where it came from
```

A Job, not an Endpoint. Nobody waits for any single card, so there is no reason
to keep a server warm, and a Job stops billing the moment the batch is done.

## Repository layout

```text
src/mediagen/          the package
  specs.py              pinned models, GPU platforms and generation settings
  records.py            the ten origins and the prompts built from them
  worker.py             the GPU worker that runs inside the Job
  metrics.py            the metrics schema and the provenance rules
  costs.py              the fixed and marginal cost model
  spotprice.py          the live preemptible prices, read from the public API
  cli.py                plan, analyze, report, compare, spot-price, verify
data/
  origins.csv           the ten records
  reference_runs/       published course measurements, with provenance sidecars
  prices/               dated price snapshots for GPUs and per call APIs
  house-rules.json      the rules 'mediagen verify' checks the repository against
docker/                 the worker image
scripts/                build the image, run the Job, re-derive the numbers
tests/                  45 tests, including cross checks against published results
docs/
  module-1-walkthrough.md   the course instructions as concrete steps
  module-1-homework.md      the answers, with provenance, and the mapping
                            from each question to where it is answered
  cost-model.md             the F/N + c derivation, sources and caveats
  capstone-proposal.md      the Module 1 capstone proposal
  learning-in-public.md     post drafts and the seven links to collect
```

## Running it

The parts that need a GPU need a GPU. The parts that explain the money do not,
and they are the ones worth running first.

```bash
# 1. See the ten records and the prompts they turn into. No GPU, no account.
python -m mediagen plan

# 2. Read the live preemptible price for a platform and region.
python -m mediagen spot-price --platform gpu-h100-sxm --region eu-north1

# 3. Re-derive every number in docs/ from the data files.
./scripts/analyze.sh

# 4. Check the repository against its own house rules.
python -m mediagen verify
```

To make the assets for real:

```bash
# Build and push the worker image. The Job can only pull from a registry.
PUSH=1 REGISTRY=<your docker hub user> ./scripts/build_image.sh

# Run it as one Job on Nebius Serverless AI.
export WORKER_IMAGE=<your docker hub user>/living-origin-cards:0.1.0
export BUCKET=<your object storage bucket>
DRY_RUN=0 ./scripts/run_job.sh

# Fill in the machine startup from the Job metadata. The worker cannot see it:
# the worker is inside the container and the Job is outside it.
nebius ai job get <job id>
python -m mediagen annotate-startup --metrics <metrics.json> \
  --created-at <created_at> --started-at <started_at>

# Now every number above is your own.
python -m mediagen analyze --metrics <metrics.json>
```

## The cost model in one box

```text
cost of one asset in a run of N assets  =  F / N  +  c

F  = (startup + model load) x price per second      paid once per run
c  = median generation time x price per second       paid once per asset

breakeven N  =  ceil( F / (p - c) )      p = the per call API price per asset
```

If `p <= c` there is no breakeven: the API is cheaper per asset than it costs
to generate one, and no batch size fixes that. The convention here is `0`.

## Provenance

Every metrics file says where it came from, and the analysis refuses to
pretend otherwise.

- `own-run` — measured by this project. Numbers are yours to quote.
- `course-reference-run` — measured by the course authors and published under
  the MIT licence. Used here because the environment this repository was
  authored in had no GPU and no Nebius account.

`mediagen analyze` prints a warning for anything that is not an `own-run`, and
`docs/` states the provenance of every figure it quotes. Running
`scripts/run_job.sh` replaces the reference data with your own measurements and
no code change.

## Status

| Module | Topic | State |
| --- | --- | --- |
| 1 | Make it work | done: pipeline, measurements, cost model, homework answers |
| 2 | Make it intelligent | next: agent loop, judge, retries |
| 3 | Make it scale | planned: batch size, spot capacity, checkpointing |
| 4 | Make it production ready | planned: evaluation, tracing, runbooks |

## Licence

MIT, Copyright (c) 2026 Cavin Otieno. See [LICENSE](LICENSE).

The measurement files under `data/reference_runs/` are MIT licensed, Copyright
(c) 2026 Nebius and DataTalks.Club, copied from the course repository at the
pinned commit `b417a3f5`. See
[data/reference_runs/README.md](data/reference_runs/README.md).

Model weights are Apache-2.0 (Sana, with the Gemma terms for its text encoder;
Wan2.2). The application links to each model's own licence.
