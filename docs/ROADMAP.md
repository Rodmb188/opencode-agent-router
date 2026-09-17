# ROADMAP — Roteador local de agentes (T00–T19)

> Documento de direção do projeto (criado a partir do planejamento de
> 2026-09-16). O usuário decidiu: **FASE A — CONSOLIDAR** primeiro.
> O diário técnico completo (medidas, falhas, decisões) vive em
> [ENGINEERING_JOURNAL.md](ENGINEERING_JOURNAL.md).
>
> **Status em 2026-09-17:** C3 ✅ · C4 ✅ · C2 ✅ (fluxos T05 com imagem real testados)
> · próximos: **C1** (CI reformulado — camada headless-friendly).

## Fluxograma do sistema

```
┌──────────────────────────────────────────────────────┐
│                       USUÁRIO                          │
│  "Faça X" │ "Explique Y" │ "Traduza Z" │ [imagem]     │
└───────────┬───────────────────────────────────────────┘
            ▼
┌──────────────────────────────────────────────────────┐
│      AGENTS.md (rotas T00–T19) + config + Regras      │
│      de Ferro (aprendidas de falha real)              │
└───────────┬───────────────────────────────────────────┘
            ▼
┌──────────────────────────────────────────────────────┐
│  ROTEADOR  ── delegação via opencode subagent         │
│   27B no-think: T06 redação │ T09 tutoria │ T10 resumo│
│   27B thinking: T12 profundo                          │
│   14B: T02 matemática │ T03 finanças │ T13 dados      │
│         T18 QA │ T19 conversão                        │
│   8B vision: T05 imagem/OCR                           │
│   Primário: T00/T01 trivial │ T04 busca + síntese     │
└───────────┬───────────────────────────────────────────┘
            ▼
┌──────────────────────────────────────────────────────┐
│            OLLAMA local (32GB RAM, sequencial)         │
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
```

## Metas

### 🟢 Curto prazo (≤ 1 semana)

| # | Objetivo | Pronto quando… | Esforço | Prioridade | Dependências |
|---|----------|----------------|---------|------------|--------------|
| C1 | Fechar CI (camada **headless-friendly** nos 20 níveis) | Estático completo no Actions + testes de modelo via Ollama direto; vivo continua checklist manual (o stack trava headless — dogfood sec. 14) | M | Alta | — |
| C2 ✅ | T05: fluxos com imagem testados | 2026-09-17: 2 imagens na pasta padrão → `ver` listou (`Casa.png`, `Homem.png`) e perguntou qual ✅; identificação: Lula (confiança alta) + isométrico de sobrevivência (estilo ✅, título não reconhecido — honesto) | S | Alta | — |
| C3 | ROADMAP.md versionado | Este arquivo no repo | S | Alta | — |
| C4 ✅ | Orçamento de contexto formalizado | Feito 2026-09-16 → [`CONTEXT_BUDGET.md`](CONTEXT_BUDGET.md) | S | Alta | — |

### 🟡 Médio prazo (≤ 1 mês)

| # | Objetivo | Pronto quando… | Esforço | Prioridade | Dependências |
|---|----------|----------------|---------|------------|--------------|
| M1 | Camada 7B para T00/T01/T02 | ≥90% da acurácia do 14B com 60% do tempo | M | Média | C1 |
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
| Matemática silenciosa no 27B | T02 → 14B é ferro; asserts no CI |
| Hardware estacionário | 7B nas rotas leves (M1); monitoramento de acurácia (M4) |

## Primeiro passo

Executar C4 + C2 (rápidos, sem dependência), depois C1 (reformulado para o limite
headless do stack). Registrar cada ajuste no ENGINEERING_JOURNAL.