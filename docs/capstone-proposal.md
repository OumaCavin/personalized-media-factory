# Capstone proposal

**Course:** Production AI Agents for Generative Media
**Module:** 1, Make it work (proposals are due at the end of Module 1)
**Project:** Living Origin Cards, a personalized media factory for a specialty
coffee roaster

---

## 1. Problem and User

A small specialty coffee roaster sells origin: which county the cherry grew
in, which varietal, what it tastes like, and a picture of the place. Today
that story is told by hand for a handful of origins. The roaster has over two
hundred of them, and every new harvest adds more.

The user is the roaster's head of marketing and their two-person content
team. They need one asset set per origin, produced in a batch rather than one
at a time, consistent enough that the set looks like one campaign.

Each run produces, per origin: an **illustration** of the growing landscape, a
**five second silent animation** of that illustration, and a **spoken tasting
note** over the top. The animation is the format that matters: a silent loop
per origin is what gets posted, and one hundred of them is a quarter of a
year of content.

Why this is worth a factory rather than a designer: the records already exist
in the roaster's spreadsheet, the product is the same for all of them, and the
constraint is volume with consistency, not a single hero image.

## 2. Input Records

- **Dataset source:** the roaster's own origin spreadsheet, converted to CSV.
  Synthetic for the capstone run: `data/origins.csv` extended to 100 rows,
  with no real personal data in it.
- **Schema:** `id`, `origin`, `county`, `altitude_m`, `varietal`, `process`,
  `tasting_notes`, `scene`. The `scene` field is the visual brief; the
  illustration prompt is derived from it, so a change to the spreadsheet
  changes the asset without a code change.
- **Target batch size:** 100 records for the image and speech stages, and a
  deterministic 10 record sample (`seed = 42`) escalated to video.

## 3. GPU Media Models

| Role | Exact model ID and revision | Modality | Target GPU and preset | Licence |
| --- | --- | --- | --- | --- |
| Keyframe | `Efficient-Large-Model/Sana_1600M_1024px_diffusers` @ `ac0da2ff55fbe434795be0dce883042e4d49e2fc` | text to image, 512x512 PNG | `gpu-h100-sxm`, `1gpu-16vcpu-200gb`, eu-north1 | [Apache-2.0](https://huggingface.co/Efficient-Large-Model/Sana_1600M_1024px_diffusers/blob/main/LICENSE) (Gemma terms for the text encoder) |
| Animation | `Wan-AI/Wan2.2-I2V-A14B-Diffusers` @ `596658fd9ca6b7b71d5057529bbf319ecbc61d74` | image to video, 832x480 MP4, 81 frames at 16 fps | `gpu-h100-sxm`, `1gpu-16vcpu-200gb`, eu-north1 | [Apache-2.0](https://huggingface.co/Wan-AI/Wan2.2-I2V-A14B-Diffusers/blob/main/LICENSE) |
| Narration | `hexgrad/Kokoro-82M` @ `f3ff3571` | text to speech, 24 kHz mono | `gpu-h100-sxm`, `1gpu-16vcpu-200gb`, eu-north1 | [Apache-2.0](https://huggingface.co/hexgrad/Kokoro-82M) |

All three are already measured in this project, so the budget below is a
projection from times that exist, not a guess.

## 4. Pipeline and Quality Checks

```text
brief -> planner (LLM) -> GPU tools -> judge -> object storage
```

1. **Planner (LLM):** reads the origin row and produces the illustration
   prompt, the motion prompt and the spoken tasting note, as structured JSON.
   The planner never calls a GPU.
2. **Keyframe (Sana) and judge:** renders the illustration and checks two
   criteria before the asset is accepted:
   1. the scene from the record is recognisable in the frame, and
   2. the frame contains no readable text, watermark or logo.
   A failed keyframe is revised once by the planner and re-rendered, then
   dropped.
3. **Narration (Kokoro):** speaks the tasting note, on the GPU, only for
   keyframes that passed.
4. **Animation (Wan2.2), asynchronous Job:** the ten sampled origins whose
   keyframes passed are animated in a separate Job, because it is the
   expensive step and it does not depend on the other ninety.

## 5. Initial Budget Estimate

Using the cost model from lesson 05: `c = rate x t_gen` per asset and
`F = rate x (t_start + t_ready)` per worker run, at the H100 regular price of
$4.50 per GPU hour (`rate = $0.00125/s`). Times are the measured ones from the
reference run, reproduced with this project's own engine.

| Stage | Jobs | Assets | `F` per run | `c` per asset | Fixed total | Marginal total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Illustration (Sana) | 2 | 100 | $0.3096 | $0.00098 | $0.6191 | $0.0980 |
| Animation (Wan2.2) | 1 | 10 | $1.5046 | $0.09584 | $1.5046 | $0.9584 |
| Narration (Kokoro) | 1 | 100 | $0.2062 | $0.00021 | $0.2062 | $0.0211 |

- **Fixed total:** $2.3299
- **Marginal total:** $1.0776, **$1.2931** with the 20% retry allowance
- **Estimated total GPU compute for the full capstone batch: $3.62** at the
  regular price, or **$0.64** at the live spot price of $0.79 per GPU hour
  read on 2026-11-23.
- **Wall clock:** about 33 minutes for the animation Job, about 5 minutes for
  an illustration shard. The three stages overlap, so the batch finishes in
  roughly 35 minutes.

The number to watch is not the total. It is that 64% of it is fixed cost, and
almost all of that fixed cost is the two model weight downloads and the
machine startup. Before the capstone adds agents and evaluations, the plan is
to keep the weights warm between runs. That is worth more than every
generative speedup in the pipeline combined.

### Assumptions and what would change this estimate

- One Job per shard, each paying its own startup and its own model loads.
- Prices are the regular on demand price and are fixed. At the spot price the
  same batch costs about $0.64, and the spot price changes every 15 minutes.
- The disk, the bucket and any retries are not included.
- The 20% retry allowance is on the marginal cost only, since a retry inside
  an existing Job does not pay a second startup.
- If the animation stage moves to a smaller model that fits an L40S, the fixed
  cost of that stage falls by more than half and the batch drops below $2.50.
  That is the first experiment after Module 1.
