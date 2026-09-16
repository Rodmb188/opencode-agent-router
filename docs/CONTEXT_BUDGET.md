# Orçamento de contexto — CONTEXT_BUDGET

> Fonte canônica dos limites de contexto do projeto (C4 do ROADMAP).
> Todo número aqui foi **medido** (ver JOURNAL) ou é **estimativa marcada** —
> nada é chute disfarçado. Ao alterar um `num_ctx` num Modelfile, atualize este
> doc **antes** do commit. Números validados em 2026-09-16.

## Tabela por modelo (medido)

| Modelo | Família | num_ctx | Tamanho | Cap embed por chamada | Comportamento ao estourar |
|---|---|---|---|---|---|
| `qwen3-local` (14B) | matemática/finanças/dados/QA/conversão | **8192** | 9.0 GB (Q4) | ~5.000 tokens (folga p/ resposta) | Não medido empiricamente — risco `exceed_context_size_error`/vazio; mitigado pelo cap (medir no M2 profiling) |
| `nothink-v2` (27B) | redação/tutoria/resumo/tradução/etc. | **12288** | 16 GB (Q4) | ~4.000 tokens | Vazio (`reason: length`) — **nunca retry**, reduzir escopo/chunk |
| `megabrain-v2` (27B) | análise profunda T12 | **12288** (herda de nothink-v2) | 16 GB (Q4) | ~4.000 tokens | Vazio (`reason: length`, medido: 8.675 input + 3.613 output = 12.288) — **nunca retry**, chunking |
| `vision` (8B VL) | imagens/OCR T05 | **16384** | 6.1 GB (Q4) | 1 imagem por turno (12 MP ≈ 8.520 tokens de imagem) + texto ≤ ~2k | Com 8192: `exceed_context_size_error` (medido). Com 16384: folga ~2×; cabe follow-up no mesmo turno |

## Custo de memória (KV cache)

- Custo medido: **≈ 384 KB por token** (fp16) — cada 4k tokens extras ≈ **1.5 GB RAM**.
- Implicação prática na regra do projeto: menos contexto simultâneo → menos swap → menos `ProviderHeaderTimeoutError`. Os 27B **sempre em sequência**, nunca em paralelo.

## Regras operacionais (decorrem dos limites acima)

1. **Nunca retry após retorno vazio** em 27B — o vazio é estouro de contexto (`reason: length`), não timeout. A ação é **reduzir o escopo** (chunk) e reenviar.
2. **Chunking**: textos maiores que o cap embed (ex.: README inteiro = 8.675 tokens) devem ir em pedaços. Portanto: **embedar na mensagem, nunca apontar arquivo** (subagentes não leem caminhos de forma confiável — medido).
3. **Vision**: 1 foto por turno. Foto de 12 MP (~8.5k tokens) + pergunta + resposta = ~9.6–10.1k; 12288 caberia com ~2.5k de folga, mas sem margem para follow-up; por isso 16384 (custo ~1.5 GB RAM a mais, disponível).
4. **T04**: material de `websearch` embutido compactado (trechos, números, faixas de preço). O `pesquisa` não tem `websearch` (provider ollama) — falha medida com 9.660 input tokens antes da resposta.
5. Estimativas a confirmar no M2 (profiling): cap real do 14B (8192) e o custo/latência de cada família sob carga real.

## Referências de medição

- `docs/ENGINEERING_JOURNAL.md`: seções *Memory engineering* (custo KV), T05 r4 (vision 12 MP / 8.520 / estouro 8192 / decisão 16384), sec. 10a (27B: 8.675+3.613=12.288 → vazio), T04 falha 9.660.
- `models/*.Modelfile`: os `PARAMETER num_ctx` atuais (12288 / 16384; 14B = 8192 no Ollama).
- `config/AGENTS.md`: regra de ferro do cap ~4k para o profundo (espelhado aqui).