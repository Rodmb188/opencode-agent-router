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
failure mode twice → rule "retry once" exhausted; a 3rd attempt is not warranted.

## 5. Action taken

Hardened `agent/revisor.md` with three rules: (1) critique-only, never summarize;
(2) never leak internal reasoning; (3) never switch language — pt-BR always, even
when the reviewed text is in another language. Applies on next opencode restart.

## 6. Open question

For critique of long English texts, T7 (revisor/qwen3-local) is currently
unreliable. Options to evaluate later:
- Route long-English-document critique to the main model (T1) or to `profundo`;
- Keep `revisor` for pt-BR text only;
- Retest after prompt hardening.

## 7. Status

- [x] Main-model review: 4 fixes applied to README
- [x] `revisor` attempts 1–2: documented as failure observations
- [x] `revisor.md` hardened
- [ ] Retest `revisor` after restart (next session)