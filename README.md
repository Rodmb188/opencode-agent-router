# Local LLM Agent Routing System for opencode

A multi-agent system that runs **100% locally** on a consumer-grade AMD machine (RX 6700 XT, 12 GB VRAM, 32 GB RAM), turning one 27B and one 14B open-source model into 18 specialized sub-agents with automatic routing by task type — no cloud, no API costs, no privacy leaks.

Every design decision here was validated with **measured evidence** (blind A/B tests, benchmarks, failure post-mortems), not vibes. The repository includes the harness, the raw results, and the lessons learned.

---

## Why this exists

Running a single large model locally is easy. Running it **well** is hard:

- **One model can't be good at everything.** The 27B quantized to fit 12 GB VRAM is great at creative writing but consistently fails multi-step arithmetic — 5 out of 5 arithmetic chains were wrong in testing. A smaller 14B model nails every calculation. These are complementary strengths.
- **Latency budgets are tiered.** You don't wait 4 minutes of deep thinking for a "what's 15% of 280?" question, and you don't accept 10-second shallow answers for an architecture decision.
- **Memory is the real constraint.** 27B models at full context thrash in swap on 32 GB RAM. The system has to be *designed* around the hardware.

The result is a **router** that classifies every request into 20 levels (T0–T19) and delegates it to the cheapest model that can do the job correctly.

---

## Part I — Foundations: choosing and taming the local models

This project started with a simple question: *what's the best free Ollama model for a machine with a 12 GB AMD GPU and 32 GB RAM?* The answer turned into a week of benchmarking, a surprise discovery about hidden thinking modes, and ultimately the design choices that make Part II (the routing system) possible.

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

Abliterated models strip the refusal/alignment layers — required by design (uncensored use case, same quality retained).

### Initial speed benchmarks (real hardware, `/api/generate`)

| Model | Context | tok/s | Time / ~200 tok | GPU split | Notes |
|---|---|---|---|---|---|
| Qwen3 14B | 16k | 11.9 | ~17 s | 80% GPU / 20% CPU | Thinking ON |
| Qwen3 14B | 16k (no-think) | 11.8 | ~20 s | 80% GPU | 242 tokens vs 422 |
| Qwen3 14B | **8k (no-think)** | **23.7** | **~8 s** | **91% GPU** | 2× faster — the sweet spot |
| Qwen3.6 27B | 16k | 4.0 | ~56 s¹ | 53% GPU / 47% CPU | Ceiling performance |
| Qwen3.6 27B | 16k (no-think) | 4.0 | ~80 s¹ | 53% GPU | 312 tokens vs 2,278 |

> ¹ The fast rows are a *capped* ~200-token measurement for comparing speed regimes. With thinking ON the model spends 2,000–4,000 tokens reasoning first — the honest end-to-end figure is **568 s / ~9.5 min** for 2,278 tokens (see *think: false* below).

### The KV cache economics (the memory trap)

Every extra token of context costs **≈ 384 KB** (fp16) of KV-cache RAM — paid per active session. The cheaper the model's parameters, the more you feel it:

| Context | KV cache | Total model + cache | Fits on 12 GB GPU? |
|---|---|---|---|
| 4,096 | 1.5 GB | ~10.5 GB | ✅ 100% GPU, fast |
| 16,384 | 6.3 GB | ~15.3 GB | ❌ spills to CPU/RAM |
| 32,768 | 12.6 GB | ~21.6 GB | ❌ slow, mostly RAM |
| 128,000 | ~50 GB | ~59 GB | ❌ impossible on 32 GB |

This table is the foundation for Part II's decision to lock the 27B at `num_ctx=12288` (saving ≈ 1.5–2 GB vs 16k while retaining ~80% of multi-turn capacity).

### The single biggest performance lever: `think: false`

Qwen3.x models generate an internal "mental draft" of **2,000–4,000 tokens** (in mixed English/Chinese) before producing a single word of output. Disabling it costs one API parameter and saves **fifteen minutes per response**:

