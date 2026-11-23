# Module 1 walkthrough

The course's Module 1 README, its Setup section and the capstone proposal
template are the canonical instructions. This document is the translation of
those instructions into steps that work in this repository, plus the two
instructions the course team added by email on 23 November 2026: how to redeem
the Nebius credits, and what to do if you ran Homework 1 on your own GPU.

Read this once before you start. It is deliberately ordered the way you will
work, and every step says which artefact in this repository it produces.

## What this guide adds to the course materials

The course documents are complete for someone who follows the lessons in
order. Three things were still open when this repository was written, and
this guide closes them.

The first is the gap between the course's setup and the concrete decisions
this repository makes: which region, which platform, which image, which
command. The course assumes eu-north1 and the reference H100 run; a project in
another region has to work that out from live prices.

The second is the provenance of every number. The timings committed here are
the course's published measurements, not a run of your own, and the repository
is built so that swapping in your own run changes nothing but the data.

The third is the two instructions from the course team's email on 23 November
2026, which are not in the lesson files: the credit redemption path and the
own-GPU path.

## Course access and Nebius credits

Course approval and Nebius credits are two separate things, and the second one
sends two emails.

Approval of the course application unlocks homework and project submissions
on the platform. The Nebius account is independent: you apply to the
[AI Builder Program](https://dev.nebius.com/builders) separately, and being
approved for the course does not approve the Builder Program application.

After the Builder Program welcome email, the promo codes arrive in **separate
emails**: an **AI Cloud** code and a **Token Factory** code. They can arrive at
different times, sometimes a day apart.

- **AI Cloud code** is the one for this module. It pays for GPU Jobs and
  Endpoints, which is everything in Module 1.
- **Token Factory code** is for LLM API usage. Module 1 does not use it.

Redeem the AI Cloud code like this:

1. Open the AI Cloud promo code email and follow its setup instructions.
   Setting up your account creates a tenant and a project in the
   [Nebius console](https://console.nebius.com/).
2. In the console, go to **Manage -> Billing -> Payments**.
3. Select **Apply promo code**.
4. In the **Top up balance** dialog, choose **With promo code**, paste the
   code, and select **Apply promo code**.
5. Check **Billing -> Transactions** to confirm the credit landed.

**You do not need a bank card for the course code.** If the console asks for
one, go back to the AI Cloud email and look for the **With promo code**
option in the Top up balance dialog. If you already added a card, Nebius adds
the $25 it charges to your AI Cloud balance, which is in the transactions list
and usable for GPU workloads.

If something is wrong:

| Situation | What to do |
| --- | --- |
| Welcome email arrived, but a code is missing | Count two days from the welcome email. If the AI Cloud or Token Factory code is still missing, DM Mikhail Rozhkov in the course Slack with the email address you applied with and which code is missing |
| Builder Program application was rejected, or you got credit through an earlier event | DM Mikhail with your application email and the context, so the team can check your case |
| The code was rejected in Billing | Check which product the email names. AI Cloud and Token Factory use separate codes and separate balances. If the AI Cloud code itself fails, send the error message in the DM without sharing the code |
| You already applied and it is still under review | Do not apply again. A second application can be flagged as a duplicate |

The Slack channel is `#course-ai-mediagen`
([C0CEG1BUDKL](https://app.slack.com/client/T01ATQK62F8/C0CEG1BUDKL)) in the
workspace `T01ATQK62F8`.

## Region and platform

This is the decision the course leaves open, and it is the one that most
changes the numbers.

The console in the screenshot shows a project called
`default-project-eu-west2`. The course's own reference measurements were taken
in **eu-north1** on an H100, and the course materials identify eu-north1 as
the region offering the L40S Intel option used in the examples. Spot prices
are published **per region**, and a platform only appears in the price list
when there is preemptible capacity for it, so an absent platform is a capacity
signal rather than a missing price.

Two facts constrain the choice for this pipeline.

Wan2.2-I2V-A14B asks for at least 80 GB of VRAM, so the clip model runs on an
H100 or an H200 and never on an L40S. Sana alone would fit an L40S, but the
asset in this pipeline is the clip.

Spot prices move. On 23 November 2026 the H100 in eu-north1 was $0.79 per
GPU hour at 04:11 UTC and $2.37 at 20:57 UTC, a factor of three inside one
day, with no change to the model, the code or the run. Over that window the
breakeven against the fal.ai price moved from 2 assets per run to 6.

So read the price before you commit, and quote the price of the region you
actually ran in. The course team asks for exactly that: use the rate for the
Nebius GPU and region you used to project the cost per asset at 1,000 assets.

```bash
# every preemptible price right now
python -m mediagen spot-price

# one platform, and what it does to this run
python -m mediagen spot-price --platform gpu-h100-sxm --region eu-north1 \
  --metrics data/reference_runs/course_h100_20kids_2026-11-14.json --n 10
```

The command prints the live price, the effective timestamp, every region that
currently publishes a price for that platform, and the projected run cost and
breakeven at that price. If the table comes back empty, there is no
preemptible capacity for that platform in that region right now: pick another
region, pick the on-demand price, or check the **Capacity dashboard** in the
console before starting a run.

To run somewhere other than the default, set the environment variables that
`scripts/run_job.sh` reads:

| Variable | Default | Notes |
| --- | --- | --- |
| `PLATFORM` | `gpu-h100-sxm` | The GPU type. Wan2.2 needs 80 GB, so H100 or H200 |
| `PRESET` | `1gpu-16vcpu-200gb` | vCPU and memory for the VM |
| `REGION` | `eu-north1` | Where the reference measurements were taken |
| `PRICE_MODE` | `preemptible` | `preemptible` or `on-demand` |
| `DISK_SIZE` | `500Gi` | The weights are about 126 GB and a bigger disk writes faster |
| `TIMEOUT` | `2h` | Ten origins take about 35 minutes on one H100 |

```bash
REGION=eu-west1 PLATFORM=gpu-h200-sxm PRESET=1gpu-16vcpu-200gb \
  DRY_RUN=0 ./scripts/run_job.sh
```

If you switch region, expect the startup and load times to differ from the
reference run. The 157.7 s startup and the 1,046 s weight download were
measured in eu-north1, and download speed to the region is part of both.

## Repository setup

The course's setup steps 4 and 5 are: clone the course repository, install
`uv`, and start Jupyter from the repository root. That path is for the
lessons and the notebooks.

For this repository the Job path does not need Jupyter or a notebook kernel.
The worker runs inside the container, and the analysis runs anywhere. What you
need locally is Python 3.10 or newer, and Docker for the image build.

```bash
git clone https://github.com/OumaCavin/personalized-media-factory.git
cd personalized-media-factory

# look at the ten records and the prompts they become
python -m mediagen plan

# check the repository against its own house rules
python -m mediagen verify
```

Install the package into a virtual environment if you prefer, so `mediagen`
is on the path rather than `python -m mediagen`:

```bash
uv venv && uv pip install -e ".[dev]"
mediagen plan
```

The one thing the course's Setup needs you to have that this does not replace
is Docker. The course FAQ is explicit that Docker is used to build the
container for Module 1.

## Container image and registry

A Job can only pull an image from a registry, so a local build is not enough.

```bash
# build only
IMAGE=living-origin-cards:0.1.0 ./scripts/build_image.sh

# build and push
PUSH=1 REGISTRY=<your docker hub user> ./scripts/build_image.sh
```

Build for `linux/amd64`, which the script does by default. A Job that fails
right after `IMAGE_PULLING` is usually the wrong architecture or a private
image that the platform cannot pull.

If you use the Nebius Container Registry instead of Docker Hub, push there
and set the registry credentials on the Job with `--registry-username` and
`--registry-password`.

## Object storage bucket

The worker writes its output through a bucket mounted at `/data`. It never
uploads anything itself; it writes ordinary files into the mounted folder.

```bash
nebius storage bucket create --name <your-bucket>

aws s3 cp data/origins.csv s3://<your-bucket>/inputs/origins.csv \
  --endpoint-url https://storage.eu-north1.nebius.cloud
```

The storage endpoint follows the region: `https://storage.eu-west2.nebius.cloud`
for an eu-west2 bucket. The access key goes in the AWS CLI configuration; it
never goes in the repository or in a chat.

## Running the batch

The launcher validates the request without creating anything first, which is
worth the ten seconds it saves.

```bash
export WORKER_IMAGE=<your docker hub user>/living-origin-cards:0.1.0
export BUCKET=<your-bucket>
export RUN_ID=job-001

# dry run by default: prints the request, creates nothing
./scripts/run_job.sh

# create it for real
DRY_RUN=0 ./scripts/run_job.sh
```

Watch it:

```bash
nebius ai job get <job id>
nebius ai job logs <job id> --follow
```

The Job ends by itself. Its lifecycle is
`PROVISIONING -> STARTING -> IMAGE_PULLING -> RUNNING -> COMPLETED`, and a
preempted Job ends in `ERROR` instead and is not retried. A preempted run
pays the startup and the weight download again and starts again from the first
origin, so record the Job's `created_at` and `started_at` before you lose
them:

```bash
python -m mediagen annotate-startup --metrics <metrics.json> \
  --created-at "2026-11-23T18:00:00Z" --started-at "2026-11-23T18:02:38Z"
```

The startup is the time between creating a Job and the container running. The
worker cannot measure it, because the worker is inside the container and the
Job is outside it.

## Measuring the cost

Once the run has finished, the numbers come out of the data, not out of prose:

```bash
python -m mediagen analyze                 # cost table and breakeven
python -m mediagen report                  # the homework answers, generated
python -m mediagen compare --runs ...      # the same step on several GPUs
./scripts/analyze.sh                       # regenerate the generated answers file
```

Each of these takes a `--metrics` path. Point them at your own metrics file
and the whole document set is re-derived from your run.

The three quantities to be able to explain are the marginal cost `c` (the
price of one more asset), the fixed cost `F` (the startup and the weight
download, paid once per run), and the breakeven `ceil(F / (p - c))` against
the per call API price. [cost-model.md](cost-model.md) derives all three.

## Submitting the homework

The form is at
[courses.datatalks.club](https://courses.datatalks.club/production-ai-agents-generative-media/homework/module1)
and the deadline is 1 December 2026 at 02:59 in your account timezone. The
form does not accept late homework once it closes.

| Form field | Where the answer comes from |
| --- | --- |
| Homework URL | This repository: <https://github.com/OumaCavin/personalized-media-factory> |
| Learning in public links | Up to seven. Drafts for three channels are in [learning-in-public.md](learning-in-public.md), and the last section lists the seven links worth posting as they happen |
| Time spent on lectures | Your own number. The course asks for hours, not an estimate of theirs |
| Time spent on homework | Your own number |
| FAQ contribution PR or issue URL | The questions for this course live in `_questions/production-ai-agents-generative-media/` in [DataTalksClub/faq](https://github.com/DataTalksClub/faq/tree/main/_questions/production-ai-agents-generative-media). Contribute there |

Note on the FAQ link: issue 281 in that repository is a question about the
number of results in a hybrid search setup, in the llm-zoomcamp course,
opened by another user and closed. It is not a contribution to this course's
FAQ, and linking it will read as though it is.

The eight answers themselves are in
[module-1-homework.md](module-1-homework.md), with the numbers generated rather
than typed.

## Running on your own GPU

The course team wrote on 23 November 2026: local runs are accepted. State that
you ran it locally, name the GPU, and estimate the cost using the rate for a
comparable GPU in Nebius AI Cloud. The team has not yet confirmed how to
record a local run in the execution field, and asks you to follow the
[homework discussion](https://datatalks-club.slack.com/archives/C0CEG1BUDKL/p1795425054477079)
for an update.

Running it here is the same worker with a local output directory:

```bash
# needs a CUDA GPU with enough memory for the clip model
python -m mediagen.worker --records data/origins.csv --out runs/local --n 10 \
  --gpu "NVIDIA H100 80GB" --region local --platform local --preset local \
  --billing local

# or just the illustration stage, which fits in about 11 GB
python -m mediagen.worker --records data/origins.csv --out runs/local --n 10 \
  --step illustration,first_frame
```

The worker writes the same `metrics.json`, so the cost engine reads it
unchanged.

What to write in each field for a local run:

| Field | What to write |
| --- | --- |
| How did you run it | The closest option on the form, plus a sentence saying it was a local GPU and not Nebius. The form's options are Endpoint, Job, and JupyterLab on a GPU, and the team is still working out the exact wording for a local run |
| Which GPU | The name of your card |
| Median generation time per asset | Your measured median, from your own `metrics.json` |
| Marginal compute cost per asset | Your median time multiplied by the Nebius rate for a comparable GPU, not by your own electricity or rental cost. The course asks for the comparable Nebius rate |
| Per call API compared | Unchanged: fal.ai, the same model, $0.2025 per 480p clip |
| Self host breakeven N | The same formula, with your median time and the comparable Nebius rate |

Two cautions. The dollar figure for a local run is an estimate against a
published rate, not an invoice, and the form asks for exactly that. And the
startup and load times are not the same on a local machine: there is no Job
to start and no 126 GB download, so the fixed part is smaller and the
breakeven is lower than the Nebius numbers in this repository.

## Capstone proposal

The template is
[projects/proposal-template.md](https://github.com/DataTalksClub/production-ai-agents-for-media-generation/blob/main/projects/proposal-template.md)
in the course repository, and it is unchanged since the commit this
repository pins. It has five sections: problem and user, input records, GPU
media models, pipeline and quality checks, and an initial budget estimate.

A filled version is already in
[capstone-proposal.md](capstone-proposal.md), built on this repository's own
measurements: the same ten origins extended to 100 records, a deterministic
ten record sample escalated to video, and a budget computed with the cost
engine rather than estimated by hand.

Two things in the template come straight from the code rather than from
prose. The model IDs, revisions and licences in section 3 are pinned in
`src/mediagen/specs.py`, so they cannot drift between the proposal and the
container. The budget in section 5 is produced by `mediagen analyze` on the
reference run.

The capstone itself is due on 15 January 2027 and is peer reviewed against
eight rubric areas. What this repository already covers, and what the later
modules add:

| Rubric area | Covered here | Later |
| --- | --- | --- |
| System | The batch path end to end: records in, media out, on Nebius Serverless AI | The agent that orchestrates it (Module 2) |
| Agent | Nothing yet | Module 2 |
| Media | Two GPU models, image and video, with assets written to object storage | Audio as the third modality |
| Cost | A cost report with a per-asset and per-run breakdown, and the price sources dated | Per accepted asset, with retries (Module 4) |
| Reliability | The run is idempotent per record and the metrics survive a restart | Resume without redoing finished work (Module 3) |
| Observability | A metrics file per run with a provenance block | A trace per record that answers why it cost and why it took that long (Module 4) |
| Reproducibility | Pinned revisions, pinned seeds, derived prompts, dated prices | The full golden set and baselines |

The capstone needs 100 image and audio records and 10 video records, so the
records file and the budget both need to grow before 15 January. That is the
natural Module 3 job.

## Cleanup and billing

A Job stops billing when it ends. A DevLab does not: it bills its disk until
you delete it. An Endpoint bills while it is `RUNNING`, idle or not.

```bash
nebius ai job list
nebius ai endpoint list
nebius ai devlab list
```

Then check **Billing -> Usage** the next day to confirm nothing is still
billing, and delete the bucket data you no longer need. This applies to
failed runs too: a Job that ended in `ERROR` still needs checking, and a
Devlab you left running keeps charging for its disk.

## Troubleshooting

| Symptom | Cause | What to do |
| --- | --- | --- |
| The spot price table is empty for a platform | No preemptible capacity for it in that region right now | Another region, another platform, the on-demand price, or the Capacity dashboard |
| Job stuck in `PROVISIONING`, then `ERROR` with `NotEnoughResources` | No capacity in that region | Another region, `PRICE_MODE=on-demand`, or try later |
| Job ends in `ERROR` after a while | Preempted, or a spot price moved above a pricing policy cap | Run it again, and record the new startup |
| Job fails right after `IMAGE_PULLING` | Wrong architecture, or a private image it cannot pull | Build for `linux/amd64`, or pass the registry credentials |
| `QuotaExceeded` | New accounts have small quotas | One GPU, and check your quotas |
| `CUDA out of memory` in the clip stage | The clip model on a GPU with less than 80 GB | Use an H100 or an H200 |
| The Job ends before the assets are done | The weight download plus the clips exceeded the timeout | Raise `TIMEOUT` |
| `COMPLETED` but the bucket is empty | Output written outside `/data` | Check `--out` and the `--volume` mount |
| The cost numbers look wrong | The startup was never filled in | `mediagen annotate-startup` |
| The numbers say `course-reference-run` | You are still reading the reference data | Point `--metrics` at your own metrics file |

## Where each piece of this lives

| Step | Artefact |
| --- | --- |
| The ten records and their prompts | `data/origins.csv`, `src/mediagen/records.py` |
| The container | `docker/Dockerfile`, `docker/requirements.txt` |
| The Job | `scripts/run_job.sh`, `src/mediagen/worker.py` |
| The measurements | `src/mediagen/metrics.py`, the `metrics.json` the worker writes |
| The cost model | `src/mediagen/costs.py`, [cost-model.md](cost-model.md) |
| The live prices | `src/mediagen/spotprice.py`, `data/prices/` |
| The homework answers | [module-1-homework.md](module-1-homework.md), `docs/homework-answers.generated.md` |
| The capstone proposal | [capstone-proposal.md](capstone-proposal.md) |
| The learning in public drafts | [learning-in-public.md](learning-in-public.md) |
| The repository house rules | `data/house-rules.json`, `mediagen verify` |
