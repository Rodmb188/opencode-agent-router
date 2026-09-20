#!/usr/bin/env bash
# =====================================================================
# b02_agents.sh — rota final do B02: apontar TODOS os agentes locais
# para o provider `ollama-nothink` (corte na fonte via proxy 11436).
# ---------------------------------------------------------------------
# Modos:
#   bash b02_agents.sh              prévia — mostra o que será feito (nada muda)
#   bash b02_agents.sh --executar   aplica a troca com backup + validação real
#   bash b02_agents.sh --rollback   restaura o último backup dos agentes
#
# Escopo: todos os arquivos em ~/.config/opencode/agent/*.md cuja linha
# `model:` comece com `ollama/` passam a usar `ollama-nothink/`. Hoje isso
# cobre os 18 agentes (8 com thinking — corte na fonte — e 10 sem thinking).
# Rollback em 1 comando (impresso no final). O proxy em si NÃO é encerrado
# pelo rollback (ele continua sendo o provider do plug B02).
# =====================================================================
set -euo pipefail

AGENTS_DIR="$HOME/.config/opencode/agent"
REPO=/home/rodmb188/opencode-projeto
PROVIDER_NAME=ollama-nothink
PROXY_BASE=http://127.0.0.1:11436
CONFIG="$HOME/.config/opencode/opencode.jsonc"
MODO="${1:-previa}"

echo "== B02 — rota final: agentes locais -> $PROVIDER_NAME (corte na fonte) =="
echo

# ---------- pré-condições comuns ----------
[ -d "$AGENTS_DIR" ] || { echo "ERRO: diretório de agentes ausente: $AGENTS_DIR"; exit 1; }
[ -f "$CONFIG" ] || { echo "ERRO: config não encontrado: $CONFIG"; exit 1; }

# lista os arquivos de agente com linha `model: ollama/`
agencts_find() {
  grep -rl '^model: ollama/' "$AGENTS_DIR" 2>/dev/null | sort || true
}

# ---------- modo rollback ----------
if [ "$MODO" = "--rollback" ]; then
  echo "== rollback =="
  BAK=$(ls -1dt "$HOME"/.config/opencode/agent.bak-b02-* 2>/dev/null | head -1 || true)
  if [ -z "$BAK" ]; then
    echo "Nenhum backup de agentes encontrado ($HOME/.config/opencode/agent.bak-b02-*)."
    echo "Estado atual dos agentes (esperado: nada a restaurar):"
    grep -r '^model: ' "$AGENTS_DIR" 2>/dev/null | sort || true
    exit 1
  fi
  rm -rf "$AGENTS_DIR"
  cp -a "$BAK" "$AGENTS_DIR"
  echo "[ok] agentes restaurados de: $BAK"
  REST=$(grep -rc '^model: ollama/' "$AGENTS_DIR" | awk -F: '{s+=$2} END{print s+0}')
  echo "[ok] rotas ainda em ollama/ direto: $REST (0 = tudo restaurado)"
  echo
  echo "Confira: grep -r '^model: ' $AGENTS_DIR"
  exit 0
fi

# ---------- modo prévia ----------
if [ "$MODO" != "--executar" ]; then
  echo "== prévia (nada é alterado) =="
  ARQ=$(agencts_find)
  if [ -z "$ARQ" ]; then
    echo "Nenhum agente com 'model: ollama/' — já está tudo em $PROVIDER_NAME (ou o diretório está vazio)."
    exit 0
  fi
  echo "Arquivos de agente encontrados: $(echo "$ARQ" | wc -l)"
  for f in $ARQ; do
    ANT=$(grep '^model: ollama/' "$f")
    NOV=$(echo "$ANT" | sed 's|^model: ollama/|model: ollama-nothink/|')
    echo "  - $(basename "$f"): $ANT  ->  $NOV"
  done
  echo
  echo "Backup será criado em: $HOME/.config/opencode/agent.bak-b02-<timestamp>"
  echo "Para aplicar: bash $0 --executar"
  exit 0
fi

# ---------- modo executar ----------
echo "== executando a troca das rotas =="

# pré-checagem: Ollama de pé
if curl -s -m 3 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "[ok] Ollama de pé (11434)"
else
  echo "ERRO: Ollama não responde em 11434. Suba com: ollama serve"; exit 1
fi

