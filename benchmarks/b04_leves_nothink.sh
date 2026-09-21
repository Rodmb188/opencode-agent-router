#!/usr/bin/env bash
# =====================================================================
# b04_leves_nothink.sh — B04: trocar os 7 agentes leves (qwen3-local)
# para nothink-v2 27B, seguindo a decisão do usuário (mitigação r16).
# ---------------------------------------------------------------------
# Modos:
#   bash b04_leves_nothink.sh            prévia — mostra o que será feito
#   bash b04_leves_nothink.sh --executar aplica com backup + validação
#   bash b04_leves_nothink.sh --rollback restaura o último backup b04
#
# Escopo: agentes que hoje usam `model: ollama-nothink/qwen3-local`:
#   dados, financeiro, importador, preciso, qa, revisor, seo (7)
# Todos passam para `ollama-nothink/nothink-v2`. Rollback em 1 comando.
# =====================================================================
set -euo pipefail

AGENTS_DIR="$HOME/.config/opencode/agent"
BAK_PREFIX="$HOME/.config/opencode/agent.bak-b04"
MODO="${1:-previa}"
ANTIGO='^model: ollama-nothink/qwen3-local$'
NOVO='model: ollama-nothink/nothink-v2'

echo "== B04 — leves qwen3-local -> nothink-v2 (27B) =="
echo

[ -d "$AGENTS_DIR" ] || { echo "ERRO: diretório de agentes ausente: $AGENTS_DIR"; exit 1; }

leves_find() {
  grep -rl '^model: ollama-nothink/qwen3-local$' "$AGENTS_DIR" 2>/dev/null | sort || true
}

# ---------- modo rollback ----------
if [ "$MODO" = "--rollback" ]; then
  echo "== rollback =="
  BAK=$(ls -1dt "${BAK_PREFIX}-"* 2>/dev/null | head -1 || true)
  if [ -z "$BAK" ]; then
    echo "Nenhum backup b04 encontrado (${BAK_PREFIX}-*)."
    exit 1
  fi
  rm -rf "$AGENTS_DIR"
  cp -a "$BAK" "$AGENTS_DIR"
  REST=$(grep -rl '^model: ollama-nothink/qwen3-local$' "$AGENTS_DIR" | wc -l)
  echo "[ok] agentes restaurados de: $BAK"
  echo "[ok] rotas ainda como nothink-v2 nos leves: $(grep -rl '^model: ollama-nothink/nothink-v2$' "$AGENTS_DIR" | wc -l) (0 esperado em dados/financeiro/importador/preciso/qa/revisor/seo)"
  echo "[ok] leves de volta em qwen3-local: $REST (7 esperado)"
  exit 0
fi

# ---------- modo prévia ----------
if [ "$MODO" != "--executar" ]; then
  echo "== prévia (nada é alterado) =="
  ARQ=$(leves_find)
  if [ -z "$ARQ" ]; then
    echo "Nenhum agente com 'model: ollama-nothink/qwen3-local' — já trocado ou diretório vazio."
    exit 0
  fi
  echo "Agentes leves encontrados: $(echo "$ARQ" | wc -l)"
  for f in $ARQ; do
    echo "  - $(basename "$f"): $(grep '^model:' "$f")  ->  $NOVO"
  done
  echo
  echo "Backup será criado em: ${BAK_PREFIX}-<timestamp>"
  echo "Para aplicar: bash $0 --executar"
  exit 0
fi

# ---------- modo executar ----------
echo "== executando a troca =="
ARQ=$(leves_find)
if [ -z "$ARQ" ]; then
  echo "Nada a trocar (nenhum agente em qwen3-local)."
  exit 1
fi
echo "Agentes a trocar ($(echo "$ARQ" | wc -l)):"
echo "$ARQ" | sed 's/^/  /'

TS=$(date +%Y%m%d-%H%M%S)
BAK="${BAK_PREFIX}-${TS}"
cp -a "$AGENTS_DIR" "$BAK"
echo "[ok] backup criado: $BAK"

for f in $ARQ; do
  sed -i "s|${ANTIGO}|${NOVO}|" "$f"
  echo "  [ok] $(basename "$f") -> $NOVO"
done

echo
echo "== validação =="
LEVES_NOVA=$(grep -rl '^model: ollama-nothink/nothink-v2$' "$AGENTS_DIR" | wc -l)
LEVES_REST=$(grep -rl '^model: ollama-nothink/qwen3-local$' "$AGENTS_DIR" | wc -l || true)
echo "agentes em nothink-v2 agora: $LEVES_NOVA"
echo "agentes ainda em qwen3-local: $LEVES_REST (0 esperado)"
[ "$LEVES_REST" = "0" ] || { echo "!! Ainda há leves em qwen3-local — verifique."; exit 1; }

echo
echo "== atendendo à regra do projeto (27B em sequência) =="
echo "Os 7 leves agora são 27B: rodar bateria comparativa em SEQUÊNCIA."
echo
echo "Rollback em 1 comando: bash $0 --rollback  (restaura $BAK)"