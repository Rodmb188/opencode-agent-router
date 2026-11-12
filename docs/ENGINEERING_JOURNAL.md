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

### T16 r6 — language rule hardened to maximum, plus `ver` factuality guard

The user audited the T16 r5 smoke outputs and found stray CJK tokens beyond
the two flagged ones: `preciso` (颗), `financeiro` (颗), `revisor`
(字词句修正如下), `qa` (润色后 + English reasoning), `seo` (丄 then a full
Chinese thinking block), and a **factual error** from `ver`: it called Lula
"ex-presidente" — he is the sitting president since 2023. Actions taken:

- **Fleet-wide language block rewritten (all 18 `agent/*.md`)**: "rigor máximo"
  — every output in pt-BR latin-only (reasoning included); mandatory
  self-review of the FULL output (start, middle, end) before finishing; drop a
  stray first token and restart; no thinking in English/Chinese.
- **`config/AGENTS.md` + live copy**: the iron rule now demands the primary
  **inspect the complete sub-agent output and sanitize everything** before
  showing — never pass through foreign characters; documents the exact leaked
  tokens from T16 r5.
- **`ver.md`**: new factuality guard — identify the person from the image, but
  never assert current/former public office with certainty without image
  support (office is external context that changes); prefer "figura pública
  brasileira" or flag "confirme a atualidade".
- **Regression**: new static check (seção 7) — every one of the 18 agents must
  contain the "## Regras reforçadas de idioma" block, so a future agent can't
  ship without it. Regression green (EXIT=0).

Honest expectation (kept in the rules): the CJK first-token artefact is a
decode-level property of the qwen3 family — instruction hardening reduces how
often it surfaces and guarantees the handler cleans it, but the primary-side
sanitization (SKILL rule 4) remains the last line of defense. Factual time
context (Lula) is a knowledge-cut limitation, mitigated by the new guard.

### T16 r7 — standard test-log + B01 re-run (prompt hardening is not a cure)

Two deliverables this round:

1. **Standard test-log format** (user's idea: stop scattering tests across
   dozens of conversations). New `benchmarks/results/README.md` indexes the
   batteries; each battery is one file
   `baterias/B0X_<goal>_<date>.md` with header (date, rules in force, models,
   goal) and, per test: sequential number, agent, verbatim prompt, verbatim
   answer, artifact note and verdict. Legacy outputs stay linked as
   "legado". B01 = full 18-agent smoke re-run after T16 r6.

2. **B01 result: 16 PASS, 1 partial, 1 FAIL.** Language-rule hardening did
   **not** eliminate the decode artefact — 6/18 answers carried a vestige
   (r5 had 5): `preciso` diacritic + English reasoning; `revisor` a whole
   Chinese reasoning block **and** a wrong correction (the sole FAIL);
   `qa`/`dados` stray CJK first token + English; `pesquisa` CJK mid-text;
   `seo` Chinese thinking. Primary-side sanitization remains the only
   guarantee of a clean delivery — which strengthens the parked case for a
   structural fix (`nothink-v3`: thinking parser or thinking disabled).

   Other findings:
   - **`ver` guard works** (no office asserted — the r5 "ex-presidente" is
     fixed) but the model stopped naming the person at all; needs calibration
     to name + not assert office.
   - **New:** `seo` miscounted characters — reported 143, real count 82 (the
     primary reconfirmed). LLM character counting is unreliable by nature; the
     good-sense rule (primary reconfirms) is what saves it.
   - **"Resumo:" tail** reappeared in 6 agents (codigo, importador, pesquisa,
     tutor, planner, ver) — the r5 inheritance finding is still open, pending
     user decision on scoping the mandatory summary to the main assistant.

Data: `benchmarks/results/baterias/B01_smoke18_pos-endurecimento_2026-09-17.md`.

### T16 r8 — user review of B01: scope resumo, remove decoys, fix ver/seo/revisor

The user read the B01 raw outputs and made a sharp architectural point: if the
main assistant must sanitize every sub-agent answer, the local-model premise
is weakened. That framing is right — the primary sanitization is a **safety
net, not the solution**; the real fix is deterministic and local (a parser
that strips the reasoning block / disables thinking at the source, i.e. the
parked `nothink-v3`). Prompt hardening is now proven insufficient by B01.
Decisions implemented:

1. **`Resumo:` scoped to the main assistant** — the mandatory-summary iron
   rule in the global `AGENTS.md` (runtime + repo copy) now says explicitly
   that **sub-agents must NOT add "Resumo:"** or any unprompted summary; the
   rule belongs to the primary only. This is the fix for the tail reappearing
   in 6 agents. (The rule lived only in the runtime AGENTS.md, which is why
   the sub-agents inherited it; the repo copy now carries the scoped version
   too, restoring parity.)
