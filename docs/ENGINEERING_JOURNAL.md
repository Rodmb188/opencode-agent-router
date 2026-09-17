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
| `vision` | Qwen3-VL 8B | Image/OCR | 16k (raised from 8k — T05 round 4) |

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

### The T05 hand-off: the image never reached `ver` (sec. 15)

A real "Revisão Teste.png" session exposed a mirror image of the T04 bug, this
time in vision: the primary spawned `ver` three times with text-only prompts
(no attachment, no path), invented `/screenshots/...` reads, and sent `explore`
on a web-stack "screenshots" hunt while the folder (`Capturas de tela`) sat in
the conversation. `ver` was right every time ("I can't see an image"); the router
was broken. Two fixes shipped together:

1. `ver.md` permission `read: allow` (vision-only, all else stays deny) so the
   subagent can open the image itself via its `read` tool, plus a behaviour rule
   that says *use the given path before claiming no image exists*.
2. Router/AGENTS rule for T05: always embed `Caminho da imagem: <absoluto>` in
   the task prompt; never delegate `explore` to "find" a screenshot; ask for the
   path when missing instead of guessing. Regression encodes *exactly* `["read"]`
   allowed on `ver`.

Same lesson as T04, migrated across modality boundaries: **whoever owns the
input owns passing it to the expert.**

### T05, round 2: `attachment: true` is not enough — the model needs `modalities`

Refinement of sec. 15, driven by two smokes in the same session:

1. **21:11 — false positive.** After the `read` fix shipped, a smoke appeared to
   pass, but the model described "text in a sans-serif font" that does not exist
   in the test image — it answered from the prompt without ever calling `read`
   (zero tool calls). The con here was not a paranoid model; it was the primary
   trusting a plausible-sounding description. Vision smoke checks must match
   description to actual image content.
2. **21:41 — the real gate.** After restart, `ver` correctly called `read`, the
   tool returned the image, yet the model received `Cannot read image (this model
   does not support image input)`. The same error hits the non-multimodal primary
   on a PNG, so the gate is in opencode, not ollama: direct calls to `vision`
   (native + OpenAI-compatible `/v1/chat/completions`) describe the knight image
   correctly.

Tracing the opencode binary (v1.18.29) showed the capability derivation for
config-defined models: `input.image = k.modalities?.input?.includes("image") ?? provider.image ?? false`. **`attachment: true` does not set `input.image`** —
a custom model needs `modalities`. And the V1 schema (`packages/core
v1/config/provider.ts`) wants `modalities` as an **object**
`{input:[...], output:[...]}`, not an array; the compact `lower()` in
`config/v2-compat.ts` deliberately ignores provider models, so no auto-conversion.
First attempt used the array form (invalid); the shipped shape is:

```jsonc
"vision": {
  "name": "Qwen3-VL 8B (visão)",
  "attachment": true,
  "modalities": { "input": ["text", "image"], "output": ["text"] }
}
```

Regression now fails if `vision.modalities` is not this object shape (section 4),
so a silent revert breaks CI instead of quietly disabling vision. **Outstanding:**
confirm the end-to-end T05 smoke after a restart with these modalities live, and
verify whether opencode hot-reloads provider config (safer to just restart).

### T05, round 3: path-with-space is a parser trap; the multimodal primary is a trap too

After the modalities fix, the real smoke ("Analisando imagem de cavaleiro",
2026-09-15) taught two things that were added to the rules:

1. The `vision` model *can* now see images end-to-end (the fix worked), but the
   session that finally succeeded ran the image **through a fresh `ver` sub-
   session** (~36 s via `read` on the exact path). When the *primary* ran on
   `vision` and tried to analyze the image directly, opencode hit "exceeded the
   provider's size limit due to large media attachments", then entered a retry
   loop of 0-token responses (`finish: unknown`), and finally the model started
   hallucinating paths (`/src/index.ts`, `/src/`, an `explore` hunt) while the
   real path sat in the conversation. Conclusion written into the router iron
   rule: **T05 always delegates — a multimodal primary must not analyze images
   itself.**
2. The user had to quote `/home/rodmb188/Imagens/Capturas de tela/Teste.png` for
   it to be honored — the unquoted space path was being re-parsed. But a direct
   test showed `read` *accepts* the space path in full; the failure was the
   primary/parser splitting it. Rule added: transfer paths **verbatim**
   (preserve quotes, never "fix" spaces into `/src/...`). Same guidance embedded
   in `ver.md`, `SKILL.md` rule 6 + protocol 7, `config/AGENTS.md`, README, and
   the regression `ver` smoke entry.

