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

---

# Kit de rollback — rota final B02 (agentes locais, r15)

Troca feita em 2026-09-20 (r15) com `benchmarks/b02_agents.sh`: os 18 arquivos
`~/.config/opencode/agent/*.md` passaram de `model: ollama/...` para
`model: ollama-nothink/...`. Backup guardado no lugar de costume:

- `~/.config/opencode/agent.bak-b02-20260920-073241` (18 arquivos)

## Rollback dos agentes em 1 comando

```bash
rm -rf ~/.config/opencode/agent && cp -a ~/.config/opencode/agent.bak-b02-20260920-073241 ~/.config/opencode/agent
```

Também disponível por script: `bash benchmarks/b02_agents.sh --rollback`.

Restaura as 18 rotas diretas `ollama/...` (sem o corte na fonte). O proxy e o
provider `ollama-nothink` continuam de pé — o plug em si desfaz-se com
`bash benchmarks/b02_plug.sh --rollback` + os comandos do README acima.

## Verificação pós-rollback

- `grep -rh '^model: ollama/' ~/.config/opencode/agent/ | wc -l` → 18
- `grep -rh '^model: ollama-nothink/' ~/.config/opencode/agent/ | wc -l` → 0