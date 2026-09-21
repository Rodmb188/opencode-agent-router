# B02 — Rota final: todos os 18 agentes pelo proxy corte-na-fonte (ollama-nothink)

- **Data:** 2026-09-20, 07:32 → 07:55 (-03)
- **Objetivo:** validar a rota final do B02 — os 18 agentes locais apontando para
  `ollama-nothink` (proxy 11436 → Ollama 11434), com o rascunho
  (`message.thinking`) cortado na fonte, no caminho real do SDK (openai-compatible)
  e no caminho real do frontmatter dos agentes.
- **Regras em vigor:** sessões curtas do primário, saída bruta só truncada
  (head -c), mudanças de runtime por script com backup + rollback, 27B em
  sequência (nunca paralelo), contexto limpo.
- **Modelos:** qwen3-local 14B (7 agentes) · megabrain-v2 27B (profundo) ·
  nothink-v2 27B (9 agentes) · vision 8B (ver) — todos agora via `ollama-nothink`.
- **Esperado em todo teste:** resposta limpa, sem erro de provider, sem rascunho
  de thinking na saída e sem ocorrência de `"thinking"` no log do proxy.
- **Resultado geral:** **6 PASS** (rota validada em 4 modelos + agente com
  thinking de ponta a ponta + log limpo) · 1 teste DESCARTADO por achado.

## Achado (registro obrigatório)

O smoke inicial tentou `opencode run --agent <nome>` para os 18 agentes. **O
`--agent` da CLI NÃO exercita o modelo do frontmatter do subagent**: a sessão run
usou o modelo principal da config, não
`ollama-nothink/<modelo>`. Prova: título de sessão com o modelo principal e erro
do provider
open-code para 14 dos 18. O caminho real dos subagentes é a chamada via task
dentro de uma sessão (usada no T05). **O smoke via CLI foi descartado** — os
tests de rota que valem são T01–T06 abaixo.

## Vereditos

| Teste | Alvo | Esperado | Resultado | Veredito |
|---|---|---|---|---|
| T01 | SDK `ollama-nothink/qwen3-local` | "ok" limpo | "ok" | ✅ limpo |
| T02 | SDK `ollama-nothink/vision` | "ok" limpo | "ok" | ✅ limpo |
| T03 | SDK `ollama-nothink/nothink-v2` (27B) | "ok" limpo | "ok" | ✅ limpo (2ª tentativa, ver T03) |
| T04 | SDK `ollama-nothink/megabrain-v2` (27B, thinking) | "ok" sem rascunho | "ok" sem rascunho | ✅ limpo — corte na fonte no 27B thinking |
| T05 | Subagent real `preciso` (frontmatter novo) | 36 | **Resposta: 36** | ✅ limpo — ponta a ponta |
| T06 | Log do proxy (`/tmp/opencode/proxy.log`) | 0x `"thinking"` | 0 ocorrências | ✅ limpo |
| T07 | Estática das rotas (grep) | 18 em `ollama-nothink/` · 0 em `ollama/` | 18 · 0 | ✅ limpo |
| ~~T08~~ | Smoke via `opencode run --agent` ×18 | — | rodou no modelo principal | ❌ descartado (achado acima) |

## Detalhes

### T01 — qwen3-local pelo provider novo (SDK real)

- Prompt: `Responda apenas com a palavra ok`
- Comando: `opencode run --model ollama-nothink/qwen3-local "..."`
- Resposta verbatim: `ok`
- Observação: 14B com thinking ativo — nenhum vestígio de rascunho na saída.

### T02 — vision pelo provider novo (SDK real)

- Prompt: `Responda apenas com a palavra ok`
- Comando: `opencode run --model ollama-nothink/vision "..."`
- Resposta verbatim: `ok`

### T03 — nothink-v2 27B pelo provider novo (SDK real)

- Prompt: `Responda apenas com a palavra ok`
- Comando: `opencode run --model ollama-nothink/nothink-v2 "..."`
- Primeira tentativa: vazio — `timeout 180` do shell cortou o carregamento do 27B
  (o run em si é ok; o proxy logou `ConnectionResetError` do corte do shell).
- Segunda tentativa (`timeout 900`): resposta verbatim: `ok`
- Observação: 27B no-think responde pelo proxy sem perda de conteúdo.

### T04 — megabrain-v2 27B thinking pelo provider novo (teste crítico)

- Prompt: `Responda apenas com a palavra ok`
- Comando: `opencode run --model ollama-nothink/megabrain-v2 "..."`
- Resposta verbatim: `ok`
- Observação: **o modelo pensa (thinking ON) e o proxy removeu o raciocínio na
  fonte** — a resposta final veio só com "ok", sem rascunho. É a prova do corte
  no caso mais caro (27B thinking).

### T05 — subagente real `preciso` (ponta a ponta via frontmatter)

- Caminho exercitado: task dentro de sessão → `agent/preciso.md`
  (`model: ollama-nothink/qwen3-local`) → proxy 11436 → Ollama 11434 → resposta.
- Prompt: `Quanto é 15% de 240? Responda apenas com o número.`
- Esperado: `36` (declarado antes da execução).
- Resposta verbatim (final): `**Resposta: 36**`.
- Observação: cálculo correto; o conteúdo trouxe passos curtos do próprio modelo
  (estilo normal do qwen3-local no content — não é o thinking do Ollama, que o
  proxy corta). **Rota do agente validada de ponta a ponta.**

### T06 — log do proxy sem rascunho

- Comando: `grep -c '"thinking"' /tmp/opencode/proxy.log`
- Resultado: `0` (após T01–T05).
- Observação: nenhuma resposta intermediária ou final com o campo `thinking`.

### T07 — validação estática das rotas

- Comando: `grep -rh '^model: ollama/' ~/.config/opencode/agent/ | wc -l` → `0`
- Comando: `grep -rh '^model: ollama-nothink/' ~/.config/opencode/agent/ | wc -l` → `18`
- Observação: os 18 arquivos `agent/*.md` trocados; backup em
  `~/.config/opencode/agent.bak-b02-20260920-073241`.

### T08 — smoke via CLI (descartado — achado)

- Comando tentado: `opencode run --agent <nome> "Responda apenas com a palavra ok"` × 18.
- Resultado: 14 × `Error from provider (Console): OpenCode's free tier can only
  be used from within OpenCode`; 4 responderam "ok" mas com título de sessão do
  modelo principal da config (não o do frontmatter).
- Conclusão: não serve para validar rota de subagent (a CLI run usa o modelo
  principal da config quando o agente é subagent).

## Arquivos tocados nesta bateria

- `benchmarks/b02_agents.sh` (novo — script de troca das rotas: prévia /
  `--executar` / `--rollback`; corrigido em r15: `grep | wc -l` com `|| true`
  para não abortar com pipefail quando o grep não acha nada).
- `~/.config/opencode/agent/*.md` × 18 (rotas `ollama/` → `ollama-nothink/`).
- Backup: `~/.config/opencode/agent.bak-b02-20260920-073241` (18 arquivos).

## Rollback (1 comando)

```bash
rm -rf ~/.config/opencode/agent && cp -a ~/.config/opencode/agent.bak-b02-20260920-073241 ~/.config/opencode/agent
```