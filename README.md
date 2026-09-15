# Local LLM Agent Routing System for opencode

A multi-agent system that runs **every model 100% locally** on a consumer-grade
AMD machine (RX 6700 XT, 12 GB VRAM, 32 GB RAM): one 27B, one 14B, and one 8B
vision model become **18 specialized sub-agents**, with automatic routing by
task type. **All reasoning happens on-device** — no API costs, no model calls to
the cloud, no privacy leaks. The single deliberate exception is web research
(T04), which by definition must reach the live internet (see below).

Every decision was validated with blind A/B tests, benchmarks, and failure
post-mortems — not vibes. The chronicle and raw results live in
[docs/ENGINEERING_JOURNAL.md](docs/ENGINEERING_JOURNAL.md).

### "Local": o que isso significa de verdade

- **Raciocínio: 100% local.** Toda inferência dos 18 sub-agentes roda no Ollama
  desta máquina. Nenhum texto sai do hardware para ser *pensado* por um modelo
  na nuvem.
- **T04 (pesquisa web) é a exceção deliberada.** Buscar "melhor celular até
  R$2.000 em 2026" exige dados vivos da internet — não existem no modelo local,
  por mais brilhante que ele seja. O fetch é feito pela tool `websearch` do
  opencode (backend Exa/Parallel), uma chamada HTTP curta por query. O que o
  `pesquisa` (nothink-v2 local) recebe são trechos de texto já coletados; **a
  síntese, o julgamento e a resposta final são 100% locais.**
- **Por que não o subagente busca sozinho:** subagentes rodam no provider
  `ollama`, e o opencode só expõe `websearch` em providers `opencode` para este
  binário (filtro em `registry.ts`, provado no dogfood sec. 13). Quem busca é o
  primário; quem pensa é o subagente local.
- **Se você quer T04 offline de verdade**, a troca é aceitar dados de hoje em
  vez de dados ao vivo — ou plugar um backend de busca próprio no `websearch`.
  Não há como ter um dado de hoje *e* 100% offline: a internet é a fonte.

---

## Why this exists

Running a single large model locally is easy. Running it **well** is hard:

- **One model can't be good at everything.** The 27B fast-mode (no thinking,
  quantized to fit 12 GB VRAM) is great at creative writing but consistently
  fails multi-step arithmetic — 5 of 5 arithmetic chains were wrong in testing.
  A 14B nails every calculation. These are complementary strengths.
- **Latency budgets are tiered.** You don't wait 4 minutes of deep thinking for
  a "what's 15% of 280?" question, and you don't accept 10-second shallow answers
  for an architecture decision.
- **Memory is the real constraint.** 27B models at full context thrash in swap on
  32 GB RAM. The system is *designed* around the hardware, not the other way round.

The result is a **router** that classifies every request into 20 levels (T00–T19)
and delegates it to the cheapest model that can do the job correctly.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User (chat)                          │
└────────────────────────────┬────────────────────────────────┘
                             │
                     ┌───────▼───────┐
                     │   ROUTER      │   Classifies T00–T19
                     │  (roteador)   │   Applies iron rules
                     └───────┬───────┘
                             │ task delegation
                             │ (T04: primary also runs websearch
                             │  and embeds snippets in the task)
┌─────────────┬──────────────┼────────────┬─────────────┬───────────┐
▼             ▼              ▼            ▼             ▼           ▼
preciso       financeiro     pesquisa     redator       profundo    dados
math (14B)    money (14B)    synth (27B)  copy (27B)    analyze     csv (14B)
                                                          …
                    ▲           ▲
                    │           │
               ┌────┴───┐   ┌───▼────────────┐
               │ Ollama │   │ Local models   │
               │ server │   │ 27B + 14B + 8B │
               │ 11434  │   │ vision         │
               └────────┘   └────────────────┘
