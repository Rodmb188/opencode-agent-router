# ROADMAP — Roteador local de agentes (T00–T19)

> Documento de direção do projeto (criado a partir do planejamento de
> 2026-09-16). O usuário decidiu: **FASE A — CONSOLIDAR** primeiro.
> O diário técnico completo (medidas, falhas, decisões) vive em
> [ENGINEERING_JOURNAL.md](ENGINEERING_JOURNAL.md).
>
> **Status em 2026-09-21:** FASE A (consolidação) concluída — C1 ✅ · C2 ✅ · C3 ✅ · C4 ✅.
> Linha de corte do rascunho: **parser 3/3** + **proxy corte-na-fonte self-test 14/14**
> (commits `3e9d038` r12 + `6ebd77f` r13 + `b6810db` r14). **Achado r13:** o Ollama
> devolve o raciocínio em campo separado (`message.thinking`); o proxy o remove na
> fonte. **Achado r14:** o package `@ai-sdk/ollama` não existe no npm (404); o proxy
> agora fala o formato OpenAI (`/v1/chat/completions` + SSE) e o plug usa o mesmo
> `@ai-sdk/openai-compatible` já comprovado. **B02 APLICADO E FECHADO** (r14 + r15):
> plug validado 6/6 e **rota final executada — os 18 agentes locais apontam para
> `ollama-nothink`** e o corte na fonte vale para as rotas reais. **r16:** causa raiz
> do vazamento residual corrigida (tools/tool_calls repassados + corte inline) e
> **r16b:** proxy passou a traduzir imagens e tool_calls de histórico (o `ver`
> identificou a pessoa). **B03 ✅** (smoke dos 18 pela rota final: 14 PASS · 2 parcial
> · 2 FAIL — 27B e vision 100% limpos; qwen3-local instável). **r17/B04 ✅:** decisão
> do usuário executada — **os 7 leves foram trocados para nothink-v2**; bateria
> comparativa 7/7 PASS, vazamentos eliminados e FAILs históricos (financeiro,
> revisor) corrigidos. **A config agora é 16 × nothink-v2 27B + profundo (megabrain)
> + ver (vision) — stack 100% 27B/vision.**
> **B05 ✅ (r18):** calibração anti-isca dos 18 frontmatters (107→39 negações,
> 0 "nunca", exemplos estrangeiros removidos, descriptions qwen3→nothink corrigidas)
> — 18 PASS · 0 regressão. **B06 ✅ (r19):** ajustes de latência sem tocar no modelo —
> keep_alive 30m (drop-in systemd, rollback em 1 comando) · timeout do proxy 600 s ·
> profiling: GPU AMD RX 6750 XT 12 GB, 27B em split 43/57 CPU/GPU, ~4,2 tok/s (teto
> físico da placa). **Decisão 2026-09-21:** **M1 (camada 7B) DESCARTADO** — precisão
> > velocidade; 14B já reprovava (vazamento 4/7 na B03); 7B reabriria os FAILs.

## Fluxograma do sistema

```
┌──────────────────────────────────────────────────────┐
│                       USUÁRIO                          │
│  "Faça X" │ "Explique Y" │ "Traduza Z" │ [imagem]     │
└───────────┬───────────────────────────────────────────┘
            ▼
┌──────────────────────────────────────────────────────┐
│      opencode · AGENTS.md (rotas T00–T19) + config     │
│  Primário: nothink-v2 (local) │ subagentes via Ollama  │
└───────────┬───────────────────────────────────────────┘
            ▼  ✅ B02: 18 agentes locais -> ollama-nothink (proxy)
┌──────────────────────────────────────────────────────┐
│  PROXY corte-na-fonte  ✅ parser 3/3 · proxy 14/14      │
│  11436 → 11434  ✅ plug (r14) e rota final dos agentes  │
│  (r15) aplicados — rollback em 1 comando por script    │
│  · corta <thinking>/RASCUNHO em content                │
│  · remove message.thinking/rascunho na fonte (r13)     │
│  · repassa tools + corta inline (r16)                  │
│  · traduz imagens/tool_calls historico (r16b)          │
│  · sanitiza charset → latino pt-BR                     │
└───────────┬───────────────────────────────────────────┘
            ▼
┌──────────────────────────────────────────────────────┐
│     OLLAMA local (32GB RAM, SEQUENCIAL obrigatório)   │
│     ✅ r17/B04: 16 × nothink-v2 27B (leves + Onda 2)  │
│     1 × megabrain-v2 27B (profundo) · 1 × vision      │
│     qwen3-local 14B AUSENTE (só em backup b04)        │
└───────────┬───────────────────────────────────────────┘
            │ resposta / erro / timeout
┌───────────▼───────────┐   ┌─────────────────────────┐
│       USUÁRIO         │   │  Journal (crônica)       │
└───────────────────────┘   └───────────┬─────────────┘
     ┌──────────────┼───────────────┐   │
     ▼              ▼               ▼   │
 benchmark     Regra nova       Correção │
 regressao     de ferro         preventiva
     │          em AGENTS.md              │
     ▼                                    │
  PASS/FAIL ──────────────────────────────┘
  LOOP: teste → falha → regra → regressão → próximo teste

Legenda: ✅ pronto (B02 fechado em r14–r16; B04/r17 troca dos leves) · ⏳ pendente (próximo: M1/M2)
```