| | With thinking | With `think: false` |
|---|---|---|
| Tokens consumed | 4,003 | 312 |
| Wall time | 19 min 4 s | 3 min 39 s |
| Output quality | Slightly more rigorous | Nearly identical |

The key: opencode passes `options.body.think: false` as a top-level field to the Ollama API — the only reliable path (CLI flags and Modelfile parameters are silently ignored). This discovery made the "two-speed 27B" architecture (fast default + deep thinking on demand) viable.

### Model stack that emerged from Part I

> At this point the models were named `nothink` / `megabrain` / `qwen3-local` / `vision`. Part II renamed the 27B pair to `nothink-v2` / `megabrain-v2` and shifted their context 16k → 12288 (see *Memory engineering*).

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

> **Part II** (the rest of this README) replaces the manual "select a model from the TUI" workflow with an **automatic task router** that picks the right model at the right speed for every request — running 100% locally.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User (chat)                          │
└────────────────────────────┬────────────────────────────────┘
                             │
                     ┌───────▼───────┐
                     │   ROUTER       │   Classifies T0–T19
                     │  (roteador)    │   Applies iron rules
                     └───────┬───────┘
                             │ task delegation
┌────────────┬───────┼───────┬────────────┬────────────┐
        ▼            ▼       ▼       ▼            ▼            ▼
   preciso     financeiro  pesquisa  redator   profundo    dados
   math (14B)    money (14B) web (27B)  copy (27B) analyze     csv (14B)
                                                          …
                       ▲           ▲
                       │           │
               ┌───────┴───┐   ┌───▼──────────┐
               │ Ollama    │   │ Local models │
               │ server    │   │ 27B + 14B + 8B│
               │ 11434     │   │ vision       │
               └───────────┘   └──────────────┘