```

### The model zoo

|      Model     |        Size       |                                Job                                |                                   Notes                                     |
|----------------|-------------------|-------------------------------------------------------------------|-----------------------------------------------------------------------------|
|  `nothink-v2`  | 27B (16 GB file)  | Creative writing, synthesis, tutoring, translation, code, sysadmin | Fast mode (thinking disabled). **Won the creativity A/B (17.5 vs 16.3/20)** |
| `megabrain-v2` | 27B (same blob)   | Deep analysis, critical decisions                                 | Thinking enabled — 10–50× slower, highest reliability                       |
| `qwen3-local`  | 14B (9 GB)        | Math, finance, review, QA, data, SEO, format conversion           | **Never misses multi-step arithmetic.** Fast and paranoid                   |
|    `vision`    | 8B VL             | Image/OCR                                                         | 12.5 s/image                                                                |

The two 27B models share the **same patched blob** — they differ only in whether
thinking is on or off at request time. The blob carries a low-level chat-template
fix (see *The Jinja crash* in the journal).

### The router ladder (T00–T19)

Every request is classified by tier. The iron rules — the non-negotiables that
came from real failures:

- **T00/T01 (trivial/general): never delegate.** Instant answers by the main model.
- **Multi-step math is forbidden on the main model.** The 27B fast-mode gets
  arithmetic wrong *even when instructed to verify*. Math → 14B.
- **Never run heavy 27B sub-agents in parallel.** Six parallel agents caused
  `ProviderHeaderTimeoutError` (5-min header timeout) through swap thrashing.
  Heavy = sequential, light = parallel ok.
- **Sub-agents on `ollama` never get the `websearch` tool** (opencode gates it by
  provider — see dogfood sec. 13), so the primary runs the searches and `pesquisa`
  synthesizes. A run that returns empty is a context-overflow input bug, not a
  timeout: cap embedded material (~4k tokens for the deep agent), chunk long texts.
- **Explicit user model choice always wins.**

|  Tier |                Category               |         Agent (model)        |
|-------|---------------------------------------|------------------------------|
|  T02  | Math / logic                          | `preciso` (qwen3-local)      |
|  T03  | Finance (interest, installments)      | `financeiro` (qwen3-local)   |
|  T04  | Web research (products, prices, news) | primary searches + `pesquisa` synthesizes (nothink-v2) |
|  T05  | Images / OCR                          | `ver` (vision)               |
|  T06  | Creative writing                      | `redator` (nothink-v2)       |
|  T07  | Text review / QA                      | `revisor` (qwen3-local)      |
|  T08  | Isolated code                         | `codigo` (nothink-v2)        |
|  T09  | Teaching / tutoring                   | `tutor` (nothink-v2)         |
|  T10  | Long-text summary                     | `sumarizador` (nothink-v2)   |
|  T11  | Translation                           | `tradutor` (nothink-v2)      |
|  T12  | Deep analysis                         | `profundo` (megabrain-v2)    |
|  T13  | Data analysis (CSV...)                | `dados` (qwen3-local)        |
|  T14  | Sysadmin / automation                 | `sysadmin` (nothink-v2)      |
|  T15  | Interview simulation                  | `entrevistador` (nothink-v2) |
|  T16  | Project planning                      | `planner` (nothink-v2)       |
|  T17  | SEO pt-BR                             | `seo` (qwen3-local)          |
|  T18  | Final QA / verification               | `qa` (qwen3-local)           |
|  T19  | Format conversion (CSV↔JSON...)       | `importador` (qwen3-local)   |

### Known limitations (measured, not theoretical)

- **Context is the killer, not the model.** Several sub-agents have returned
  *empty* results — every single time it was an input-size bug (`reason: length`
  at 12,288 tokens: `profundo` with the README embedded whole, `pesquisa` after
  14 `webfetch` calls), never a model failure. Mitigation is preventive: cap
  embedded material (~4k tokens for the 27B thinking agent), chunk long texts,
  never rely on retry.
- **`websearch` is host-side.** Sub-agents on `ollama` never receive the tool —
  opencode gates it by provider (dogfood sec. 13). T04 is split by design:
  primary fetches, sub-agent synthesizes. Same result, right tool, no context blowup.
- **CJK leakage is a decode artifact, not a prompt problem.** Qwen3-family
  occasionally emits one foreign character as the very first token, even with an
  explicit "think in pt-BR" rule. The deterministic fix is presentation-layer:
  the router strips any non-Latin prefix before showing the result (dogfood sec. 11).
- **The primary cannot attach images** (main model has no multimodal input), so
  a T05 vision smoke must be run manually in the TUI with an attached image.
- **Hardware is the ceiling.** Two 27B parallel agents thrash swap on 32 GB RAM
  (`ProviderHeaderTimeoutError`). Heavy agents run sequentially by rule.

---

## Design decisions, in brief

Three measured ratifications underpin the ladder above (details + raw data in the
journal):

1. **Creativity** — blind A/B (36 shuffled outputs, fixed rubric): 27B no-think
   **17.5/20** vs 14B 16.3/20 → the 27B owns creative tiers.
2. **Math reliability** — `qwen3-local` **14/14** (~6 s); `nothink-v2` **13/14**
   (1 arithmetic error, unfixable by instruction — and 5 of 5 multi-step chains
   failed in a dedicated dry-run); `megabrain-v2` **3/3** but 61–235 s →
   math/finance/data go only to the 14B.
3. **Format fidelity** — CSV→JSON blind test: `nothink-v2` (fast-mode 27B)
   silently altered types (`"32"` → `32`, `""` → `null`); the 14B preserved the
   schema → conversion and data tiers go only to the 14B.
4. **Tool gating beats assumptions (T04 worked example).** The first design had
   the `pesquisa` sub-agent run `websearch` itself. It never happened: opencode
   only exposes that tool on `opencode`-provider sessions, not `ollama`, and
   without it the agent fell into 14 `webfetch` calls that filled its 12,288-token
   context and returned *empty* (`reason: length`). The fix came from the
   evidence, not a preference: **split the job where the tool exists** — the
   primary runs 2–3 `websearch` calls, extracts the essential snippets, embeds
   them in the task message, and the local 27B does the synthesis/ranking/
   verdict. Same quality, no context blowup, and the exact same "data online,
   thinking local" split described in the intro. (Dogfood sec. 8–9 and 12–13.)

---

## Memory design

The 27B splits ~10 GB VRAM / ~8 GB RAM; the real killer is the **KV cache** (the
per-token context memory, ≈ 384 KB/token fp16). Context is part of the design:

|       Context      | KV cache | RAM saved vs 16384 |
|--------------------|----------|--------------------|
|   16384 (default)  | ~4–6 GB  |          —         |
| **12288 (chosen)** | ~3–4 GB  |       ~1–2 GB      |
|        8192        | ~2–3 GB  |       ~2–3 GB      |

`12288` is the sweet spot: imperceptible quality impact, comfortable 4–6 turn
conversations, KV fits the memory budget. ⚠️ the models' baked-in `num_ctx`
**overrides** the `OLLAMA_CONTEXT_LENGTH` env var — so the models were
**recreated** with `PARAMETER num_ctx 12288` (see `models/`), not just
reconfigured.

The host uses **zram (zstd)** for swap — healthy at 3.4× compression — but any
swap access is 5–10× slower than RAM. Hence: fewer contexts → less swap → faster
responses. Other mitigations built into the router:

- Sequential execution of 27B agents (parallel = swap thrash = provider timeouts).
- `ollama stop` between heavy sessions to free ~18 GB instantly.
- `ollama-start` script pins `OLLAMA_CONTEXT_LENGTH` and guards double-start.

---

## Repository layout

```
├── README.md                   ← you are here
├── LICENSE
├── ollama-start                ← server bootstrap (pins OLLAMA_CONTEXT_LENGTH, guards double-start)
├── docs/
│   └── ENGINEERING_JOURNAL.md  ← the full chronicle (benchmarks, failures, results)
├── agent/                      ← the 18 sub-agent definitions (opencode agent files, one .md each)
├── config/
│   ├── opencode.jsonc          ← provider + model wiring, 20-min timeout
│   └── AGENTS.md               ← global iron rules
├── models/                     ← how to rebuild the local models
│   ├── README.md               ← step-by-step: obtain base, apply template fix, rebuild
│   ├── nothink-v2.Modelfile    ← 27B, no-think, 12288 ctx
│   ├── megabrain-v2.Modelfile  ← 27B, thinking, 12288 ctx
│   ├── build_replacement.py    ← the GGUF template-patch tooling
│   └── qwen3_template.jinja    ← the fixed chat template
├── skills/
│   ├── roteador/SKILL.md       ← the router: tier ladder + iron rules
│   └── pesquisa-web/SKILL.md   ← search guidelines for the primary (T04)
└── benchmarks/
    ├── avaliar-modelos         ← reusable benchmark CLI
    ├── benc_writing.py         ← A/B creativity harness
    ├── benc_agentes.py         ← router-validation harness
    ├── benc_objetivo.py        ← type-fidelity tests
    ├── run_tests.py            ← full battery (14 varied prompts)
    └── results/                ← raw outputs, maps, versions, vision test