# pré-checagem: proxy de pé (formato OpenAI, POST — o proxy só atende POST)
if RESP=$(curl -s -m 30 -X POST "$PROXY_BASE/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3-local","messages":[{"role":"user","content":"Responda apenas com a palavra ok"}]}'); then
  if echo "$RESP" | python3 -c 'import json,sys
try:
    d=json.load(sys.stdin); c=d.get("choices",[{}])[0].get("message",{}).get("content","")
    sys.exit(0 if c else 1)
except Exception: sys.exit(1)'; then
    echo "[ok] proxy de pé em 11436 (respondeu content sem thinking)"
  else
    echo "ERRO: proxy não respondeu content. Saída (truncada):"; echo "$RESP" | head -c 300; exit 1
  fi
else
  echo "ERRO: proxy não respondeu em $PROXY_BASE. Suba com: python3 $REPO/benchmarks/nothink_proxy.py"
  exit 1
fi

# pré-checagem: provider no config
if grep -q "\"$PROVIDER_NAME\"" "$CONFIG"; then
  echo "[ok] provider $PROVIDER_NAME presente na config"
else
  echo "ERRO: provider $PROVIDER_NAME ausente da config. Rode primeiro: bash $REPO/benchmarks/b02_plug.sh --executar"
  exit 1
fi

# idempotência: nada para trocar?
ARQ=$(agencts_find)
if [ -z "$ARQ" ]; then
  echo "Nenhum agente em 'ollama/' — troca já aplicada (idempotente). Nada a fazer."
  exit 0
fi

# 1/4 — backup do diretório de agentes
TS=$(date +%Y%m%d-%H%M%S)
BACKUP="$HOME/.config/opencode/agent.bak-b02-$TS"
cp -a "$AGENTS_DIR" "$BACKUP"
echo "[1/4] backup dos agentes: $BACKUP ($(find "$BACKUP" -name '*.md' | wc -l) arquivos)"

# 2/4 — aplica a troca
N=0
for f in $ARQ; do
  sed -i 's|^model: ollama/|model: ollama-nothink/|' "$f"
  N=$((N+1))
done
echo "[2/4] rotas trocadas em $N arquivos de agente"

# 3/4 — validação estática: nenhuma rota ollama/ direta; todas ollama-nothink/
QTD_ANT=$(grep -rh '^model: ollama/' "$AGENTS_DIR" 2>/dev/null | wc -l || true)
QTD_NOV=$(grep -rh '^model: ollama-nothink/' "$AGENTS_DIR" 2>/dev/null | wc -l || true)
echo "[3/4] validação estática: ollama/ -> $QTD_ANT (esperado 0) · ollama-nothink/ -> $QTD_NOV"
if [ "$QTD_ANT" -ne 0 ] || [ "$QTD_NOV" -lt 1 ]; then
  echo "ERRO: validação estática falhou — restaurando do backup."
  rm -rf "$AGENTS_DIR"; cp -a "$BACKUP" "$AGENTS_DIR"
  exit 1
fi

# 4/4 — validação real: caminho do SDK com um agente com thinking (preciso)
echo "[4/4] validando no caminho real (opencode run --agent preciso)..."
if command -v opencode >/dev/null 2>&1; then
  SAIDA=$(opencode run --agent preciso "Quanto é 15% de 240? Responda apenas com o número." 2>&1 || true)
  echo "--- saída (truncada) ---"
  echo "$SAIDA" | head -c 400
  echo
  echo "------------------------"
  if echo "$SAIDA" | grep -qiE 'provider.*error|erro de rede|timeout|rascunho|racioc[ií]nio'; then
    echo "ALERTA: conteúdo suspeito na saída. Inspecione antes de confiar."
    echo "Se for erro de provider, restaure com: bash $0 --rollback"
  else
    echo "[4/4] agente com thinking respondeu limpo pelo proxy — rota validada."
  fi
else
  echo "[4/4] opencode CLI ausente — validação real pulada (valide manualmente)."
fi

# relatório final
echo
echo "== troca aplicada =="
echo "agentes : $AGENTS_DIR"
echo "backup  : $BACKUP"
echo "rotas   : $QTD_NOV em $PROVIDER_NAME · $QTD_ANT restantes em ollama/ direto"
echo
echo "== rollback em 1 comando =="
echo "rm -rf $AGENTS_DIR && cp -a $BACKUP $AGENTS_DIR"