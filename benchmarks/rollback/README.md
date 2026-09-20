# Kit de rollback — plug do proxy B02

Guardado em 2026-09-20 (antes do plug). Dois backups idênticos da config
`~/.config/opencode/opencode.jsonc`:

- `opencode.jsonc.bak-20260920-055511` (aqui no repo)
- `~/.config/opencode/opencode.jsonc.bak-20260920-055511` (no lugar de costume)

## Rollback em 1 comando

```bash
cp /home/rodmb188/opencode-projeto/benchmarks/rollback/opencode.jsonc.bak-20260920-055511 ~/.config/opencode/opencode.jsonc
```

Restaura o provider único `ollama` (baseURL `http://localhost:11434/v1`) e remove
o provider `ollama-nothink` adicionado pelo plug, voltando ao estado do commit
`d7b1f86`. O proxy pode ser encerrado com `kill` do PID anotado no JOURNAL r13;
a config restaurada não o referencia, então ele deixa de ser dependência.

## Verificação pós-rollback

- `python3 benchmarks/regressao.py` → PASS (estático)
- `grep -c ollama-nothink ~/.config/opencode/opencode.jsonc` → 0