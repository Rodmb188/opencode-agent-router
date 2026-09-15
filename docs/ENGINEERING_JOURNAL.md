# Engineering Journal

The decisions that shaped this system were validated with measured evidence, not
hypothesis. This document collects the full chronicle: the model selection
journey, the KV-cache economics, the *think: false* discovery, the failures that
led to iron rules, and the raw results from live routing waves.

Start with [README.md](../README.md) for the stable overview of what the system
does and how it works.

---

## Part I — Foundations: choosing and taming the local models

This project started with a simple question: *what's the best free Ollama model
for a machine with a 12 GB AMD GPU and 32 GB RAM?* The answer turned into a week
of benchmarking, a surprise discovery about hidden thinking modes, and ultimately
the design choices that make Part II (the routing system) possible.

### The machine

| Component | Spec |
|---|---|
| CPU | Intel i9-10900KF (10C / 20T) |
| RAM | 32 GB, ~16 GB free |
| GPU | AMD RX 6700 XT, 12 GB VRAM (Vulkan/RADV backend) |
| OS | CachyOS (Arch-based), user-space Ollama (no sudo) |
| Storage | ~636 GB free NVMe |

### Model journey

```
Day 1  qwen2.5:14b (wrong recommendation — 2.5 was older; 3.0 existed for the same size)
Day 1    ──→ huihui_ai/qwen3-abliterated:14b  (2.5 deleted, identical size, better benchmarks)
Day 1    ──→ + qwen3-vl:8b              (vision/multimodal, best free option for 12 GB)
Day 1    ──→ + richardyoung/qwen3.6-27b-abliterated  (Q4 ~16 GB — "the ceiling this machine can hold")
```

Abliterated models strip the refusal/alignment layers — required by design
(uncensored use case, same quality retained).

### Initial speed benchmarks (real hardware, `/api/generate`)

| Model | Context | tok/s | Time / ~200 tok | GPU split | Notes |
|---|---|---|---|---|---|
| Qwen3 14B | 16k | 11.9 | ~17 s | 80% GPU / 20% CPU | Thinking ON |
| Qwen3 14B | 16k (no-think) | 11.8 | ~20 s | 80% GPU | 242 tokens vs 422 |
| Qwen3 14B | **8k (no-think)** | **23.7** | **~8 s** | **91% GPU** | 2× faster — the sweet spot |
| Qwen3.6 27B | 16k | 4.0 | ~56 s¹ | 53% GPU / 47% CPU | Ceiling performance |
| Qwen3.6 27B | 16k (no-think) | 4.0 | ~80 s¹ | 53% GPU | 312 tokens vs 2,278 |

> ¹ The fast rows are a *capped* ~200-token measurement for comparing speed
> regimes. With thinking ON the model spends 2,000–4,000 tokens reasoning first
> — the honest end-to-end figure is **568 s / ~9.5 min** for 2,278 tokens (see
> *think: false* below).

### The KV cache economics (the memory trap)

Every extra token of context costs **≈ 384 KB** (fp16) of KV-cache RAM — paid per
active session. The cheaper the model's parameters, the more you feel it:

| Context | KV cache | Total model + cache | Fits on 12 GB GPU? |
|---|---|---|---|
| 4,096 | 1.5 GB | ~10.5 GB | ✅ 100% GPU, fast |
| 16,384 | 6.3 GB | ~15.3 GB | ❌ spills to CPU/RAM |
| 32,768 | 12.6 GB | ~21.6 GB | ❌ slow, mostly RAM |
| 128,000 | ~50 GB | ~59 GB | ❌ impossible on 32 GB |

This table is the foundation for Part II's decision to lock the 27B at
`num_ctx=12288` (saving ≈ 1.5–2 GB vs 16k while retaining ~80% of multi-turn
capacity).

### The single biggest performance lever: `think: false`

Qwen3.x models generate an internal "mental draft" of **2,000–4,000 tokens**
(in mixed English/Chinese) before producing a single word of output. Disabling
it costs one API parameter and saves **fifteen minutes per response**:

| | With thinking | With `think: false` |
|---|---|---|
| Tokens consumed | 4,003 | 312 |
| Wall time | 19 min 4 s | 3 min 39 s |
| Output quality | Slightly more rigorous | Nearly identical |

The key: opencode passes `options.body.think: false` as a top-level field to the
Ollama API — the only reliable path (CLI flags and Modelfile parameters are
silently ignored). This discovery made the "two-speed 27B" architecture (fast
default + deep thinking on demand) viable.

### Model stack that emerged from Part I