```

### The model zoo

| Model | Size | Job | Notes |
|---|---|---|---|
| `nothink-v2` | 27B (16 GB file) | Creative writing, research, tutoring, translation, code, sysadmin | Fast mode (thinking disabled). **Won the creativity A/B (17.5 vs 16.3/20)** |
| `megabrain-v2` | 27B (same blob) | Deep analysis, critical decisions | Thinking enabled — 10–50× slower, highest reliability |
| `qwen3-local` | 14B (9 GB) | Math, finance, review, QA, data, SEO, format conversion | **Never misses multi-step arithmetic.** Fast and paranoid |
| `vision` | 8B VL | Image/OCR | 12.5 s/image |

Two of the 27B models share the **same patched blob** — they differ only in whether `think` is on or off at request time. The blob carries a custom template fix (see *The Jinja crash*).

### The router ladder (T0–T19)

Every incoming request is classified by tier. The iron rules (the non-negotiables that came from real failures):

- **T0/T1 (trivial/general): never delegate.** Instant answers by the main model.
- **Multi-step math is forbidden on the main model.** The 27B fast-mode gets arithmetic wrong *even when instructed to verify*. Math → 14B.
- **Never run heavy 27B sub-agents in parallel.** Six parallel agents caused `ProviderHeaderTimeoutError` (5-min header timeout) through swap thrashing. Heavy = sequential, light = parallel ok.
- **A web search that returns empty is a failure.** Fallback to audited knowledge with an explicit disclaimer.
- **Explicit user model choice always wins.**

| Tier | Category | Agent (model) |
|---|---|---|
| T2 | Math / logic | `preciso` (qwen3-local) |
| T3 | Finance (interest, installments) | `financeiro` (qwen3-local) |
| T4 | Web research (products, prices, news) | `pesquisa` (nothink-v2) |
| T5 | Images / OCR | `ver` (vision) |
| T6 | Creative writing | `redator` (nothink-v2) |
| T7 | Text review / QA | `revisor` (qwen3-local) |
| T8 | Isolated code | `codigo` (nothink-v2) |
| T9 | Teaching / tutoring | `tutor` (nothink-v2) |
| T10 | Long-text summary | `sumarizador` (nothink-v2) |
| T11 | Translation | `tradutor` (nothink-v2) |
| T12 | Deep analysis | `profundo` (megabrain-v2) |
| T13 | Data analysis (CSV...) | `dados` (qwen3-local) |
| T14 | Sysadmin / automation | `sysadmin` (nothink-v2) |
| T15 | Interview simulation | `entrevistador` (nothink-v2) |
| T16 | Project planning | `planner` (nothink-v2) |
| T17 | SEO pt-BR | `seo` (qwen3-local) |
| T18 | Final QA / verification | `qa` (qwen3-local) |
| T19 | Format conversion (CSV↔JSON...) | `importador` (qwen3-local) |

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
- `nothink-v2` (27B, no-think): 13/14 with **1 arithmetic failure** ("34" instead of "44") that could not be fixed by ordering it to verify.
- `megabrain-v2` (27B, thinking): 3/3 correct — but at **61–235 s** per call.

**Decision:** the 27B never touches money or math tiers. Latency budget for re-checking a quote is 5 s, not 4 minutes.

### Objective format tests (type fidelity)
`importador` on a CSV→JSON blind test: the 27B silently altered types (`"32"` → `32`, `""` → `null`); the 14B preserved schema. **Data conversion, data analysis, and SEO → 14B.**

---

## Memory engineering (the fun part)

On this hardware the 27B splits ~10 GB VRAM / ~8 GB RAM. The real killer is the **KV cache** — the per-token context memory:

| Context | KV cache | RAM saved vs 16384 |
|---|---|---|
| 16384 (default) | ~4–6 GB | — |
| 12288 (chosen) | ~3–4 GB | ~1–2 GB |
| 8192 | ~2–3 GB | ~2–3 GB |

12288 was picked as the sweet spot: imperceptible quality impact, comfortable 4–6 turn conversations, and the KV cache fits the memory budget. ⚠️ note: the models' baked-in `num_ctx` **overrides** the `OLLAMA_CONTEXT_LENGTH` env var, so the models had to be **recreated** with `PARAMETER num_ctx 12288` (see `models/`), not just reconfigured.

The host uses **zram (zstd)** for swap — healthy at 3.4× compression ratio — which we confirmed is *not* the bottleneck; the bottleneck is that *any* swap access is 5–10× slower than RAM. Hence: fewer contexts → less swap → faster responses.

Other mitigations baked into the router:
- **Sequential execution of 27B agents** (parallel = swap thrash = provider timeouts).
- **`ollama stop`** between heavy sessions to free ~18 GB instantly.
- **`ollama-start`** script that pins `OLLAMA_CONTEXT_LENGTH` and guards against double-start.

---

## Failures that shaped the system

A system hands you its best feature by teaching you its worst failure:

### 1. The Jinja template crash
Ollama raised a runtime error from the model's Jinja template during tool calls ("No user query provided"), killing tool-use sessions silently. **Fix:** a low-level patch of the model's chat template inside its GGUF blob (see `models/build_replacement.py` + `models/qwen3_template.jinja`), built with a custom blob rebuild. The two 27B models now run on the patched blob.

### 2. Empty results & provider timeouts
A research agent returned nothing on its first live run. Post-mortem through server logs found **two stacked causes**:
- Six 27B sub-agents launched in parallel → swap thrash → 5-minute `ProviderHeaderTimeoutError`s throttled everything.
- The agent **recursively delegated to itself** via `opencode call` in bash instead of using the websearch tool.

**Fixes:** (a) router rule *heavy = sequential*, (b) provider timeout raised 5 → 20 min, (c) agent prompt now *forbids self-delegation and bash recursion*, (d) a documented **fallback path**: if web search returns empty, answer from consolidated knowledge with an explicit "values not confirmed online" disclaimer — never an empty reply.

### 3. The hallucinated correction
The 14B reviewer, while competently catching real errors, once "corrected" a phrase that was already correct ("ter pedidos"). **Fix:** prompt rule — *never invent defects; ambiguous items are suggestions, not corrections.*

### 4. Stale reasoning residue
The deep-analysis model leaked a stray CJK character from its scratch reasoning into a final answer. **Fix:** a mandatory clean-output pass rule (pure target language, no foreign-script artifacts).

---

## Repository layout

```
├── README.md                   ← you are here
├── LICENSE
├── ollama-start                ← server bootstrap (pins OLLAMA_CONTEXT_LENGTH, guards double-start)
├── agents/                     ← the 18 sub-agent definitions (opencode agent files)
├── config/
│   ├── opencode.jsonc          ← provider + model wiring, 20-min timeout
│   └── AGENTS.md               ← global iron rules
├── models/                     ← how to rebuild the local models
│   ├── nothink-v2.Modelfile    ← 27B, no-think, 12288 ctx
│   ├── megabrain-v2.Modelfile  ← 27B, thinking, 12288 ctx
│   ├── build_replacement.py    ← the GGUF template-patch tooling
│   └── qwen3_template.jinja    ← the fixed chat template
├── skills/
│   ├── roteador/SKILL.md       ← the router: tier ladder + iron rules
│   └── pesquisa-web/SKILL.md   ← websearch-first research skill
└── benchmarks/
    ├── avaliar-modelos         ← reusable benchmark CLI
    ├── benc_writing.py         ← A/B creativity harness
    ├── benc_agentes.py         ← router-validation harness
    ├── benc_objetivo.py        ← type-fidelity tests
    ├── run_tests.py            ← full battery (14 varied prompts)
    └── results/                ← raw outputs, maps, versions, vision test