```

`opencode` (*the CLI this configures*) loads every `.md` in its `agent/`
directory as a delegatable sub-agent and applies `AGENTS.md` as global
instructions — no plugin code; the whole system is **declarative markdown + one
JSON config**.

Every agent declares an explicit `permission:` block in its frontmatter (15
tool keys) — the default is **deny**, and each agent opens only what its role
needs. Text/vocal agents (including `pesquisa`) are pure readers of embedded
material with all tools denied; only `codigo`, `dados`, `importador` and
`sysadmin` keep file/shell tools. `task` is denied on every sub-agent
(nested delegation is cut off by design). One lesson from real failures
(dogfood sec. 10 and 13): `permission` frontmatter is necessary but not
sufficient — opencode's registry can still gate a tool by provider (e.g.
`websearch` never reaches sub-agents running on `ollama`), so the T04 flow is
"primary searches, sub-agent synthesizes".

---

## Getting started

> This setup tailors models you must already have locally. The A/B numbers here
> are mine; on your hardware they may differ — which is the point: **measure,
> don't copy.**

1. **Clone and install the config layer.**
   ```bash
   git clone git@github.com:Rodmb188/opencode-agent-router.git ~/.config/opencode
   ```
2. **Provide the models.** You need the `richardyoung/qwen3.6-27b-abliterated`
   class of 27B (with the template fix applied per `models/README`) and a 14B,
   pushed into Ollama. Then rebuild with the Modelfiles:
   ```bash
   ollama create nothink-v2   -f models/nothink-v2.Modelfile
   ollama create megabrain-v2 -f models/megabrain-v2.Modelfile   # FROM nothink-v2
   ```
3. **Start the server** (pins `OLLAMA_CONTEXT_LENGTH=12288`):
   ```bash
   ./ollama-start
   ```
4. **Run the benchmark** against your own models and compare with
   `benchmarks/results/`:
   ```bash
   ./benchmarks/avaliar-modelos
   ```
5. **Use it.** Just chat in a normal opencode session; the router handles the rest.

---

## Tech stack

- **opencode** — CLI + sub-agent + skill runtime
- **Ollama** — local model server (`/v1` OpenAI-compatible)
- **Qwen3-family GGUF** models (abliterated), quantized Q4
- **Python** — benchmark harnesses
- **zram/zstd** — compressed swap planning
- AMD RX 6700 XT · **Vulkan/RADV**, 20-core CPU, 32 GB RAM

---

## License

MIT — see [LICENSE](LICENSE).

*Português note: the agent definitions and prose targets are pt-BR because that
is the primary language of use; the benchmark artifacts and routing layers are
language-agnostic.*