> At this point the models were named `nothink` / `megabrain` / `qwen3-local` /
> `vision`. Part II renamed the 27B pair to `nothink-v2` / `megabrain-v2` and
> shifted their context 16k → 12288 (see *Memory engineering* in README).

| Alias | Base model | Role | Context |
|---|---|---|---|
| `nothink` | Qwen3.6 27B abliterated | Daily driver (fast, no thinking) | 16k |
| `megabrain` | Same blob, thinking ON | Deep analysis, critical decisions | 16k |
| `qwen3-local` | Qwen3 14B abliterated | Fast math, reliable review | 8k |
| `vision` | Qwen3-VL 8B | Image/OCR | 8k |

### Operational tooling built in Part I

| Tool | Purpose |
|---|---|
| `systemd user service` | Auto-starts Ollama at boot (before login, via Linger) |
| `OLLAMA_KEEP_ALIVE=15m` | Keeps models warm across conversations |
| `/dummy` command | Pre-warms the model before heavy sessions |
| Compaction tuning | `tail_turns:5`, `preserve_recent_tokens:6000`, `reserved:2048` |

---

## Part II — The routing system

Part II replaces the manual "select a model from the TUI" workflow with an
**automatic task router** that picks the right model at the right speed for every
request — running 100% locally. See the [README](../README.md#architecture) for
the current architecture.

---

## Evidence over opinion: how decisions were made

### Blind creativity A/B (writing)

36 raw outputs generated, shuffled, scored blind against a fixed rubric:

| Model | Score | Verdict |
|---|---|---|
| nothink-v2 (27B, no-think) | **17.5 / 20** | Assigned to redator, tutor, sumarizador, tradutor |
| qwen3-local (14B) | 16.3 / 20 | Close, but the 27B wins on creative tasks |

### Reliable math vs fast math

- `qwen3-local` (14B): **14/14** correct, ~6 s each, step-by-step self-verified.
- `nothink-v2` (27B, no-think): 13/14 with **1 arithmetic failure** ("34"
  instead of "44") that could not be fixed by ordering it to verify.
- `megabrain-v2` (27B, thinking): 3/3 correct — but at **61–235 s** per call.

**Decision:** the 27B never touches money or math tiers. Latency budget for
re-checking a quote is 5 s, not 4 minutes.

### Objective format tests (type fidelity)

`importador` on a CSV→JSON blind test: the 27B silently altered types (`"32"` →
`32`, `""` → `null`); the 14B preserved schema. **Data conversion, data
analysis, and SEO → 14B.**

---

## Failures that shaped the system

A system hands you its best feature by teaching you its worst failure:

### 1. The Jinja template crash

Ollama raised a runtime error from the model's Jinja template during tool calls
("No user query provided"), killing tool-use sessions silently. **Fix:** a
low-level patch of the model's chat template inside its GGUF blob (see
`models/build_replacement.py` + `models/qwen3_template.jinja`), built with a
custom blob rebuild. The two 27B models now run on the patched blob.

### 2. Empty results & provider timeouts

A research agent returned nothing on its first live run. Post-mortem through
server logs found **two stacked causes**:
- Six 27B sub-agents launched in parallel → swap thrash → 5-minute
  `ProviderHeaderTimeoutError`s throttled everything.
- The agent **recursively delegated to itself** via `opencode call` in bash
  instead of using the websearch tool.

**Fixes:** (a) router rule *heavy = sequential*, (b) provider timeout raised 5 →
20 min, (c) agent prompt now *forbids self-delegation and bash recursion*, (d) a
documented **fallback path**: if web search returns empty, answer from
consolidated knowledge with an explicit "values not confirmed online" disclaimer
— never an empty reply.

### 3. The hallucinated correction

The 14B reviewer, while competently catching real errors, once "corrected" a
phrase that was already correct ("ter pedidos"). **Fix:** prompt rule — *never
invent defects; ambiguous items are suggestions, not corrections.*

### 4. Stale reasoning residue

The deep-analysis model leaked a stray CJK character from its scratch reasoning
into a final answer. **Fix:** a mandatory clean-output pass rule (pure target
language, no foreign-script artifacts).

---

## Results snapshot

### Part I — model speed & behavior

| Test | Model | Result |
|---|---|---|
| ~200-tok responses | Qwen3 14B @16k / @8k | 11.9 / **23.7 tok/s** (~17 s / ~8 s) |
| ~200-tok responses | Qwen3.6 27B @16k | 4.0 tok/s (~56 s) |
| Thinking on vs off (27B) | megabrain vs nothink | 4,003 vs 312 tokens · **19 min vs 3 min 39 s** |
| Context math | KV cache / token | 384 KB (fp16) |

### Part II — routing validation