## Metas

### 🟢 Curto prazo (≤ 1 semana)

| # | Objetivo | Pronto quando… | Esforço | Prioridade | Dependências |
|---|----------|----------------|---------|------------|--------------|
| C1 ✅ | Fechar CI (camada **headless-friendly**) | 2026-09-17: estático no Actions (`rota-ci.yml`, badge no README) + paridade Modelfile⇢CONTEXT_BUDGET + `benchmarks/model_checks.py` headless (qwen3 `391` ✅, nothink "bom dia" ✅, 4 modelos presentes) — vivo continua checklist manual | M | Alta | — |
| C2 ✅ | T05: fluxos com imagem testados | 2026-09-17: 2 imagens na pasta padrão → `ver` listou (`Casa.png`, `Homem.png`) e perguntou qual ✅; identificação: Lula (confiança alta) + isométrico de sobrevivência (estilo ✅, título não reconhecido — honesto) | S | Alta | — |
| C3 ✅ | ROADMAP.md versionado | Este arquivo no repo (commit `d27b92d`) | S | Alta | — |
| C4 ✅ | Orçamento de contexto formalizado | Feito 2026-09-16 → [`CONTEXT_BUDGET.md`](CONTEXT_BUDGET.md) | S | Alta | — |

### 🟡 Médio prazo (≤ 1 mês)

| # | Objetivo | Pronto quando… | Esforço | Prioridade | Dependências |
|---|----------|----------------|---------|------------|--------------|
| M1 | ~~Camada 7B para T00/T01/T02~~ **DESCARTADO (2026-09-21)** | Precisão > velocidade: 14B já reprovava (vazamento 4/7), 7B reabriria FAILs | — | — | — |
| M2 | Profiling de latência por swap | 3 cenários medidos (atual / com 7B / tuning) | M | Média | M1 |
| M3 | Onboarding (SETUP.md) | Configurar em <15 min sem erro | S | Média | C3 |
| M4 | Bateria automática de A/Bs | CI falha se nível retrocede >0.5 pts | M | Baixa | C1, M1 |

### 🔴 Longo prazo (1–3 meses)

| # | Objetivo | Pronto quando… | Esforço | Prioridade | Dependências |
|---|----------|----------------|---------|------------|--------------|
| L1 | CLI standalone do roteador (headless) | 10 comandos de teste headless | L | Média | M2 |
| L2 | Publicação v1.0 | README profissional, release, CI verde | L | Baixa | C3, M3, C1 |
| L3 | Novos domínios (2–3 agentes) | 1 agente novo integrado + 20 testes | M | Baixa | C1, M1, L1 |
| L4 | Smoke vivo headless | 50 interações sem crash + relatório | M | Média | L1 |

## Direção estratégica (decisão: FASE A)

1. **A — Consolidar** 🔧 (1–2 sem): CI, QA T05/T04, orçamentos formais. ← **escolhida**
2. **D — Performance** ⚡ (1–2 sem): profiling, tuning num_ctx, keep-model.
3. **B — Escalar** 🏗️ (3–4 sem): camada 7B, novos agentes/domínios.
4. **C — Produto** 📦 (2–3 meses): CLI standalone, onboarding, v1.0.

Ordem recomendada: **A → D → B → C**. Publicar antes de consolidar = dívida técnica.

## Riscos principais