### T05, round 4: five real photos — the model out-scored its own ground truth

First real-world challenge after secs. 15–17: five photos from the user's camera
roll, one question each, verified against the user's expectations.

| Photo | Question | `ver` answer | Verdict |
|---|---|---|---|
| `Família.jpg` | How many people? | 4 | ✅ |
| `André jóia.jpg` | What is on André's face? | black fabric mask | ✅ (the first framing, "what is André wearing?", answered about clothing — asking *on the face* is required for facial items) |
| `Carro alegórico.jpg` | Describe the person | blue shirt, white medical mask, flower lei + crown, stylized carnival mask (orange/purple/gold) | ✅ (the carnival mask matches the user's "stack of carnival glasses" — accepted) |
| `Última foto.jpg` | How many people, and what's on each face? | **8 people: 4 masked (black, white surgical, pink, green) + 4 unmasked** | ✅ (the user's original ground truth said "4 people"; the model's count was the correct one) |
| `Eu no sítio.png` | Describe | health bar bottom-left + "virtual/nature" scene, read as a game screenshot | ✅ (user confirmed the reading was exactly right) |

**Reading:** **5/5 fully correct.** The two "failures" of earlier rounds did not
recur. Two standouts: the 8-people count — the evaluator's own expectation was
wrong, the model was right — and the sítio photo, initially graded as partial by
the router, which the user then confirmed as spot-on (the health-bar + virtual
scene reading was the correct one).

**Context sizing — the 12k vs 16k question.** A 12 MP photo (4608×3456)
tokenizes to **≈8,520 tokens**. With the `ver` system prompt (~0.8k), the
question and the answer, a single turn lands at **≈9.6–10.1k**. `num_ctx 8192`
overflowed (`exceed_context_size_error`); the model was recreated with
**16384** and validated across all five photos. 12288 would fit the single-turn
case (~2.5k of headroom) but leaves no margin for a same-session follow-up or a
denser image; the 4k extra tokens of KV cache cost ~1.5 GB RAM, which this box
has. **Decision: `vision` stays at 16384** (see `models/vision.Modelfile`).

Also re-validated: paths with spaces passed **verbatim and unquoted** work — the
quoting requirement from sec. 17 was a parser artifact of the primary, not of
`read`; extensions can be omitted since the agent opens the exact path. This
closes the "outstanding" from sec. 16 (live end-to-end smoke after restart).

### T05, round 5: a default directory so the user stops typing paths

Every T05 request so far required the absolute path in the prompt. The user
asked for a default: when no path is given, `ver` checks
`/home/rodmb188/Imagens/Análise IA/` first and only reports failure after
actually looking there (folder name as proposed, kept — spaces are fine, the
verbatim rule covers them).

Implementation, applied to every layer that carries the T05 rule:

- `ver.md`: `list: allow` (tool pair becomes exactly `list` + `read`). Behaviour
  rule: use `list` *only* on the default directory, never hunt elsewhere; one
  image → `read` it, several → list the names and ask which, empty/missing →
  say so and request the exact path; never invent filenames or variants.
- Router (`SKILL.md` rule 6 + protocol 7) and `config/AGENTS.md` (repo + live
  copy): when the user gives no path, embed
  `Caminho padrão: /home/rodmb188/Imagens/Análise IA/` in the `ver` prompt
  instead of asking the user upfront; ask the user only if `ver` reports the
  folder empty. The `explore` prohibition is untouched — this is `ver`'s own
  `list` on one fixed directory, not a hunt.
- Regression (`regressao.py`): `ver` permission must be exactly
  `["list", "read"]`, the default-directory string must appear in `ver.md` and
  `SKILL.md`, and a new smoke entry covers the empty-folder path (must warn and
  ask, never invent).

Live check with the empty folder behaved correctly: `ver` read the default
directory, reported it empty, and asked for the exact path — no phantom
filenames. One slip caught and hardened into the rule: it offered a fabricated
"Caminho alternativo: /home/rodmb188/Imagens/Capturas de tela/" as if it
existed. The behaviour rule now explicitly forbids suggesting alternative paths
the user never mentioned; checking the folder (or not) is the difference between
helping and hallucinating.

### T16 r1 — roadmap (fase A) and a canonical context budget (C4)

The user hit "done building, no direction" and asked for a flowchart + goals
before continuing. `planner` produced the full map (flowchart, 3-horizon goals,
4 strategic scenarios, risks) and the router audited it against the real
constraints of this stack — two corrections went in before versioning:

1. **C1 (CI) reformulated**: `opencode run` headless still hangs on this box
   (sec. 14), so "20 levels green in CI" is impossible today. Realistic CI =
   full static layer on GitHub Actions + model checks via Ollama directly
   (no TUI) + a versioned manual live checklist.
2. **C2 does not depend on CI** — it is a 5-minute manual test with a real
   image in the default directory.

Decision: **Fase A — Consolidar**, order **A → D → B → C** (publish before
consolidating = technical debt).

- `docs/ROADMAP.md` created (commit `d27b92d`): flowchart, C1–C4 / M1–M4 /
  L1–L4 with done-when criteria, scenarios, risks, first step.
- **C4 done**: `docs/CONTEXT_BUDGET.md` — canonical measured table:
  qwen3-local (14B) **8192**, nothink-v2/megabrain-v2 (27B) **12288**,
  vision (8B VL) **16384**; embed caps (~5k / ~4k / 1 image per turn); overflow
  behaviour (27B empty = `reason: length` → never retry, chunk instead; vision
  8192 → 16384 fix); KV cost ≈ 384 KB/token (~1.5 GB per 4k). The 14B cap is
  an estimate flagged for M2 profiling.
- Iron rule updated in `config/AGENTS.md` + live copy: CONTEXT_BUDGET is the
  single source for context limits — update the doc before committing a
  Modelfile change.

### T16 r2 — C2 done, language rule reinforced fleet-wide, character-count sanity

Live C2 test with two real images in the default directory (2026-09-17):

- **Flow check**: `ver` with no path listed both files verbatim (`Casa.png`,
  `Homem.png`) and asked which to analyze — the "several → ask" branch of the
  T05 protocol works live.
- **Identification (not description)** — user's framing: "identify what it
  sees, don't describe it". `Homem.png` → **Luiz Inácio Lula da Silva,
  confidence high** (facial features, dark suit, green/yellow/blue striped
  tie, green backdrop) — a named identification, above the user's own
  expectation. `Casa.png` → **isometric 2D survival game** (style: high,
  genre: medium; blood, weapons, supplies, no HUD); the title was honestly
  not recognized (low confidence, Rust/TLoU considered and rejected as
  imperfect matches). The user had expected no identification at all.

Fleet-wide rule reinforcement (requested after the user saw the planner's
stray CJK output and a 200-char creativity test drift into English thinking):

- **Language**: every one of the 18 agents must think AND answer in pt-BR;
  foreign traces (CJK/Latin/English) fail the delivery. Added a canonical
  block to all `agent/*.md` and strengthened the iron rule in `AGENTS.md`
  (repo + live copy).
- **Character-count sanity**: "N characters" requests are answered on the
  FIRST attempt with a small margin (±5% or ±10 chars, whichever is larger),
  reporting the exact count alongside, with no endless rewrites — the user
  decides whether to accept. Root cause of the request: a simple 200-char
  creativity answer took 20+ minutes of silent rewriting (201 vs 198 chars).
- Verified `docs/ROADMAP.md` / `docs/CONTEXT_BUDGET.md` contain **no real
  CJK** — the planner's leaked character was display-output only, already
  sanitized in the saved file.

### T16 r3 — progress bar removed (user decision after analysing its saga)

The user reviewed the other conversation ("Notificação quando resposta
termina", 577 messages: 39 user turns, 475 assistant, 9 compactions) — it ran
from "I stopped getting end-of-response notifications" into a long progress-bar
campaign: repeated "Invalid V2 TUI plugin module" load errors, an
investigation into the compiled Bun single-file binary, plugin reconciliations
after two opencode updates, esbuild via npx — and the bar still never rendered
reliably. Decision: **remove the progress bar entirely**.

- Runtime: `~/.config/opencode/plugins/progress/` deleted; `tui.json` cleared
  of its entrypoint reference (`plugin: []`) — no more load errors on startup,
  no more phantom entries.
- Repo: `benchmarks/regressao.py` — removed the static section 5 (plugin
  checks), the `live_plugin_check()` function and its call, and the
  `barra-progresso` smoke entry. Regression is green again.
- The end-of-response *notification* (the conversation's original request)
  was deliberately left in place — only the bar was removed.

### T16 r4 — C1 done: CI in three layers, plus a real finding from the new check

C1 (fase A) implemented and validated live:

- **C1a (static)**: `rota-ci.yml` already ran `regressao.py` on every push —
  added the parity check (seção 6): each `models/*.Modelfile` `num_ctx` must
  match `docs/CONTEXT_BUDGET.md`, with `FROM` inheritance respected
  (megabrain-v2 → 12288 from nothink-v2). CI badge added to the README.
- **C1b (model sanity, headless)**: new `benchmarks/model_checks.py` calls
  Ollama directly via `/api/generate` — no TUI, no opencode. The first run
  FAILED instructively: `num_predict: 64` cut inside the Qwen3 family's hidden
  thinking, so the final response never arrived (qwen3-local returned empty);
  bumped to 1024 → **both PASS**: qwen3-local `17 × 23 → 391` (27.4 s),
  nothink-v2 translation contains "bom dia" (88.4 s). All four models verified
  present via `/api/tags`. megabrain-v2 (thinking ON, minutes) and vision
  (needs an image) stay in the manual live checklist by design.
- **Runs only locally** (honest scope): the GitHub runner has no Ollama and no
  models — static checks live in Actions; model checks live on this box.
- **Finding (matches the user's own report)**: `nothink-v2` called raw emits
  its reasoning as visible English text ("Here's a thinking process: …") —
  the model has no qwen3 RENDERER/PARSER or suppressing chat template, so it
  "thinks out loud". This is the same symptom the user saw in the 200-char
  creativity test (started thinking in pt-BR, drifted to English, answered in
  pt-BR). Not fixed here; the router's pt-BR sanity rule mitigates
  presentation. A real fix would be a `nothink-v3` with qwen3 PARSER that
  strips the thinking block (or a template that disables it) — parked in the
  roadmap as a future finding.

### T16 r5 — full smoke: all 18 agents live (first complete run, 2026-09-17)

First time every sub-agent was exercised in one session (leves in parallel,
27B strictly sequential — iron rule). One green-wave of 7 + 11 sequential:

| agent | prompt | result |
|---|---|---|
| preciso | 17×23 | ✅ 391 |
| financeiro | R$1.200/6x | ✅ R$ 200,00 |
| revisor | grammar fix | ✅ "Nós vamos amanhã para a festa." |
| qa | 10% of R$1.500 | ✅ "sim" — ⚠ CJK first token (润色后) + English reasoning in output |
| importador | JSON→CSV | ✅ empty city preserved (`""`) |
| dados | mean of 4 numbers | ✅ 25 |
| pesquisa | verdict on embedded material | ✅ Y cheaper by R$ 600 |
| codigo | fix `a - b` | ✅ `a + b` (added unprompted "Resumo:" tail) |
| redator | slogan ≤6 words | ✅ "Feito à mão, servido com alma." |
| sumarizador | 1-sentence summary | ✅ faithful |
| tutor | variable analogy | ✅ labeled box |
| tradutor | pt→en | ✅ "The black cat slept." |
| sysadmin | disk command | ✅ `df -h` |
| seo (1st) | meta description | ❌ answered with only a "Resumo:" — no meta |
| seo (retry, harder phrasing) | same | ✅ meta, 152 chars + count — ⚠ CJK first token (分步骤思考) |
| entrevistador | STAR question | ✅ — ⚠ "opinion" for "opinião" |
| planner | 3 steps for v1.0 | ✅ coherent with L2 goals |
| profundo | 27B parallel risk | ✅ swap/OOM-kill, 14–16 GB each |
| ver | identify Homem.png | ✅ Lula da Silva, 95% confidence |

Reading: **18/18 functional** — no arithmetic, link or hallucination failures.
Two findings:

1. The CJK first-token decode artifact still shows up on the qwen3 family
   (qa, seo): the primary-side sanitization rule (SKILL rule 4) remains
   required; the pt-BR reinforcement reduces but does not eliminate it.
2. **Sub-agents read the global AGENTS.md and copy the "Resumo:" rule** —
   codigo, redator, seo and profundo appended an unprompted summary, and
   seo's first attempt answered *only* the summary (format instead of
   deliverable). Suggest scoping the mandatory-summary rule to the main
   assistant only — pending user decision.