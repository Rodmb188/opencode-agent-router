# Orçamento de contexto — CONTEXT_BUDGET

> Fonte canônica dos limites de contexto do projeto (C4 do ROADMAP).
> Todo número aqui foi **medido** (ver JOURNAL) ou é **estimativa marcada** —
> nada é chute disfarçado. Ao alterar um `num_ctx` num Modelfile, atualize este
> doc **antes** do commit. Números validados em 2026-09-16.

## Tabela por modelo (medido)

| Modelo | Família | num_ctx | Tamanho | Cap embed por chamada | Comportamento ao estourar |
|---|---|---|---|---|---|
| `nothink-v2` (27B) | **todos os agentes de texto** (leves T02/T03/T07/T13/T18/T19 e onda 2 — desde a B04/r17; 16 agentes) | **16384** | 16 GB (Q4) | ~4.000 tokens | Vazio (`reason: length`) — **nunca retry**, reduzir escopo/chunk |
| `megabrain-v2` (27B) | análise profunda T12 | **16384** (herda de nothink-v2) | 16 GB (Q4) | ~4.000 tokens | Vazio (`reason: length`, medido: 8.675 input + 3.613 output = 12.288 no 12288) — **nunca retry**, chunking |
| `vision` (8B VL) | imagens/OCR T05 | **16384** | 6.1 GB (Q4) | 1 imagem por turno (12 MP ≈ 8.520 tokens de imagem) + texto ≤ ~2k | Com 8192: `exceed_context_size_error` (medido). Com 16384: folga ~2×; cabe follow-up no mesmo turno |

> **Nota (r17/B04):** `qwen3-local` (14B) **saiu da rota** — vazava raciocínio
> inline (o corte do proxy não alcança inline sem o marcador); os 7 agentes que
> o usavam (dados, financeiro, importador, preciso, qa, revisor, seo) passaram
> para `nothink-v2` (27B, num_ctx 12288 à época — hoje 16384, ver nota 2026-09-29; cap ~4k). Linha de referência histórica:
> 14B = 8192 / ~5k embed / 9.0 GB.

> **Nota (2026-09-29):** os 27B subiram **12288 → 16384** (nothink-v2,
> megabrain-v2 e os legados). Motivo medido na sessão "O Pescador": com o
> prompt fixo do opencode v2 (system + tools), o request final estourou
> (`request (14777 tokens) exceeds the available context size (12288)` → 502)
> e, após o fix de compactação, o resumo da compactação era truncado pelo cap
> de saída (`Compaction summary reached the output token limit` →
> StepFailedError → sessão morta). Solução em duas frentes: `num_ctx` 16384
> (+1.5 GB RAM de KV, mesma decisão do vision) e caps de saída subidos —
> nothink 1536→2500, megabrain 2500→3072 (anti-loop preservado). O **proxy
> corte-na-fonte** aplica o `num_ctx` por família via `options`; os Modelfiles
> não mudaram (ref. de medição abaixo).

## Custo de memória (KV cache)

- Custo medido: **≈ 384 KB por token** (fp16) — cada 4k tokens extras ≈ **1.5 GB RAM**.
- Implicação prática na regra do projeto: menos contexto simultâneo → menos swap → menos `ProviderHeaderTimeoutError`. Os 27B **sempre em sequência**, nunca em paralelo.

## Regras operacionais (decorrem dos limites acima)

1. **Nunca retry após retorno vazio** em 27B — o vazio é estouro de contexto (`reason: length`), não timeout. A ação é **reduzir o escopo** (chunk) e reenviar.
2. **Chunking**: textos maiores que o cap embed (ex.: README inteiro = 8.675 tokens) devem ir em pedaços. Portanto: **embedar na mensagem, nunca apontar arquivo** (subagentes não leem caminhos de forma confiável — medido).
3. **Vision**: 1 foto por turno. Foto de 12 MP (~8.5k tokens) + pergunta + resposta = ~9.6–10.1k; 12288 caberia com ~2.5k de folga, mas sem margem para follow-up; por isso 16384 (custo ~1.5 GB RAM a mais, disponível).
4. **T04**: websearch Exa (key local — free tier) para TODOS os modelos e agentes LOCAIS (`websearch.provider: exa` no config GLOBAL); máx. 1–2 buscas por subagente, trechos curtos ~4k tokens. O Big Pickle/provider opencode segue na forma padrão (infra — nunca a Exa). Aderência dura: entregar links absolutos, nunca terminar com pergunta. Os 18 subagentes têm `websearch: allow` desde 25/09/2026. Falha histórica medida com 9.660 input tokens antes da resposta (versão antiga, sem a tool).
5. Estimativas a confirmar no M2 (profiling): cap real do 14B (8192) e o custo/latência de cada família sob carga real.

## Referências de medição

- `docs/ENGINEERING_JOURNAL.md`: seções *Memory engineering* (custo KV), T05 r4 (vision 12 MP / 8.520 / estouro 8192 / decisão 16384), sec. 10a (27B: 8.675+3.613=12.288 → vazio), T04 falha 9.660.
- `models/*.Modelfile`: os `PARAMETER num_ctx` nos Modelfiles (14B = 8192; 27B/vision = 12288/16384), **com override do proxy desde 2026-09-29**: o corte-na-fonte força `options.num_ctx` por família (27B/vision = 16384, 14B = 8192) a cada request.
- `config/AGENTS.md`: regra de ferro do cap ~4k para o profundo (espelhado aqui).