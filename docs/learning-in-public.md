# Learning in public

The course asks for a short post about the asset and the idea behind it, with
`@DataTalksClub` and `@Nebius` tagged. Drafts for three channels.

Everything published should carry the provenance note. The numbers below come
from the course's published reference run, and saying so is more interesting
than claiming otherwise.

## The provenance line to include

```text
Timing and cost figures are re-derived from the course's published reference
run (MIT, DataTalks.Club and Nebius) with my own cost engine; the engine
reproduces their published breakevens on three GPUs. My own Job will replace
them.
```

## LinkedIn

```text
Completed Module 1 of Production AI Agents for Generative Media.

I am building "Living Origin Cards" for a Kenyan specialty coffee roaster: for
each coffee origin, a painterly illustration of where the cherry grew, animated
into a 5 second silent loop for social. I picked it because origin storytelling
is how a small roaster sells a commodity, and because 200 origins is a batch
problem, not an image problem.

The run: Wan2.2 image-to-video on one H100, as a single Nebius Serverless AI
Job. One startup, one model load, ten animations, and the Job stops billing
when it is done.

  76.7 s  median generation time per asset
  $0.0958 marginal compute cost per asset
  $0.2025 what fal.ai charges per call for the same model
  15      assets per run before self hosting beats the API

The part I did not expect: the breakeven is decided by the fixed cost, not the
marginal one. It is the 126 GB weight download that has to be paid for, so
caching the weights moves the breakeven and making the model faster barely
does. And the same workload has three answers depending on the price you pay
for the GPU: 15 clips at the regular price, 5 at the spot snapshot, 2 at the
live spot price this morning.

Code and the full cost model: https://github.com/OumaCavin/personalized-media-factory

@DataTalksClub @Nebius
```

## X

```text
Module 1 of Production AI Agents for Generative Media is done.

Ten Kenyan coffee origins, ten animated origin cards, one H100 Job, one weight
download.

76.7 s per card. $0.0958 each in marginal compute. A per-call API charges
$0.2025 for the same model, so self hosting pays off from 15 cards per run.

The fixed cost decides that number, not the marginal one. The weight download
is what you have to beat.

https://github.com/OumaCavin/personalized-media-factory

@DataTalksClub @Nebius
```

## Short form, for a comment or a Slack message

```text
Module 1 done. Built "Living Origin Cards": an illustration plus a 5 second
loop per Kenyan coffee origin, Wan2.2 image-to-video on one H100 as a
Nebius Serverless AI Job. 76.7 s per asset, $0.0958 marginal cost, $0.2025
for the same model per call on fal.ai, so self hosting breaks even at 15
cards per run. Cost model and code:
https://github.com/OumaCavin/personalized-media-factory
```

## Rules

- Tag `@DataTalksClub` and `@Nebius`.
- No credentials, no Endpoint tokens, no bucket keys, and no run IDs that are
  still billing. Stop or delete every Endpoint, Job and DevLab first, then
  check Billing to Usage the next day to confirm nothing is still billing.
- Post after the cleanup, not before.

## Useful progress links to collect

The submission form takes up to seven public links. These are the ones worth
posting as they happen:

1. The repository, once the first commit is pushed.
2. The generated cost table, `docs/homework-answers.generated.md`.
3. A short post with the cost-versus-batch-size curve.
4. A post on the spot price versus regular price comparison.
5. A post on the `F / N + c` model applied to a model I did not measure.
6. The cross-check that my engine reproduces the published breakevens.
7. A post on the first own-run Job, once it exists.
