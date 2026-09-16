# Dogfooding: README review — main model vs `revisor` agent

Date: 2026-09-15 (late session).
Object: `README.md` of this repo (~340 lines, English).
Method: the README is reviewed blindly (a) by the main model and (b) by the
project's own `revisor` subagent (qwen3-local). Findings compared and registered.

## 1. Main-model review (applied)

Found 4 real issues. All applied as fixes:

| # | Issue | Fix |
|---|-------|-----|
| A | Typo in architecture diagram: `precisely/` (agent name) | → `preciso` (restored diagram alignment) |
| B | "ROCm" in Tech stack — wrong backend | → `Vulkan/RADV` |
| C | Speed table near-false promise: 27B "~56 s" was a capped ~200-token measurement; honest end-to-end figure is 568 s / 2,278 tokens | → added reconciliation footnote |
| D | Narrative gap: models named `nothink`, `megabrain`, 16k context in Part I vs `nothink-v2`, `megabrain-v2`, 12288 in Part II | → added bridge note under *Model stack* |

## 2. `revisor` agent — attempt 1 (failed the task)

Prompt: structured review request (pt-BR output, 4 sections, "point out only real
problems"). Result: **a faithful 700-word summary of the README** instead of a
critique. Output started with a stray CJK character (`緻`) and ended with
"Let me know if you'd like help setting this up…" (chat-assistant persona drift).
No defects found — zero usable review items.

## 3. `revisor` agent — attempt 2, retry (failed again, worse)

Minimal prompt: "list at most 6 real problems, do not summarize, format: line +
1-line problem". Result: **entirely in Chinese**, leaked internal chain-of-thought
("嗯，用户给了我…我需要确保总结涵盖…"), summarized again, answered in helper tone
with emoji. No defects found.

## 4. Hypothesis

qwen3-local (14B, multilingual Qwen3) given a long English technical document
drifts to its dominant training distribution (Chinese/English) and to its
default behavior (summarize) instead of following the critique directive. Same
failure mode three times → rule "retry once" exhausted; further attempts are
not warranted.

## 4b. Attempt 3 — post-hardening retest (invalid, then confirmed)

Requested by the user. Same prompt as attempt 1. Result: **identical failure** —
entirely in Chinese, opening stray CJK char (`颗`), summarized again. However
the `revisor.md` hardening (item 5) was applied in a session that **had not been
restarted**; agent files reload only at opencode startup, so this run still used
the old definition → attempt 3 does NOT validate the hardening. What it adds:
three identical structural failures across prompts prove the task type (rigorous
critique of a long English doc) is outside this agent/model combo's reliable
envelope.

## 4c. Attempt 4 — post-restart, hardened definition (failed, new drift)

Requested by the user, run after a real opencode restart (hardened `revisor.md`
now active). Same prompt as attempt 1. Result: **a fourth, new failure mode** —
no summary, no Chinese; the agent instead responded with a fabricated
step-by-step account of "running grep with the pattern `function parse(argv) {`"
and "switching to `read` to check for occurrences", i.e. confabulated coding
activity entirely unrelated to the review request. Zero review items.

## 4d. Attempt 5 — `profundo` (T12, megabrain-v2 27B thinking)

Requested by the user as the trio capstone (main model / revisor / profundo on the
same prompt). Same prompt as attempt 1. Result: **a fifth failure, new mode** —
the agent answered with a self-introduction ("Olá! Sou o megabrain-v2… Em que
posso ajudar?") without reading the file or producing any review item. Task
completion failed outright (no file read, no analysis).

## 4e. Attempt 6 — `profundo` sanity check (control, PASSED)

To separate *broken* from *task-type envelope* (the user's explicit question),
the same `profundo` agent received its **core task** — a deep architecture
decision (modular monolith vs microservices), the exact class it aced in wave 3.
Desired output: verdict + trade-off table + inversion condition + executive
summary, pt-BR, no foreign alphabets.

Result: **flawless** — structured verdict, 8-dimension trade-off table,
inversion conditions, executive summary; 100% pt-BR, no leaks, complete. The
subagent pipeline is functional; the five review failures are a **task-type
envelope boundary**, not a hardware or config defect.

## 5. Conclusion — T7/T12 review envelope

Five subagent attempts, five distinct failures — revisor (qwen3-local 14B):
summary / Chinese / CJK-leak / confabulated grep; profundo (megabrain-v2 27B):
greeting without task execution; **yet profundo fully succeeds on its native
task class (attempt 6)**. Verdict: with the local stack, **rigorous critique of a
long English document is outside the subagent envelope of BOTH review tiers —
prompt design does not recover it.** The recommended routing ("long-EN QA →
T12") was refuted for *this task type*: the **main model (T1) is the only
reliable reviewer**. But T12 remains excellent for its intended use — deep
analysis. These are envelope boundaries, consistently reproducible, not broken
agents.

## 5b. Actions taken

- Hardened `agent/revisor.md` with three rules: (1) critique-only, never
  summarize; (2) never leak internal reasoning; (3) never switch language —
  pt-BR always.
- Registered the four-attempt failure series (this file).
- README split into stable doc + `docs/ENGINEERING_JOURNAL.md` (structure issue
  surfaced by this dogfood was an input to that: the README read like a chronicle).

## 7. Status

- [x] Main-model review: 4 fixes applied to the original README
- [x] `revisor` attempts 1–4: four distinct failures, series registered
- [x] `profundo` attempt 5: greeting-only, no task execution, registered
- [x] `revisor.md` hardened (hygiene rules)
- [x] `profundo` attempt 6 sanity check (native task): **PASSED** — envelope, not breakage
- [x] Conclusion: long-English-doc QA → **T1 only** (T7 and T12 fail it, but T12 stays for deep analysis)
- [x] README split into stable layout + `docs/ENGINEERING_JOURNAL.md`

---

## 8. Experiment: embed whole vs chunking (the user's hypothesis)

The user proposed the failures might come from **how** the text is delivered, not
from capability. Controlled test, one variable changed, on `revisor`
(qwen3-local 14B): same task (list DEFECTS ONLY, pt-BR, "don't summarize"), four
prompts — A = full README embedded; B1/B2/B3 = three embedded chunks.

| Test | Delivery | Task adherence | Output quality |
|---|---|---|---|
| A | Full README embedded | ✓ stayed on task (format respected) | ✗ invented **reformat suggestions** as defects (e.g. "14B → 14B (quantized to 9 GB)", "12 GB VRAM → (27B)"), lone opening CJK char |
| B1 | Chunk 1 (intro/arch) | ✓ on task | ✗ nitpicks as defects ("nails is informal", "italic vs bold") |
| B2 | Chunk 2 (decisions/memory/layout) | ✓ on task, best | ~decent: 2 fair stylistic/nuance flags + 3 weak ones ("saves" vs "economiza" in an English doc) |
| B3 | Chunk 3 (getting-started/stack) | ✗ **drifted**: answered "how to configure opencode.json" as a tutorial | off-task |

### Verdict

1. **The form WAS a real factor — for task-adherence.** Embedding the text in the
   prompt (instead of pointing at the file) fixed what 5/5 earlier attempts got
   wrong on adherence (Chinese / summary / greeting / confabulated grep): 3 of 4
   embedded runs stayed on-task and obeyed the output format.
2. **But the ceiling is judgment, not format.** Once on-task, qwen3-local
   *invents* defects (reformatting suggestions, stylistics) even when told "APENAS
   problemas reais". It cannot reliably distinguish a real defect from a nitpick
   in English technical prose.
3. **Chunking risks decontextualization.** B3 (imperative "Clone… Start… Use it")
   got read as a user request → helper mode. Descriptive sections (B2) fare best.
4. Conclusion: for the local stack, **embed + section-chunking is the best
   possible local form**, but it does not close the gap to the main model — it
   raises adherence from 0/5 to 3/4 while quality stays shallow. Long-EN critical
   review remains a T1 task; the embedding technique is still worth adopting for
   T7/T12 when reviewing *pt-BR* or short texts.
---

## 9. Experiment: does embedding fix profundo too? (test A only)

Repeat of section 8's test-A, but on **`profundo` (megabrain-v2 27B, thinking
ON)** — the model that on attempt 5 greeted without reading the file. One
variable: the full README was embedded in the prompt (same "DEFECTS ONLY, pt-BR"
format).

### Result

| Run | Delivery | Outcome |
|---|---|---|
| 9a | Full README embedded | First invocation returned **empty result** (0 bytes, state=completed) |
| 9b | Same task, resumed session | ✓ stayed on-task; delivered **7 real findings**, all in pt-BR, format respected |

The 7 findings (reviewed against the repo): 3 fully valid (intro omits the 8B
vision model from the "two models, 18 agents" claim; `agent/` vs `agents/` dir
divergence; `models/README` referenced but absent from the repo tree), 1 partial
("Qwen3-6.5/3.6-class" is undefined; the phrase is inherited from
`models/README`), and 3 nuance/coherence flags (intro "5 of 5 arithmetic" vs
design §"13/14" and megabrain "3/3" — different batteries not distinguished;
"the 27B" in format-fidelity § was actually `nothink-v2`; same battery-mixing in
math §).

### Verdict

1. **Embedding fixes adherence on profundo too.** Attempt 5 (file-path) failed;
   attempt 9b (embedded) delivered on-task, in-format, in pt-BR — same pattern as
   revisor (0/5 → 3/4).
2. **Quality ceiling is higher than revisor's.** The 7 findings were mostly
   real; only the nuance items were near-nits, and several were legitimate
   coherence gaps the README genuinely had. This is the strongest review the
   local stack produced.
3. **New reliability quirk: occasional empty first result.** 9a completed with
   zero output (megabrain-v2, long prompt + thinking). One data point; a retry
   recovered it. Worth a retry-on-empty rule for future heavy T12 embeds.
4. All 7 findings were applied to the README (fixes validated against
   `models/README.md` and the journal). Embedding is now the **recommended
   delivery for T12** critical review, and the README no longer contradicts
   itself on models, batteries, or layout.

---

## 10. Root cause of the "empty profundo" + tool permission lockdown

### 10a. Because: the empty was context overflow, not timeout

DB evidence for attempt 9a (README fully embedded, `megabrain-v2`, thinking ON):

```
step-finish { reason: "length", tokens: { total: 12288, input: 8675, output: 3613 } }
```

`input 8675 + output 3613 = 12288 = num_ctx`. The model burned the whole window inside
reasoning and terminated with `reason: length` BEFORE emitting any final text → 0 bytes.
Attempt 9b worked only because its prompt was tiny (76 tokens) and reused the cache:
`cache.read: 8671`. So "retry" was luck, not a strategy. **The fix is preventive math**:
megabrain at 12288 ctx needs input ≲ 4k tokens (reasoning reserves the rest).

### 10b. Action: tool `permission` lockdown (embed-only agents)

All 18 agents now carry an explicit `permission:` block. Text-based agents (T02–T12
vocals, QA, vision, tutoring, writing, planning, SEO, translation) are **`read/edit/bash/
web/task: deny`** — because the quality experiments proved the working input form is
*embedded text in the message*, not file reads. Only four keep real tools:

| Agent | Tools allowed |
|---|---|
| `pesquisa` | `webfetch`, `websearch`, `skill` |
| `codigo` | `read`, `edit`, `glob`, `grep`, `list`, `bash`, `external_directory`, `todowrite`, `lsp` |
| `dados` | same as `codigo` |
| `importador` | same as `codigo` |
| `sysadmin` | `read`, `edit`, `glob`, `grep`, `list`, `bash`, `external_directory`, `todowrite`, `lsp` |

`task` is `deny` everywhere (subagents must never spawn sub-subagents; matches
`subagent_depth: 1`). `entrevistador` alone allows `question` (interactive).

### 10c. Roteador rule 9 rewritten

Old: "empty = failure, retry 1× with smaller scope". New: empty is context overflow →
**cap embedded input at ~4k tokens for `profundo`**, chunk longer texts, never rely on
retry as the fix. (Rule 9 + protocol now mandate embedding text in the task message;
matched by AGENTS.md iron rules.)

### 10d. Why this closes the loop with the experiments

- Attempts 1–4 failed reading a file path → embedding fixed adherence (sec. 8).
- Attempt 9a failed from oversized embedding → chunking/budget fixes it (sec. 10a).
- Both failure classes are now handled at the *router* level (input form + size), which
  is the only stable fix — consistent with the envelope conclusion in sec. 5.

---

## 11. pt-BR thinking rule: prompt-level fix FAILED (CJK leak is a decode artifact)

After the tool lockdown (sec. 10), all 18 agents gained an explicit pt-BR rule
("raciocínio e resposta em pt-BR; bloqueie outro alfabeto"). Smoke-tested the
two agents that had leaked before (`preciso`, `revisor`):

| Run | Before fix | After per-agent pt-BR rule |
|---|---|---|
| `preciso` | leaked `栋` | STILL leaked `颗` (answer correct: R$73.44) |
| `revisor` | leaked `起来`, bad "nos vamos" call | STILL leaked `起来` (corrections correct) |

### Verdict

1. **The CJK residue is a first-token decode artifact of Qwen3-family at low
   sampling, not a reasoning/language defect** — it precedes the actual content
   and does not affect correctness. It persists under explicit per-agent
   pt-BR instructions.
2. **Prompt-level "think in pt-BR" is not a reliable control.** Don't claim it
   is. The honest, deterministic fix is on the *presentation* layer: the router
   strips any non-Latin prefix before showing the result (roteador protocol step 4).
3. Both smoke tests otherwise passed: correct math step-by-step with
    verification; correct review with clean, defensible corrections. Tool
    lockdown (sec. 10) did not break the agents.

---

## 12. `profundo` re-test with the new rules: PASSED (no CJK leak)

Pre-registered smoke test after rule 9 rewrite (4k embed budget) + pt-BR rules +
CJK sanitize. Task: "devo modularizar esse monólito?" with a short scenario
embedded (~4k tokens, well under budget).

| Check | Result |
|---|---|
| Decision quality | Sound 4-point analysis: recommendation, 2 risks, 1 objective signal, verdict |
| Language | Clean pt-BR throughout — **zero CJK leak** on first run |
| Context budget | Within 12288 (embedded input ≲ 4k; no `reason: length`) |
| Compliance | Used the deep-analyze pattern, no tool attempts |

### Verdict

1. The **embedded ≤4k + pt-BR + step-4 sanitize** package works end-to-end on
   the 27B deep agent. The earlier empty/corrupt outputs (sec. 9/10a) were
   context-overflow + decode artifacts, both now addressed at the router level.
2. One cosmetic typo in the verdict ("migraçãoprematura") — a word-gap, not a
   regression; no action required.
3. Rule 9 (preventive embedding budget) is the correct control for heavy agents.

---

## 13. `pesquisa` T04: websearch NÃO chega a subagente em `ollama` (regra-real)

Smoke test do `pesquisa` (Nothink-v2 27B, material embutido: "melhor robô aspirador
custo-benefício Brasil R$1.500–2.500") voltou **vazio**. Investigação no DB + source:

| Evidência | Achado |
|---|---|
| Tool calls reais da sessão | `skill` ×2, `webfetch` ×14, **`websearch` ×0** |
| Reasoning do subagente (verbatim) | "não tenho a ferramenta `websearch` disponível — só tenho `webfetch` e `skill`" |
| `registry.ts:58` `webSearchEnabled()` | websearch só é exposto se provider = `opencode`/`opencode-go` OU env `OPENCODE_ENABLE_EXA` / `OPENCODE_ENABLE_PARALLEL` |
| Provider da sessão | `ollama` (primário = `opencode/big-pickle`, subagentes = `ollama/*`) |
| Envs | nenhuma de EXA/PARALLEL presente no shell nem no systemd |
| Desfecho | 14 webfetches acumularam `input 9.660` → `reason: length` (12.288) com `output 100` → resposta vazia |

### Conclusão prática

- `permission: websearch: allow` no agente é **necessário mas nunca suficiente**:
  a tool é filtrada no registry por provider antes de chegar ao toolset do subagente.
- Sem websearch, o subagente caça `webfetch` (inclusive URLs de buscadores) e
  estoura o contexto — a mesma classe de falha do `profundo` (sec. 10a).
- **Fix adotado (não é workaround): inverter a divisão de trabalho em T04.**
  Quem tem a tool é o primário (`opencode`); quem sintetiza melhor é o subagente.
  O roteador agora manda: *primário roda 2–3 `websearch`, extrai trechos, embute na
  mensagem, `pesquisa` sintetiza/ranqueia/veredita sem nenhuma tool*.
- `pesquisa.md` reescrito: permission **all-deny**, regra "você não tem websearch,
  o material vem embutido". Roterador: linha T04 + regra 4 + protocolo passo 6.

### Verificado junto

- `websearch` REALMENTE funciona no primário deste ambiente (teste ao vivo com
  resultado acima): porque o primário roda provider `opencode` (big-pickle).
- Doc oficial confirma o gate de provider (tools page, seção `websearch`).

---

## 14. Two real boundaries found during post-restart polish

### 14a. T05 (vision) cannot be smoked by the primary — no image input

The primary model (`opencode`/big-pickle) is **not multimodal**: this session
cannot attach/read an image, so a `task` to `ver` cannot carry the attachment.
The `ver` agent (vision 8B VL) does support images, but the delegation link
fails before it — the error is raised on the primary side ("ERROR: Cannot read
image"). Consequence: T05 must be smoked manually in the TUI (user attaches an
image). Documented in README "Known limitations".

### 14b. `opencode run --agent <subagent>` does not work headless

Attempted to headless-smoke the stack via CLI:
`opencode run --agent preciso "17*23"` → the CLI **falls back to the default
agent** with a warning ("agent preciso is a subagent, not a primary agent").
Attempts to route via the roteador (`__TIER__ T02 ...`) and even a trivial
`opencode run "2+2"` each hung >120 s with no output — the CLI opens an
interactive session that never returns on this stack. So the automated
regression (`benchmarks/regressao.py`) deliberately splits: **static checks
run headless, live smokes are a TUI checklist**. The static layer is the one
that catches the real breakage class (YAML/permission/link integrity).

### 14c. Bonus: the three `description:` YAML bugs finally fixed

The binary validator flagged `qa.md`, `sumarizador.md`, `tradutor.md` for
unescaped `:` inside `description:` ("erros inadmissíveis", "A/B de
sumarização: 14,75", "A/B de tradução: 14,67"). Tagged harmless pre-existing
... but they were real YAML breaks. Fixed by quoting the descriptions; the
regression script now fails if any frontmatter fails to parse. 18/18 green.

---

## 15. T05 smoke test: the image never reached `ver` (and the "screenshots" hunt)

Real session (`Revisão Teste.png`, 2026-09-15, primary `build` on `big-pickle`):

1. User sent `@ver /home/rodmb188/Imagens/Capturas de tela/Teste.png "Me diga o que
   você vê"`. The primary spawned `ver` with a **text-only prompt** ("Analyze
   attached image...") that carried neither the attachment nor the path. `ver`
   correctly replied "I can't see any image" — nothing had arrived. **The subagent
   was right; the router was broken.**
2. User: "it's in the screenshots folder". Primary invented paths: `read
   /screenshots/Teste.png` and `read /screenshots/` → both failed.
3. Primary then delegated to `explore` "search screenshots directory in codebase,
   check conventions like /public/screenshots or /assets/screenshots" — 12 web-stack
   globs (`public`, `assets`, `static`, `media`, `uploads`, `docs`...), all empty,
   while the answer was plain in the conversation: `Capturas de tela`.
4. Two more `task`→`ver` attempts (20:46, 20:52) repeated failure #1.

Root cause is division of labor, same class as T04's websearch gate: the primário
does not automatically hand the attachment to the subagent, and `ver.md` had
`read: deny`, so it couldn't open the file by itself even if handed the path.

Fix (shipped):
- `ver.md`: `read: allow` (vision only, all else deny) + behaviour rule #2: if the
  prompt carries a file path, USE `read` on it before saying "I see no image".
- `roteador/AGENTS.md` rule for T05: always embed `Caminho da imagem: <absoluto>`
  in the task prompt; never delegate to `explore` to "find" the screenshot; ask the
  user for the path if missing instead of guessing.
- Regression now encodes it: `ver` must have exactly `["read"]` allow.

After the fix, a smoke was run twice in the same session:

- **21:11 — FALSE POSITIVE.** The `read` fix had shipped, but the live config was
  not re-loaded yet. The smoke *appeared* to pass because the model described
  "text in a sans-serif font" — there is no such text in the test image. The ver
  answered from its system prompt / prompt template, without ever calling `read`
  (zero tool calls in the session part). Lesson: on vision, trust only output that
  references *visible content that matches the image*, not any description with
  plausible object nouns. The `ver` smoke checklist note was updated to demand a
  description/OCR that matches the actual image.
- **21:41 — the real blocker surfaced.** After a restart, `ver` **did** call `read`
  and the tool returned the image (attachment present in the tool result), but the
  model received `Cannot read image (this model does not support image input)`
  instead of the bytes. Same error hits the non-multimodal primary when it reads a
  PNG, so the gate is in opencode, not ollama: a direct call to the `vision` model
  (native API and OpenAI-compatible `/v1/chat/completions` with `image_url`)
  correctly describes the image (a knight in armor holding a sword). The model has
  vision; the stack was cutting it.

---

## 16. T05, round 2: opencode derives image support from `modalities`, not `attachment`

The 21:41 failure above was traced into the opencode binary (strings on v1.18.29,
`/usr/bin/opencode`):

- For a model defined in `provider.<id>.models`, capabilities are computed as
  `input.image = k.modalities?.input?.includes("image") ?? providerCapability.image ?? false`.
- `attachment: true` alone maps to a different flag and does **not** set
  `input.image` to true. A custom model needs `modalities` declared.

The tricky part: the V1 schema for `Model.modalities` (packages/core
`v1/config/provider.ts`) is an **object** —

```ts
modalities: Schema.optional(Schema.Struct({
  input:  Schema.optional(Schema.Array(Schema.Literals(["text","audio","image","video","pdf"]))),
  output: Schema.optional(Schema.Array(Schema.Literals(["text","audio","image","video","pdf"]))),
}))
```

— not an array of strings. A first attempt wrote `"modalities": ["text", "image"]`
(array), which the decoder would never map onto `.input`; the compact `lower()`
step in `config/v2-compat.ts` deliberately does not touch provider models. The
correct shape in `opencode.jsonc`:

```jsonc
"vision": {
  "name": "Qwen3-VL 8B (visão)",
  "attachment": true,
  "modalities": { "input": ["text", "image"], "output": ["text"] }
}
```

The SDK types agree: `modalities?: { input: Array<"text"|"audio"|"image"|"video"|"pdf">; output: ... }`.

Fix shipped:
- `config/opencode.jsonc` (repo) and `~/.config/opencode/opencode.jsonc` (live)
  now carry the object-shaped `modalities` on `vision`.
- `benchmarks/regressao.py` gained a static check (section 4) that fails if
  `vision.modalities` is not an object containing `image` in `input` and `text` in
  `output` — so a future array-shaped revert breaks CI instead of silently
  toggling `input.image` off.
- **Open question:** whether opencode hot-reloads provider config at runtime.
  Config files are read per instance state (config.ts `loadInstanceState`); the
  safe path is a restart after editing `opencode.jsonc`. **Next action:** restart
  opencode, run the T05 smoke again (path in prompt, image = `Teste.png`), and
  confirm the `ver` output describes the knight image — without *any* "Cannot read
  image" or hallucinated "text" in its reasoning.

---

## 17. T05, round 3: the multimodal primary is the trap, not the helper

Two follow-up sessions after the `modalities` fix shipped showed what happens when
the main model (running `vision` directly) tries to *analyze* the image instead of
delegating:

- Session "Analisando imagem de cavaleiro" (`ses_f58474c...`): the primary ran on
  `ollama/vision`. Sending the attached `Teste.png` straight into the main context
  produced `exceeded the provider's size limit due to large media attachments`,
  followed by a loop of retries with **0 input/0 output tokens** and `finish:
  "unknown"`. Then the confused primary started hallucinating paths: `read
  /src/index.ts`, `read /src/`, and `task → explore` "Find the correct path for
  the 'src' directory" — while the real answer (`/home/rodmb188/Imagens/Capturas
  de tela/Teste.png`) was in the conversation. That is the "muito pensar" the
  report references: not slow thinking, but a retry/hallucination loop.
- The user then pasted the path **in quotes**: the flow finally worked. A
  fresh `ver` sub-session (`ses_f57a0f244...`) called `read` on
  `/home/rodmb188/Imagens/Capturas de tela/Teste.png`, got the attachment, and
  described the knight image correctly in ~36 s (read at 01:00:10, answer at
  01:00:32, 4,804 total tokens).

Two real fixes distilled:

1. **Paths with spaces are valid** — `read` accepts them fine when passed *in
   full*. What breaks is re-parsing: splitting `Capturas de tela` into tokens, or
   "correcting" the path into `/src/index.ts`. The router/AGENTS rules now
   mandate **verbatim** transfer (keep quotes if given, otherwise pass intact,
   never normalize). `ver.md` got the same instruction.
2. **A multimodal primary must still delegate to `ver`.** A clean sub-session
   context + `read` on the exact path is fast and reliable; running the image
   through the primary's own context overflows the provider limit and loops. The
   iron rule now says: if the task is T05, delegate — do not analyze yourself even
   if you can see.

Regression smoke for `ver` now explicitly covers the space-path case and forbids
re-parsing.