| Test | Model | Result |
|---|---|---|
| Math battery (14 q) | qwen3-local | 14/14 · ~6 s |
| Math battery (14 q) | nothink-v2 | 13/14 · 1.8–11.5 s · 1 arithmetic error |
| Math battery (3 q) | megabrain-v2 | 3/3 · 61–235 s |
| Creativity A/B (36 out) | nothink-v2 vs qwen3-local | 17.5 vs 16.3 / 20 |
| Vision/OCR | vision 8B | red circle + "OLA 42" identified · 12.5 s |
| Live routing wave 1 | preciso / financeiro / revisor / importador | 2/4 perfect, reviewer caught real errors, CSV-quote edge found |
| Live routing wave 2 | codigo / tutor / sumarizador / tradutor / sysadmin / redator | flawless; one concordance slip caught and fixed |
| Live routing wave 3 | profundo / pesquisa | profundo excellent (one CJK leak, fixed); pesquisa first run empty → post-mortem → fixed |
| Wave 4: permission lockdown | all 18 agents | explicit `permission:` blocks; `task` denied everywhere; tool-gated smoke tests |
| Wave 5: dogfooding | profundo / revisor / preciso / pesquisa | profundo re-test PASSED (no CJK leak); CJK leak proven a decode artifact, fixed at router; T04 websearch provider-gate → search on primary, synthesize on subagent |

---

## Future work

- [ ] Swap-based latency profiling before/after context tuning (quantify the
  1–2 GB win)
- [ ] Add a 7B tier for T00/T01 and T02 to offload the 14B
- [ ] Automated regression battery that re-runs the A/Bs on every model change
- [x] CI-style "router sanity" smoke suite on live routing → partial: static
  layer landed in `benchmarks/regressao.py` + `.github/workflows/rota-ci.yml`;
  live smokes are a TUI checklist because headless `opencode run` hangs on this
  stack (dogfood 14b). A fully headless live run needs the CLI to route
  subagents — tracked as future.
- [ ] Standalone CLI so the router works outside opencode

---

## README dogfooding review

See [benchmarks/results/readme_review_dogfood.md](../benchmarks/results/readme_review_dogfood.md)
for the blind main-model vs `revisor` agent comparison of the README.

## Dogfooding waves 4–5 (post-release hardening)

The README shipped; what followed are the real-battle fixes that only show up
after the system runs. Full evidence in the dogfood log (sections 8–13).

### Context overflow is the recurring silent killer

Two different agents returned *empty* outputs, and both turn out to be the same
disease: input grew past the model context (12288 tokens) during the request, so
the answer step was capped at ~100 tokens before it started. First seen with
`profundo` (README embedded whole: 8.675 input tokens), then with `pesquisa`
(14 consecutive `webfetch` calls accumulated 9.660 input tokens). **Empty result
is almost never a timeout and never a model failure — it is an input-size bug**,
and the fix is preventive (cap/compact input), never retry.

### Tool permission: what "allow" really means (registry > frontmatter)

The `pesquisa` agent had `websearch: allow` in its frontmatter and still couldn't
search. Root cause is in opencode's own registry (`webSearchEnabled`): the
`websearch` tool is only exposed when the session's provider is `opencode` /
`opencode-go`, or `OPENCODE_ENABLE_EXA` / `OPENCODE_ENABLE_PARALLEL` is set.
All subagents here run on `ollama` → the tool never reaches them. The subagent
itself diagnosed it mid-run ("não tenho websearch — só webfetch e skill") and
fell back to 14 `webfetch` calls that blew the context.

**Decision:** invert the T04 division of labor — the primary (which runs on the
`opencode` provider and *does* have websearch) performs the searches and embeds
the snippets in the task message; the `pesquisa` agent becomes a pure synthesis
stage (rank, justify, verdict) with all tools denied. This matches the embed
pattern that already fixed `profundo` (sec. 8–9); it does not change VRAM (the
primary is cloud, the 27B subagent was already loaded) and keeps the subagent as
the synthesis expert rather than replacing it.

### CJK leak: proven a decode artifact, not a prompt problem

A per-agent "pense em pt-BR" rule did *not* stop stray CJK first-tokens (`颗`,
`起来`, `栋`). The honest conclusion (sec. 11) is that it is a first-token decode
artifact of Qwen3-family, unaffected by prompting; the deterministic fix lives in
the router's presentation layer (strip non-Latin prefix). The `profundo` re-test
under the new rules (sec. 12) came back clean pt-BR on the first run.

### The tools that kept working

Tool lockdown (sec. 10) did not break the stack: `preciso` math and `revisor`
grammar smoke tests still pass. The pattern that carries the system is:
**embed material in the message, cap heavy-agent input, sanitize on the way out.**