| Risco | Mitigação |
|---|---|
| Swap thrash entre 27B | `ollama stop` entre sessões pesadas; fallback para 14B em timeout |
| Estouro de contexto → vazio | Cap ~4k tokens embedados; nunca retry; C4 formaliza |
| T05 sem imagem na pasta padrão | Fluxo "avisa e pede caminho" já implementado (r5); teste C2 |
| Matemática silenciosa no 27B | B04: nothink-v2 acertou T02 (R$ 224,00) e T04/qa; manter asserts no CI e baterias de conferência (preciso/financeiro) |
| Hardware estacionário | 7B nas rotas leves (M1); monitoramento de acurácia (M4) |
| Primário degenera em sessão longa/contexto poluído (r13) | Executar mudanças de runtime (B02) em sessão curta e escopo mínimo; inspecionar saída bruta com truncamento; kit de rollback pronto |

## Próximo passo

**B02 — corte na fonte: APLICADO E FECHADO** (2026-09-20, r14 + r15):
1. Plug do provider `ollama-nothink` (npm `@ai-sdk/openai-compatible`, baseURL
   `http://127.0.0.1:11436/v1`) executado com `benchmarks/b02_plug.sh` (r14):
   backup ✅ → provider ✅ → proxy de pé ✅ → `/api/chat` e OpenAI JSON/SSE sem
   `thinking` ✅ → `opencode run --model ollama-nothink/qwen3-local` limpo ✅.
2. **Rota final (r15)** com `benchmarks/b02_agents.sh`: os **18 agentes locais**
   (`~/.config/opencode/agent/*.md`) apontam para `ollama-nothink/...` — corte na
   fonte vale para as rotas reais. Validação (bateria B02): 4 modelos via SDK
   (qwen3-local, vision, nothink-v2, megabrain-v2 27B thinking) limpos, subagente
   `preciso` de ponta a ponta (36) e 0 ocorrências de `thinking` no log do proxy.
   Achado: `opencode run --agent` não exercita o frontmatter de subagent (a sessão
   run usa o modelo principal da config) — os subagentes se validam via task.
3. Rollback em 1 comando por script (`b02_plug.sh --rollback` /
   `b02_agents.sh --rollback`); backup dos agentes em
   `~/.config/opencode/agent.bak-b02-20260920-073241`.

**B03 + B04 — smoke final e troca dos leves: FECHADOS** (2026-09-21, r16 + r17):
- B03: smoke dos 18 pela rota final (mesmos prompts da B01). Achados corrigidos
  no proxy na própria rodada: r16 (repassar `tools`/`tool_calls`, cortar raciocínio
  inline pelo marcador ` response`) e r16b (traduzir imagens `image_url` → campo
  `images` nativo + `arguments` string → objeto — o `ver` voltou a funcionar e
  identificou a pessoa). Resultado: 14 PASS · 2 parcial · 2 FAIL — 27B/vision 100%
  limpos; falhas todas do qwen3-local (financeiro vazou, revisor não corrigiu).
- B04/r17: decisão do usuário — os 7 leves (dados, financeiro, importador, preciso,
  qa, revisor, seo) trocados para `nothink-v2` com `benchmarks/b04_leves_nothink.sh`
  (backup `agent.bak-b04-20260921-005131`). Bateria comparativa: **7/7 PASS, 0
  vazamento** — financeiro e revisor (FAILs históricos) corrigidos; seo com erro de
  3 na contagem (149 real vs 152 informado). A config agora é **16 × nothink-v2 +
  megabrain-v2 (profundo) + vision (ver) — stack 100% 27B/vision, qwen3 fora da rota**.

Feito isso, os próximos eram **M1** (camada 7B) ou **M2** (profiling). 2026-09-21:
**M1 descartado por decisão do usuário** (precisão > velocidade — 14B já reprovava,
7B reabriria os FAILs) e **o profiling foi antecipado dentro da B06** (gargalo medido:
eval ~4,2 tok/s no split 43/57 CPU/GPU — teto físico da RX 6750 XT 12 GB).
Pendente: **push** dos commits locais (`0ac624a`, `37758d5`, `6f4fe1c`, `51e4cfa`,
`cfca09d`).

## Registro de baterias de teste (novo, 2026-09-17)

Cada bateria de teste vira **um arquivo** em `benchmarks/results/baterias/`,
com número sequencial, data, prompts e respostas verbatim e veredito — o
índice fica em `benchmarks/results/README.md`. Isso evita acumular dezenas de
conversas e deixa o histórico auditável. Primeira bateria: **B01** (smoke dos
18 agentes pós-endurecimento — 16 PASS, 1 parcial, 1 FAIL; ver JOURNAL
T16 r7). B02 (corte-na-fonte): self-tests do parser 3/3 (r12) e do proxy
**4/4** após o achado r13 (`message.thinking` — commit `6ebd77f`);
bateria completa do plug fica registrada aqui quando executada.