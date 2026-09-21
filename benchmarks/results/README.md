# Registro de baterias de teste

Cada bateria de teste vira **um arquivo** em `baterias/`, com número
sequencial (B01, B02...), data, prompts enviados verbatim, respostas dos
subagentes verbatim e vereditos. O objetivo é acompanhar a evolução dos 18
agentes sem acumular dezenas de conversas dispersas — o registro vive no repo.

## Baterias registradas

| # | Data | Arquivo | Resultado geral |
|---|---|---|---|
| B01 | 2026-09-17 | [`baterias/B01_smoke18_pos-endurecimento_2026-09-17.md`](baterias/B01_smoke18_pos-endurecimento_2026-09-17.md) | 16 PASS · 1 parcial · 1 FAIL |
| B02 | 2026-09-20 | [`baterias/B02_rota-final-proxy_2026-09-20.md`](baterias/B02_rota-final-proxy_2026-09-20.md) | 6 PASS (rota final dos 18 agentes pelo proxy) · 1 descartado por achado |
| B03 | 2026-09-21 | [`baterias/B03_smoke18_rota-nothink-r16_2026-09-21.md`](baterias/B03_smoke18_rota-nothink-r16_2026-09-21.md) | 14 PASS · 2 parcial · 2 FAIL (27B e vision todos limpos; qwen3-local instável) |
| B04 | 2026-09-21 | [`baterias/B04_comparativo_leves-nothink_2026-09-21.md`](baterias/B04_comparativo_leves-nothink_2026-09-21.md) | **7 PASS · 0 FAIL** — 7 leves trocados qwen3→nothink-v2; vazamentos eliminados, FAILs históricos corrigidos |
| B05 | 2026-09-21 | [`baterias/B05_antiisca_2026-09-21.md`](baterias/B05_antiisca_2026-09-21.md) | **18 PASS · 0 FAIL · 0 regressão** — calibração anti-isca dos 18 frontmatters (107→39 negações, 0 "nunca", exemplos estrangeiros removidos) |

## Legado (antes do formato padrão)

Formato antigo, mantido para consulta histórica:

- `agentes_bateria/` — bateria de agentes no formato legado (ID + prompt + resposta).
- `readme_review_dogfood.md` — revisão A/B do README (dogfooding).
- `model_checks_*.log` — saídas headless do `model_checks.py` (C1).
- `regressao_*.log` — saídas headless do `regressao.py`.
- `test_results_*.json`, `writing_map.json`, `writing_outputs.txt`, `visao_teste.png` — materiais das primeiras validações.

## Regras do formato (a partir de B01)

- **Um arquivo por bateria**, nome `B0X_<objetivo>_<AAAA-MM-DD>.md`.
- **Cabeçalho com contexto**: data, regras em vigor, modelos, objetivo.
- **Cada teste**: número sequencial (T01, T02...), agente, hora, **prompt
  verbatim**, **resposta verbatim** (integral; truncado só com aviso),
  **veredito** (PASS / FAIL / ⚠ ressalva + observação).
- Resultados de conferências numéricas (ex.: `preciso`) têm o esperado
  declarado antes de rodar, para o veredito ser objetivo.