2. **Removed the CJK literals from the rule texts** (all 18 `agent/*.md` and
   both AGENTS.md). Insight: listing the leaked glyphs inside the prompt is
   *priming* — it can raise the very leakage it warns against. Stray examples
   were also found and scrubbed from `preciso.md`, `profundo.md` and
   `revisor.md`; `agent/` now has zero foreign literals. History/evidence
   files (journal, old dogfood/battery logs) were left as-is: they are not
   loaded into any agent prompt.
3. **`ver.md` — identification is the job** (B01/T18): name the person/object
   with a confidence level; do not withhold the name out of caution (in B01
   it only described clothes and failed the actual question). Office/vínculo
   may not be asserted; if the task needs external judgment (current office,
   changing data), the `ver` returns description + identification and the
   primary routes the interpretation to `pesquisa`/`preciso`/`profundo`.
   Same routing note added to the T05 iron rule in both AGENTS.md.
4. **`seo.md` — counting rule** (B01/T14): never estimate; count one by one.
   Spaces count (Google's meta-description convention); if the ask defines a
   different convention, follow it and say which was used. Note: the reported
   143 vs the real 82 was **not** a space miscount (space-free it still could
   not reach 143) — it was a fabricated number.
5. **`revisor.md` — mandatory final self-review** (B01/T03): re-read your own
   correction and confirm the final sentence has none of the errors you were
   supposed to fix; if unsure about a rule, don't invent — flag it.

Regression green (EXIT=0); all 18 agents carry the language block.
## T16 r11 — nothink-v3: parser determinístico global ENTREGUE e 3/3 PASS
(2026-09-19 · B02 preparatório)

**Decisão do usuário (r9): parser GLOBAL (todos os agentes com thinking),
não recorte de um "trio CJK" fixo.** Motivos registrados:
- Não existe trio canônico estável: os vazamentos alternaram entre agentes
  a cada rodada (r5: preciso, financeiro, revisor, qa, seo; B01 r6:
  revisor, seo, qa, dados, pesquisa...). "Os 3" não é uma lista determinável;
  parser global elimina a necessidade de saber quais são.
- Parser global = mesma infra de parser em 3, mas sem buracos.

**Entrega: `benchmarks/nothink_parser.py`** — sanitização determinística,
100% local, SEM dependência de provider/modelo:
- `sanitize()` → filtra por característica Unicode: mantém only latin
  (ASCII + Latin-1 + Latin Extended-A com acentos pt-BR), espaços e os
  símbolos comuns (%, $, #...). Remove qual Err (CJK, kana, cirílico etc.)
  por bloco Unicode — a MESMA rede que os agentes usam, agora como função
  reutilizável.
- `corta_bloco_rascunho()` → remove bloco de raciocínio marcado
  (marcadores padrão: <thinking>, RASCUNHO, Raciocínio:) quando presente.
- CLI: `python3 benchmarks/nothink_parser.py` (sanitiza stdin → stdout) e
  `--self-test`.
- Self-test embutido verifica 3 cenários; **3/3 PASS** (r11 corrigiu o
  único falso negativo: o literal `cenario_limpo` tinha `%%` herdado de
  heredoc, não o parser — o teste agora testa o que pretendia).

**Escopo do parser vs. passo a passo (pergunta do usuário respondida):**
- O parser corta o RASCUNHO (raciocínio interno), NÃO a resposta final.
  O passo a passo das contas deve viver na RESPOSTA final (é ali que o
  usuário lê), não no raciocínio — isso é regra de entrega, não de charset.
- O parser preserva integralmente o texto limpo (ver self-test cenario_limpo:
  "Taxa de 5%... R$ 210." passa intacto).
- Portanto: parser global NÃO compromete o passo a passo das contas; o que
  é comprometido — e resolvido — é o vazamento de rascunho em charset.

**Duas camadas possíveis de aplicação (documentado, decisão final do
usuário em aberto):**
1. Parser na saída do primário (meu lado): eu recebo a resposta crua do
   subagente e aplico `sanitize()` de forma mecânica antes de entregar.
   → eu TENHO acesso ao rascunho (vejo para cortar), não "penso" nele.
2. Parser na fonte (proxy local entre Ollama e opencode, tipo nothink na
   origem): o bloco é cortado ANTES de chegar ao opencode.
   → nem o primário veria o rascunho; sanitização do primário vira só
   garantia redundante.

**ICA / regra de idioma segue reforçada** (independente do parser, que é
rede): AGENTS.md e os 18 agentes continuam exigindo pt-BR latino do
subagente; parser é a rede estrutural, sanitização é a rede de segurança.

**Próximo passo (proposto):** B02 — bateria de validação cruzada rodando
todos os 18 agentes com `notthink-v3` (parser global) como provider apontando
para o parser (camada 2 via proxy local ou camada 1 via sanitização no
primário). A decisão de rodar camada 1 ou 2 é do usuário quando quiser B02.

**Arquivos tocados nesta revisão:**
- benchmarks/nothink_parser.py (criado; parser 100% local determinístico)
- benchmarks/README.md (índice da bateria) — se aplicável
- benchmarks/results/baterias/B02_... (quando B02 rodar)
- docs/ENGINEERING_JOURNAL.md (este registro)


## r12 — proxy B02: corte-na-fonte validado (drift da def local eliminado)

**Decisão do usuário**: plugar o proxy local (corte na fonte, antes de chegar ao
primário). Historico: parser determinístico global (r11, notchink_global 3/3).

**O que foi feito** (benchmarks/nothink_proxy.py):
1. Proxy HTTP local (11436 -> 11434, ThreadingHTTPServer, stdlib pura) que
   repassa /api/chat ao Ollama com stream=False e aplica o sanitize DENTRO do
   objeto de resposta (fonte única = nothink_parser.sanitize).
2. Self-test determinístico (cenarios gerados em runtime via chr, sem literal
   estrangeiro no fonte): 3/3 PASS.
3. **Bug real encontrado e corrigido**: o proxy tinha `def sanitize` LOCAL que
   sobrescrevia o import (drift de cópia — o mesmo problema que critiquei na
   arq). Removida a def local; fonte única = import. Proxy 3/3 + parser 3/3.

**O que falta (decisão do usuário)**: plugar o proxy no provider do opencode
(baseURL -> http://127.0.0.1:11436) para que o corte aconteça na fonte — nem o
primário veria o rascunho. É mudança de runtime do provider, não feita nesta
rodada (decisão dele).

## r13 — achado `message.thinking`: o rascunho passaria INTACTO pela fonte
(2026-09-20 · sessão "Roteador Local - Fase B", commit `6ebd77f`)

**Contexto**: sessão nova iniciada com o handoff para executar o B02 (r12) com
backup + rollback. Durante a validação do repasse real (proxy 11436 → 11434 com
qwen3-local), o teste imprimiu o JSON cru do Ollama e revelou um vazamento que o
self-test 3/3 não cobria:

- O Ollama devolve o raciocínio em **campo separado `message.thinking`** (em
  inglês), fora do `content`.
- O proxy r12 só sanitizava `message.content` → **o rascunho sairia da fonte
  INTACTO**, exatamente o vazamento que o B02 existe para cortar.
- O achado só apareceu no teste real: os self-tests 3/3 usavam `content` apenas.

**Correção aplicada** (`benchmarks/nothink_proxy.py`):
- `sanitize_stream_resposta` remove `thinking` e `thinking_duration` do objeto
  `message` em bloco (o rascunho não é sanitizado — é eliminado na fonte).
- Self-test ampliado para 4 cenários, incluindo `message.thinking` com CJK:
  **4/4 PASS** (determinístico).

**Kit de rollback** (`benchmarks/rollback/`): criado antes de qualquer plug —
`opencode.jsonc.bak-20260920-055511` + `README.md` com o comando único de
restauração. O plug em si NÃO foi feito (a sessão colapsou antes; ver abaixo).

**Sessão Fase B colapsou no fim (roteiro do looping, repetido)**: após os testes
de repasse, o contexto da sessão acumulou a saída crua gigante do `thinking` do
qwen3 (milhares de tokens) + JSONs + logs. Logo em seguida o reasoning do
primário degenerou em repetição (37k → 44k chars de lixo em uma só
resposta), o stream ficou longo demais e o provider cortou sem `finish_reason`
(`provider.invalid-output`), com o opencode emendando retries sintéticos. Mesmo
padrão da Fase A (31× o mesmo erro, sem proxy). Observado:
- O proxy em si é inerte enquanto nada aponta para a porta 11436 — não é a
  causa de rede; o gatilho foi a **poluição do contexto da sessão** durante o
  trabalho de implementação.
- Consequência prática: **manter as sessões do primário curtas e o contexto
  limpo**; executar validação pesada (repasse real, JSON cru) fora da sessão do
  primário ou com saída truncada.

**Lições para o B02 (forma positiva):**
- Executar o plug em sessão curta e de escopo mínimo (backup → apontar
  `baseURL` → validar → rollback se preciso), evitando despejar saídas grandes
  no contexto do primário.
- O kit de rollback já está pronto; o achado r13 torna o corte-na-fonte
  efetivamente completo (sem ele, o plug seria inútil).

**Arquivos tocados:**
- benchmarks/nothink_proxy.py (editado; achado r13 — commit `6ebd77f`)
- benchmarks/rollback/ (criado: README.md + backup da config)
- docs/ROADMAP.md e docs/ENGINEERING_JOURNAL.md (registros)

## r14 — plug do B02 APLICADO e validado (endpoint OpenAI + script seguro)
(2026-09-20 · commit `b6810db`)

**Bloqueio encontrado na execução**: o package `@ai-sdk/ollama` (formato nativo
do Ollama) **não existe no registry npm** — `404 Not Found` na inicialização do
provider. Confirmado via registry: `@ai-sdk/ollama` → 404; `ollama-ai-provider`
→ 200; `@ai-sdk/openai-compatible` → 200 (o pacote em uso há meses).

**Decisão (rota mais robusta)**: sem dependência nova — o proxy passa a falar o
**formato OpenAI** (`/v1/chat/completions`), traduzindo para o `/api/chat`
nativo do Ollama e devolvendo no formato que o `@ai-sdk/openai-compatible`
já consome (JSON e SSE com `[DONE]`). O rascunho (`thinking`) é descartado por
construção na tradução: só o `content` sanitizado é levado para a resposta
OpenAI. Self-test ampliado para **7/7 PASS** (inclui tradução OpenAI→Ollama,
Ollama→OpenAI sem thinking e SSE completo).

**Entrega do plug**: `benchmarks/b02_plug.sh` (prévia / `--executar` /
`--rollback`), com backup antes de tocar a config, rollback automático em
qualquer falha e validação em 4 frentes + o caminho real do SDK:
1. `/api/chat` (curl): content presente, thinking ausente ✅
2. `/v1/chat/completions` JSON (curl): choices[0].message.content ✅, thinking ausente ✅
3. `/v1/chat/completions` SSE (curl): `data:` no início e `[DONE]` no fim ✅
4. `opencode run --model ollama-nothink/qwen3-local "Responda apenas com a palavra ok"` → **"ok" limpo** ✅

**Estado do plug**: config `~/.config/opencode/opencode.jsonc` ganhou o provider
`ollama-nothink` (npm `@ai-sdk/openai-compatible`, baseURL
`http://127.0.0.1:11436/v1`), proxy rodando na 11436 com log em
`/tmp/opencode/proxy.log`, rollback em 1 comando guardado na saída da execução.
Cadeia inteiramente local (loopback 11436 → 11434); nada sai da máquina.

**O que falta para a rota final do B02**: apontar os agentes com thinking
(profundo, preciso etc. — via AGENTS.md/skills) para `ollama-nothink/...` em vez
de `ollama/...`; hoje o provider novo está plugado e validado, mas as rotas ainda
usam o `ollama` direto. Bateria completa do B02 registrada quando isso rodar.

**Arquivos tocados:**
- benchmarks/nothink_proxy.py (endpoint OpenAI + SSE; self-test 7/7 — `b6810db`)
- benchmarks/b02_plug.sh (novo; plug seguro com prévia/executar/rollback — `b6810db`)
- docs/ROADMAP.md e docs/ENGINEERING_JOURNAL.md (registros)

## r15 — B02 FECHADO: rota final dos 18 agentes pelo proxy (corte na fonte ativo)
(2026-09-20 · sessão iniciada pelo handoff · commit a definir)

**Objetivo**: o passo que faltava do B02 — apontar os agentes locais para
`ollama-nothink` para o corte na fonte valer nas rotas reais. Decisão do usuário
no arranque: **todos os 18 agentes** (não só os 8 com thinking), para consistência
total do corte.

**Execução (padrão r13/r14: script pronto com backup + rollback, sessão limpa):**
- Escrito `benchmarks/b02_agents.sh` (prévia / `--executar` / `--rollback`),
  espelhando o `b02_plug.sh`: pré-checagem (Ollama, proxy respondendo content sem
  `thinking`, provider na config), backup do diretório de agentes, troca
  `sed 's|^model: ollama/|model: ollama-nothink/|'` nos 18 `agent/*.md`,
  validação estática e relatório com rollback em 1 comando.
- **Prévia**: 18 arquivos listados com linha antiga → linha nova (nada alterado).
- **--executar**: backup em `~/.config/opencode/agent.bak-b02-20260920-073241`,
  troca aplicada; validação estática: 18 em `ollama-nothink/` · 0 em `ollama/`.
- **Bug corrigido na hora**: o `grep | wc -l` com `pipefail` abortava o script
  quando o grep não achava match (exit 1 do grep) — acrescentado `|| true`.

**Validação real (bateria B02, `benchmarks/results/baterias/`):**
- 4 modelos via SDK pelo provider novo: `qwen3-local`, `vision`, `nothink-v2`
  (27B) e **`megabrain-v2` (27B com thinking ON)** → todos responderam "ok"
  limpo. O megabrain-v2 é a prova do corte: pensa e não vaza nenhum rascunho.
- Subagente real `preciso` via task (ponta a ponta pelo frontmatter trocado):
  "Quanto é 15% de 240?" → `**Resposta: 36**` ✅.
- Log do proxy: **0 ocorrências de `"thinking"`** após todos os testes.

**Achado (registrado na bateria B02)**: `opencode run --agent <nome>` NÃO
exercita o modelo do frontmatter de subagent — a sessão run usa o modelo
principal da config; 14 dos 18 smokes via CLI deram
"OpenCode's free tier can only be used from within OpenCode" (provider open-code
fora da interface) e 4 responderam com o título do modelo principal da sessão. O
caminho real do subagent é a chamada via task dentro de uma sessão (como no
teste do `preciso`). Lição: **validação de rota de subagent = task em sessão,
não `opencode run --agent`**.

**Estado final do B02:** plug (r14) + rota final (r15) aplicados; corte na fonte
ativo nas rotas reais; rollback em 1 comando para cada peça (config e agentes);
bateria B02 no padrão do índice. Próximos blocos: **M1** (camada 7B) ou **M2**
(profiling).

**Arquivos tocados:**
- benchmarks/b02_agents.sh (novo; troca de rotas com prévia/executar/rollback)
- benchmarks/results/baterias/B02_rota-final-proxy_2026-09-20.md (novo)
- benchmarks/results/README.md (índice com B02)
- docs/ROADMAP.md (status, fluxograma e próximo passo atualizados)
- docs/ENGINEERING_JOURNAL.md (este registro)
- config/opencode.jsonc (provider `ollama-nothink` espelhado na doc do repo)
- config/AGENTS.md e skills/roteador/SKILL.md (nota: rotas passam pelo proxy)
- benchmarks/rollback/README.md (rollback dos agentes adicionado ao kit)
- Fora do repo: `~/.config/opencode/agent/*.md` × 18 (rotas trocadas) + backup
  `~/.config/opencode/agent.bak-b02-20260920-073241`

## r16 — achado raiz do vazamento residual + B03 (proxy com tools, tool_calls e imagens)

(2026-09-20 → 2026-09-21 · sessão iniciada pelo handoff do r15 · commit a definir)

**Objetivo**: executar a B03 (smoke dos 18 pela rota final do B02, mesmos prompts
da B01) e, ao comparar, descobrir e corrigir a causa raiz do vazamento residual
que persistia mesmo com o corte na fonte.

**Causa raiz do vazamento (achado principal):**
- `traduz_oai_para_ollama` **descartava os `tools` do request do SDK**. Sem
  tools, o qwen3 emite o raciocínio **inline no content** (inglês/chinese) em vez
  do campo `thinking` — e o corte do `thinking` na fonte não pega inline.
- Evidências: pior caso system grande + sem tools = inline em 4/4; com tools =
  inline em 4/10; user-only = 8/8 limpo; `think: true` forçado sem efeito;
  alucinações CJK do dataset (resíduos U+9897, U+0308, diacríticos no content).
- Fix: repassar `tools`/`tool_choice` na ida, normalizar `tool_calls` no formato
  OpenAI na volta (id/type/arguments string, SSE com chunk dedicado), remover
  `<tool_call>` não-parseado do content e cortar raciocínio inline pelo marcador
  ` response` (regex `(?:^|[ \t\r\n])response[\r\n]`). Self-test 11/11.
- **Limite confirmado**: o corte na fonte funciona para modelos que separam o
  thinking (nothink-v2, megabrain-v2). O qwen3-local (14B) **não separa de forma
  confiável no contexto de agente** — quando emite inline sem o marcador, nada
  corta (evidência na B03: `financeiro` vazou). Mitigação (trocar leves por
  nothink-v2 / aceitar sanitização do primário / mexer no Modelfile) fica para
  decisão do usuário.

**Fix novo descoberto DURANTE a B03 (r16b):**
- O subagent `ver` quebrava em 502 no 2º turno (imagem voltando via tool result).
  Duas causas em `traduz_oai_para_ollama`: (1) o SDK manda imagens como
  `content` em LISTA de parts `image_url` e o `/api/chat` nativo só aceita
  content string + campo `images` (base64 sem prefixo data:); (2) `tool_calls`
  de histórico chegam com `arguments` em string JSON (formato OpenAI) e o Ollama
  nativo só aceita OBJETO. Corrigido com `_converte_content_parts` + `json.loads`
  nos arguments; self-test 12/12 → 14/14. Depois do fix, o `ver` identificou
  "Luiz Inácio Lula da Silva" (na B01 só descrevia sem nomear).

**Execução da B03** (`benchmarks/results/baterias/B03_smoke18_rota-nothink-r16_2026-09-21.md`):
- Onda 1 (qwen3-local): preciso ✅ limpo (corte inline funcionou) · financeiro ❌
  (vazou inline — regressão da B01) · revisor ❌ (vazou + não corrigiu) · qa ✅
  com artefato (retry) · importador ✅ (retry após 502) · dados ✅ limpo · seo ⚠
  (contagem 155 informada, real 129).
- Onda 2 (nothink-v2, sequencial): pesquisa ✅ · codigo ✅ · redator ⚠ (7 palavras,
  limite 6) · sumarizador ✅ · tutor ✅ (2 typos) · tradutor ✅ · sysadmin ✅ ·
  entrevistador ✅ · planner ✅ — TODOS limpos, sem tail "Resumo:" (na B01
  aparecia em 6 agentes).
- Onda 3 (megabrain-v2, sequencial): profundo ✅ — sem vazamento (B01 tinha 1
  palavra em inglês); 1 typo ("1620 GB" = 16–20).
- Onda 4 (vision, sequencial): ver ✅ — identificou a pessoa (fix r16b); 2× 502
  antes, corrigido na própria bateria.

**Estado:** proxy com os fix r16 (tools) + r16b (imagens/tool_calls) e self-test
14/14; B03 registrada; índice e docs atualizados. Mitigação dos agentes
qwen3-local: **decisão do usuário → trocar tudo para nothink-v2, executada e
validada na B04 (r17 abaixo)**.

**Arquivos tocados:**
- benchmarks/nothink_proxy.py (fix r16: tools/tool_calls/corte inline; fix r16b:
  content parts → images nativo + arguments string → objeto; self-test 14/14)
- benchmarks/results/baterias/B03_smoke18_rota-nothink-r16_2026-09-21.md (novo)
- benchmarks/results/README.md (índice com B03)
- docs/ROADMAP.md (status e próximo passo)
- docs/ENGINEERING_JOURNAL.md (este registro)

## r17 — B04: troca dos 7 leves qwen3-local → nothink-v2 validada (7/7 PASS)

(2026-09-21 · sessão do usuário · commit a definir)

**Objetivo**: decisão do usuário (após a B03): trocar TODOS os leves para
nothink-v2 e rodar uma bateria SÓ com os trocados para comparar com o
qwen3-local; se algo falhasse, identificar o porquê.

**Execução:**
- `benchmarks/b04_leves_nothink.sh` (novo, padrão b02: prévia/executar/rollback)
  trocou os 7 agentes em `qwen3-local` (dados, financeiro, importador, preciso,
  qa, revisor, seo) para `nothink-v2`. Backup: `agent.bak-b04-20260921-005131`;
  validação pós-troca: 0 restantes em qwen3-local · 16 totais em nothink-v2.
- Estado final dos 18: 16 × nothink-v2 · 1 × megabrain-v2 (profundo) · 1 ×
  vision (ver). **A configuração agora é 100% 27B/vision — nada mais roda no
  14B**, o que encerra o problema de raciocínio inline do qwen3 na fonte.

**Bateria B04 (7/7 PASS, sem vazamento):**
- preciso ✅ 391 · **financeiro ✅ R$ 224,00 (FAIL da B03 corrigido)** ·
  **revisor ✅ corrigiu tudo (FAIL desde a B01 corrigido)** · qa ✅ "Sim" ·
  importador ✅ campo vazio (verboso, ressalva) · dados ✅ 25 (1ª tentativa sem
  resposta — ConnectionResetError no log do proxy; retry OK) · seo ✅ meta 149
  reais vs 152 informados (erro de 3, dentro do limite; contagem ainda não
  exata — regra de bom senso mantida).

**Lições registradas:**
- Vazamento de raciocínio na saída: de 4/7 (B03) para 0/7 (B04). O custo é
  latência: cada leve agora demora como um 27B (~1–6 min; na 1ª carga pode
  estourar o timeout do SDK se o modelo descarregar — ver dados T06).
- `seo`/`redator`: a contagem de caracteres/palavras segue não confiável mesmo
  no 27B — o primário reconfere (regra de bom senso).
- Verbosidade do 27B (aumento real de tokens na resposta) é o novo trade-off —
  prompts dos agentes podem exigir achatamento futuro se incomodar.

**Próximos passos possíveis:** M1 (camada 7B) para recuperar velocidade nos
leves com um modelo menor que talvez não tenha o problema do qwen3; M2
(profiling); ou calibrar os prompts dos 7 para reduzir a verbosidade.

**Arquivos tocados:**
- benchmarks/b04_leves_nothink.sh (novo; troca dos leves com prévia/executar/rollback)
- benchmarks/results/baterias/B04_comparativo_leves-nothink_2026-09-21.md (novo)
- benchmarks/results/README.md (índice com B04)
- benchmarks/results/baterias/B03_smoke18_rota-nothink-r16_2026-09-21.md
  (correção: pesquisa/codigo/redator já eram nothink-v2 — não são leves)
- docs/ROADMAP.md (status e próximo passo)
- docs/ENGINEERING_JOURNAL.md (este registro)
- Fora do repo: `~/.config/opencode/agent/*.md` × 7 (modelo trocado) + backup
  `~/.config/opencode/agent.bak-b04-20260921-005131`

---

## r18 — Calibração anti-isca dos 18 agentes (B05)

**Data:** 2026-09-21 · **Bateria:** B05 (18 PASS · 0 FAIL · 0 regressão)

**Contexto:** pedido do usuário — revisar as "leis dos subagentes" para evitar
iscas (regras que citam o comportamento proibido ou os caracteres indesejáveis,
escrita negativa que age como priming). Roteiro aprovado: (1) revisão anti-isca,
(2) bateria M1 de candidatos 7B.

**Diagnóstico (greps em `~/.config/opencode/agent/*.md`):**
- 107 formulações negativas nos 18 frontmatters; exemplos de caracteres
  estrangeiros citados nas regras (preciso, revisor, profundo); bloco "Tom e
  energia" repetia frases proibidas ("Não.", "Não dá", "Não posso") — ensinava o
  que se queria evitar; 7 descriptions diziam "qwen3-local" (falso desde a B04).

**O que foi feito:**
- Reescritos os 18 frontmatters em forma positiva, preservando frontmatter e
  permissions; backup em `~/.config/opencode/agent.bak-b05-antiisca-20260921-014627`.
- Métricas: negações 107 → 39 (todas neutras/fáticas); "nunca/jamais/proibido" → 0;
  caracteres estrangeiros nas regras → 0; "qwen3-local" → 0.
- B05 rodou os MESMOS prompts da B04 (7 leves) e da B03 (demais 11): 18/18 PASS,
  nenhum veredito piorou; 3 melhoraram (redator slogan 7→5 palavras; tutor sem
  typos; planner sem typo "1015"). Teste extra de segurança no sysadmin com a
  regra positiva: entregou o comando destrutivo pedido MAS com dry-run, aviso de
  irreversibilidade e caminho seguro — barreira mantida.
- Contagem de caracteres continua não confiável (seo informou 146, real 141) —
  primário reconfere. 1ª chamada de 27B após descarga segue podendo voltar vazia
  (tradutor) — retry individual resolve.

**Lição:** instrução negativa ("não faça X") coloca X no contexto do modelo;
prescrição positiva ("faça Y mantendo Z") alcança o mesmo controle sem o priming.
Risco residual: prescrições positivas precisam manter a força — a B05 mostrou
que as barreiras de segurança (sysadmin) e de aderência (qa) se mantêm.

**Próximos passos:** M1 (bateria de candidatos 7B com teste anti-vazamento +
acurácia vs nothink-v2 + tempo).

**Arquivos tocados:**
- Fora do repo: `~/.config/opencode/agent/*.md` × 18 (reescritos) + backup
  `~/.config/opencode/agent.bak-b05-antiisca-20260921-014627`
- benchmarks/results/baterias/B05_antiisca_2026-09-21.md (novo)
- benchmarks/results/README.md (índice com B05)

---

## r19 — Ajustes de latência sem tocar no modelo (B06)

**Data:** 2026-09-21 · **Decisão do usuário:** manter 27B (precisão > velocidade);
descartar 7B/M1 como downgrade; otimizar os arredores sem tocar em modelo/agente.

**Contexto descoberto durante o profiling (o que mudou o entendimento):**
- O PC TEM GPU: **AMD Radeon RX 6750 XT 12 GB VRAM** (Vulkan/RADV; `nvidia-smi` não
  existe porque é AMD). O `ollama ps` mostrava "100% GPU" do vision — era a AMD.
- O `nothink-v2` (17 GB) roda em **split 43% CPU / 57% GPU** — não cabe inteiro na
  VRAM de 12 GB; quase metade do modelo calcula na CPU (tráfego PCIe por token).
- Medição: carga fria = **7,2 s** (NVMe rápido, barato); geração quente =
  **~4,2 tok/s** (21 s p/ 88 tokens, 47 s p/ 164). **O gargalo é o eval pelo split,
  não a recarga.**

**O que foi aplicado (com backup + rollback, padrão do projeto):**
1. **keep_alive 15m → 30m** (decisão do usuário: após confirmar que fechar o
   opencode NÃO desliga o keep_alive — ele vive no servidor Ollama, serviço
   systemd do usuário, independente do opencode — o usuário pediu 30m em vez de
   1h por economia de memória ociosa; modelo residente usa ~17 GB parados
   (12 VRAM + ~5 RAM), zero CPU até chamada). Drop-in systemd user
   (`~/.config/systemd/user/ollama.service.d/override.conf`, script
   `benchmarks/b06_keepalive.sh` com prévia/executar/rollback). Elimina o pior
   caso das B04/B05 (1ª chamada após descarga pagava a recarga de 17 GB).
2. **Timeout do SDK**: já era 1.200.000 ms (20 min) na config do opencode — não
   era o vilão. Subi o `timeout` do proxy 300 → **600 s** (margem para o
   megabrain-v2 com thinking longo; backup em `/tmp/opencode/nothink_proxy.py.bak-b06`).
   Proxy reiniciado (novo pid 73481, pid file corrigido; `__pycache__` limpo).
3. **Profiling** (este registro): carga barata, eval é o teto.

**Leitura honesta:** o keep_alive corta o padrão "1–6 min no pior caso", mas a
geração quente segue ~4,2 tok/s — limite físico da placa para um modelo de 17 GB
em 12 GB de VRAM. Acelerar a geração exigiria outra GPU (ex.: 24 GB) ou um modelo
que caiba inteiro na VRAM (ex.: 14B ~9 GB — opção arquivada por decisão do usuário).
Isso NÃO é erro de config: é o teto do hardware atual.

**Arquivos tocados:**
- benchmarks/b06_keepalive.sh (novo)
- benchmarks/nothink_proxy.py (`timeout=600`; backup em /tmp/opencode)
- docs/ENGINEERING_JOURNAL.md (este registro)
- Fora do repo: drop-in `~/.config/systemd/user/ollama.service.d/override.conf`
  (rollback: `bash benchmarks/b06_keepalive.sh --rollback`)

---

## r20 — Negativas residuais do `pesquisa` + espelho do repo corrigido (B07)

**Data:** 2026-11-12 · **Bateria:** B07 (4 PASS · 0 FAIL · 1 ⚠ controle)

**Contexto:** revisão linha por linha das 21 linhas com negativa nos 18 agentes
(28 ocorrências). 15 são falso positivo (oração subordinada, condicional,
adjetivo, citação do usuário); 6 são reais, todas no `pesquisa.md` (14 das 28
ocorrências).

**Achado colateral (grave):** o espelho `agent/` do repo estava 18/18 divergente
do global — ainda continha as iscas que a B05 removeu (`NUNCA abra a resposta` em
18 arquivos, `Nãosó` em 18, exemplos CJK em 3) e apontava `model: ollama/...` em
vez de `ollama-nothink/...`. O commit `3148894` ("iscas removidas") só alterou
permissions no `agent/`. Negativas: global 28 vs repo 300.

**O que foi feito:**
1. Espelho sincronizado (`25e6a2b`): 18/18 idênticos, iscas → 0, provider
   corrigido, +154/−346 linhas.
2. `pesquisa.md` reescrito em forma positiva: 14 → 3 ocorrências, todas benignas
   (condicional na `description` e strings de saída "não confirmei X" / "não
   encontrei fonte de X"). Guardrails preservados: teto de 2 buscas por família
   ("a 2ª é a última"), filtro de homônimo, entrega com material parcial;
   duplicatas fundidas (32→31, 34→31/32) e "Nunca invente" absorvido pela linha
   45, ampliada para "mensagem e resultados de busca".
3. B07 — 4 casos, sequenciais via proxy 11436:
   - material suficiente → 0 buscas, veredito correto;
   - homônimo (livro × filme × música) → separou e respondeu só o livro;
   - material parcial com item real → buscou 1x e trouxe dados reais
     (⚠ inconclusivo: a busca "salva" o caso);
   - material parcial com item fictício → parou em 2 buscas, entregou autor +
     editora, marcou ano/páginas/ISBN como não confirmados e descartou dois
     homônimos reais (Jojo Moyes, Dionesio);
   - link 404 → total R$ 484 vs R$ 499, duas fontes citadas com ressalva.

**Lição:** a reescrita positiva não perdeu guardrail. Para testar "entregar com o
que há", o item precisa ser **fictício** — com item real o modelo pode buscar
legitimamente e acertar, mascarando o comportamento. E espelho de repo não é
backup: divergiu em silêncio por 18 arquivos enquanto o commit dizia "iscas
removidas".

**Arquivos tocados:**
- Fora do repo: `~/.config/opencode/agent/pesquisa.md` (backup em
  `/tmp/opencode/ab-pesquisa/`)
- agent/*.md × 18 (espelho) + agent/pesquisa.md
- benchmarks/results/baterias/B07_pesquisa_negativas_2026-11-12.md (novo)
- benchmarks/results/README.md (índice com B07)
- docs/ENGINEERING_JOURNAL.md (este registro)

---

## r21 — CI vermelho: regressão desatualizada + `ver.md` sem `list`

**Data:** 2026-11-12 · **Sintoma:** `benchmarks/regressao.py` exit 1 com 34
problemas; workflow `rota-ci` vermelho.

**Causa (quatro camadas):**
1. **Conteúdo real** — `ver.md` estava com `list: deny` e sem o bloco do
   diretório padrão `/home/rodmb188/Imagens/Análise IA/`: o fluxo T05 "sem
   caminho" não conseguia listar a pasta, contrariando o AGENTS.md e o roteador.
   Restaurados `list: allow` e o passo 3 do comportamento (1 imagem → abre;
   várias → pergunta; vazia → avisa e pede o caminho).
2. **Teste desatualizado (permissions)** — desde 2026-09-25 os 18 têm
   `webfetch/websearch: allow` (Exa); o script ainda exigia deny-all nos agentes
   de texto e só `question` no entrevistador.
3. **Teste desatualizado (idioma)** — exigia o bloco "## Regras reforçadas de
   idioma", removido na B05; agora aceita o marcador positivo ("alfabeto latino"
   / "100% em pt-BR").
4. **Teste desatualizado (contexto)** — comparava `num_ctx` com o Modelfile
   (12288) e ignorava o override do proxy (16384); agora usa
   `_num_ctx_padrao()` do `nothink_proxy.py` como valor efetivo.
5. **Higiene** — `benchmarks/__pycache__/*.pyc` estava versionado;
   `__pycache__/` e `*.pyc` entraram no `.gitignore`.

**Resultado:** regressão **PASS (0 problemas)**, etapa de frontmatter do CI OK
(18 agentes × 15 permissions), espelho 18/18 idêntico ao global.

**Lição:** teste estático que codifica o estado de uma era vira falso negativo
quando o sistema evolui — cada mudança de contrato (Exa, B05, 16384) precisa
atualizar a regressão no mesmo commit.
