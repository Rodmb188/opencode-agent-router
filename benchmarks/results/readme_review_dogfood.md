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