```

`opencode` (*the CLI this configures*) loads every `.md` in its `agent/` directory as a delegatable sub-agent and applies `AGENTS.md` as global instructions — no plugin code needed; the whole system is **declarative markdown + one JSON config**.

---

## Getting started

> This setup tailors models that you must already have locally. The A/B numbers here are mine; on your hardware they may differ — which is the point: **measure, don't copy.**

1. **Clone and install the config layer.**
   ```bash
   git clone git@github.com:<you>/opencode-agent-router.git ~/.config/opencode
   ```
2. **Provide the models.** You need a Qwen3-6.5/3.6-class 27B (abliterated, with the template fix applied per `models/README`) and a 14B, pushed into Ollama. Then rebuild with the Modelfiles:
   ```bash
   ollama create nothink-v2   -f models/nothink-v2.Modelfile
   ollama create megabrain-v2 -f models/megabrain-v2.Modelfile   # FROM nothink-v2
   ```
3. **Start the server** (pins `OLLAMA_CONTEXT_LENGTH=12288`):
   ```bash
   ./ollama-start
   ```
4. **Run the benchmark** against your own models and compare with `benchmarks/results/`:
   ```bash
   ./benchmarks/avaliar-modelos
   ```
5. **Use it.** Just chat in a normal opencode session; the router handles the rest.

---

## Results snapshot (this hardware)

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

---

## Tech stack

- **opencode** — CLI + sub-agent + skill runtime
- **Ollama** — local model server (`/v1` OpenAI-compatible)
- **Qwen3-family GGUF** models (abliterated), quantized Q4
- **Python** — benchmark harnesses
- **zram/zstd** — compressed swap planning
- AMD RX 6700 XT · **Vulkan/RADV**, 20-core CPU, 32 GB RAM

## Future work

- [ ] Swap-based latency profiling before/after context tuning (quantify the 1–2 GB win)
- [ ] Add a 7B tier for T0/T2 to offload the 14B
- [ ] Automated regression battery that re-runs the A/Bs on every model change
- [ ] CI-style "router sanity" smoke suite on live routing
- [ ] Standalone CLI so the router works outside opencode

## License

MIT — see [LICENSE](LICENSE).

*Português note: the agent definitions and prose targets are pt-BR because that is the primary language of use; the benchmark artifacts and routing layers are language-agnostic.*