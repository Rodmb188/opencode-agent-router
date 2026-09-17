# Registro de baterias de teste

Cada bateria de teste vira **um arquivo** em `baterias/`, com número
sequencial (B01, B02...), data, prompts enviados verbatim, respostas dos
subagentes verbatim e vereditos. O objetivo é acompanhar a evolução dos 18
agentes sem acumular dezenas de conversas dispersas — o registro vive no repo.

## Baterias registradas

| # | Data | Arquivo | Resultado geral |
|---|---|---|---|
| B01 | 2026-09-17 | [`baterias/B01_smoke18_pos-endurecimento_2026-09-17.md`](baterias/B01_smoke18_pos-endurecimento_2026-09-17.md) | 16 PASS · 1 parcial · 1 FAIL |

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