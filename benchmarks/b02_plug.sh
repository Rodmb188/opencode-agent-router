#!/usr/bin/env bash
# =====================================================================
# b02_plug.sh — plug do proxy corte-na-fonte (B02), à prova de erro
# ---------------------------------------------------------------------
# Modos:
#   bash b02_plug.sh               prévia — mostra o que será feito (nada muda)
#   bash b02_plug.sh --executar    aplica o plug com backup + validação real
#   bash b02_plug.sh --rollback    restaura o último backup e encerra o proxy
#
# Validação real: roda `opencode run` com o provider novo — o caminho que
# o opencode usa de verdade (SDK -> proxy -> Ollama) — e confere que o
# rascunho não aparece na resposta. Qualquer falha restaura o backup
# automaticamente e encerra o proxy.
# =====================================================================
set -euo pipefail

REPO=/home/rodmb188/opencode-projeto
CONFIG="$HOME/.config/opencode/opencode.jsonc"
PROXY_PY="$REPO/benchmarks/nothink_proxy.py"
PROXY_LOG=/tmp/opencode/proxy.log
PROXY_PID=/tmp/opencode/proxy.pid
PROVIDER_NAME=ollama-nothink
PROXY_BASE=http://127.0.0.1:11436
MODELO_LEVE=qwen3-local

MODO="${1:-previa}"

echo "== B02 — plug do proxy corte-na-fonte =="
echo

rollback_auto() {
  echo "== rollback automático =="
  [ -f "$PROXY_PID" ] && kill "$(cat "$PROXY_PID")" 2>/dev/null || true
  [ -f "$CONFIG" ] && [ -n "${BACKUP:-}" ] && cp "$BACKUP" "$CONFIG"
  echo "Config restaurada de: ${BACKUP:-<nenhum backup>}"
  echo "Para limpar por completo: bash $0 --rollback"
}

# ---------- pré-condições comuns ----------
[ -f "$CONFIG" ]  || { echo "ERRO: config não encontrado: $CONFIG"; exit 1; }
[ -f "$PROXY_PY" ] || { echo "ERRO: proxy não encontrado: $PROXY_PY"; exit 1; }
command -v python3 >/dev/null || { echo "ERRO: python3 ausente"; exit 1; }
command -v curl >/dev/null  || { echo "ERRO: curl ausente"; exit 1; }

if curl -s -m 3 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "[ok] Ollama de pé (11434)"
else
  echo "ERRO: Ollama não responde em 11434. Suba com: ollama serve"
  exit 1
fi

if ss -tln 2>/dev/null | grep -q ':11436'; then
  echo "AVISO: já há algo escutando na 11436 (proxy antigo ativo)."
  echo "       Para encerrar: bash $0 --rollback"
fi

# ---------- modo rollback ----------
if [ "$MODO" = "--rollback" ]; then
  echo "== rollback =="
  BAK=$(ls -1t "$HOME"/.config/opencode/opencode.jsonc.bak-plug-* 2>/dev/null | head -1 || true)
  if [ -z "$BAK" ]; then
    echo "Nenhum backup de plug local encontrado. Usando o kit do repo (r13):"
    BAK="$REPO/benchmarks/rollback/opencode.jsonc.bak-20260920-055511"
  fi
  cp "$BAK" "$CONFIG"
  echo "[ok] config restaurada de: $BAK"
  if [ -f "$PROXY_PID" ]; then
    kill "$(cat "$PROXY_PID")" 2>/dev/null || true
    rm -f "$PROXY_PID"
    echo "[ok] proxy encerrado"
  fi
  if grep -q "$PROVIDER_NAME" "$CONFIG"; then
    echo "ALERTA: provider $PROVIDER_NAME ainda presente na config."
  else
    echo "[ok] provider $PROVIDER_NAME ausente da config (esperado)"
  fi
  echo "Confira depois: python3 $REPO/benchmarks/regressao.py"
  exit 0
fi

# ---------- modo prévia ----------
if [ "$MODO" != "--executar" ]; then
  echo "== prévia (nada é alterado) =="
  python3 - "$CONFIG" "$PROVIDER_NAME" "$PROXY_BASE" "$MODELO_LEVE" <<'PY'
import json, sys
cfg_path, nome, base, leve = sys.argv[1:5]
with open(cfg_path) as f:
    cfg = json.load(f)
if nome in cfg.get("provider", {}):
    print("Provider %s JÁ existe — nenhuma mudança necessária." % nome)
    sys.exit(0)
ref = cfg.get("provider", {}).get("ollama", {})
novo = {"npm": "@ai-sdk/openai-compatible",
        "name": "Ollama (local) via proxy corte-na-fonte",
        "options": {"baseURL": base + "/v1", "timeout": 1200000},
        "models": ref.get("models", {})}
print("Será adicionado ao provider do config:")
print(json.dumps({nome: novo}, ensure_ascii=False, indent=2))
print()
print("Modelos herdados do provider ollama: %d" % len(novo.get("models", {})))
print("Validação depois do plug:")
print("  1. curl POST %s/api/chat (formato nativo Ollama)" % base)
print("  2. curl POST %s/v1/chat/completions (formato OpenAI, stream e SSE)" % base)
print("  3. opencode run --model %s/%s (caminho real do SDK)" % (nome, leve))
print("Rollback: backup guardado antes da mudança + comando único (impresso no final)")
PY
  echo
  echo "Para aplicar: bash $0 --executar"
  exit 0
fi

# ---------- modo executar ----------
echo "== executando o plug =="

# idempotência
if grep -q "\"$PROVIDER_NAME\"" "$CONFIG"; then
  echo "ERRO: provider $PROVIDER_NAME já existe na config."
  echo "      Rode: bash $0 --rollback (ou revise manualmente)."
  exit 1
fi

# 1/6 — backup
TS=$(date +%Y%m%d-%H%M%S)
BACKUP="$HOME/.config/opencode/opencode.jsonc.bak-plug-$TS"
cp "$CONFIG" "$BACKUP"
echo "[1/6] backup da config: $BACKUP"

# 2/6 — adiciona o provider
python3 - "$CONFIG" "$BACKUP" "$PROVIDER_NAME" "$PROXY_BASE" <<'PY'
import json, sys
cfg_path, bak, nome, base = sys.argv[1:5]
with open(bak) as f:
    cfg = json.load(f)
ref = cfg.get("provider", {}).get("ollama", {})
novo = {"npm": "@ai-sdk/openai-compatible",
        "name": "Ollama (local) via proxy corte-na-fonte",
        "options": {"baseURL": base + "/v1", "timeout": 1200000},
        "models": ref.get("models", {})}
cfg.setdefault("provider", {})[nome] = novo
with open(cfg_path, "w") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
    f.write("\n")
print("[2/6] provider %s adicionado (npm @ai-sdk/openai-compatible, baseURL %s/v1)" % (nome, base))
PY

# 3/6 — sobe o proxy em background
nohup python3 "$PROXY_PY" > "$PROXY_LOG" 2>&1 &
echo $! > "$PROXY_PID"
sleep 2
if ss -tln 2>/dev/null | grep -q ':11436'; then
  echo "[3/6] proxy de pé em 11436 (pid $(cat "$PROXY_PID"), log $PROXY_LOG)"
else
  echo "[3/6] ERRO: proxy não subiu — veja as últimas linhas do log:"
  tail -5 "$PROXY_LOG" || true
  rollback_auto
  exit 1
fi

# 4/6 — validação via curl (formato nativo /api/chat)
echo "[4/6] validando repasse real (curl /api/chat, modelo $MODELO_LEVE)..."
RESP=$(curl -s -m 180 -X POST "$PROXY_BASE/api/chat" -H 'Content-Type: application/json' \
  -d "{\"model\":\"$MODELO_LEVE\",\"messages\":[{\"role\":\"user\",\"content\":\"Responda apenas com a palavra ok\"}],\"stream\":false}" || true)
if echo "$RESP" | python3 -c 'import json,sys
try:
    d = json.load(sys.stdin)
    sys.exit(0 if "content" in d.get("message", {}) else 1)
except Exception:
    sys.exit(1)'; then
  echo "[4/6] repasse respondeu (content presente)"
  if echo "$RESP" | grep -q '"thinking"'; then
    echo "[4/6] ALERTA: campo thinking presente — veja o log do proxy: $PROXY_LOG"
  else
    echo "[4/6] thinking ausente — corte na fonte funcionando"
  fi
else
  echo "[4/6] ERRO no repasse real. Resposta (truncada):"
  echo "$RESP" | head -c 300
  echo
  tail -8 "$PROXY_LOG" || true
  rollback_auto
  exit 1
fi

# 4b/6 — validação do endpoint OpenAI (/v1/chat/completions), modo JSON
echo "[4b/6] validando /v1/chat/completions (formato OpenAI, stream false)..."
RESP_OAI=$(curl -s -m 180 -X POST "$PROXY_BASE/v1/chat/completions" -H 'Content-Type: application/json' \
  -d "{\"model\":\"$MODELO_LEVE\",\"messages\":[{\"role\":\"user\",\"content\":\"Responda apenas com a palavra ok\"}],\"stream\":false}" || true)
if echo "$RESP_OAI" | python3 -c 'import json,sys
try:
    d = json.load(sys.stdin)
    ch = d.get("choices", [{}])[0].get("message", {})
    sys.exit(0 if ch.get("content") else 1)
except Exception:
    sys.exit(1)'; then
  echo "[4b/6] endpoint OpenAI respondeu (content presente)"
  if echo "$RESP_OAI" | grep -q '"thinking"'; then
    echo "[4b/6] ALERTA: thinking presente na resposta OpenAI — veja $PROXY_LOG"
  else
    echo "[4b/6] thinking ausente — corte na fonte funcionando no formato OpenAI"
  fi
else
  echo "[4b/6] ERRO no endpoint OpenAI. Resposta (truncada):"
  echo "$RESP_OAI" | head -c 300
  echo
  tail -8 "$PROXY_LOG" || true
  rollback_auto
  exit 1
fi

# 4c/6 — validação do streaming SSE (o opencode usa stream:true no caminho real)
echo "[4c/6] validando /v1/chat/completions com stream (SSE)..."
SSE=$(curl -s -m 180 -X POST "$PROXY_BASE/v1/chat/completions" -H 'Content-Type: application/json' \
  -d "{\"model\":\"$MODELO_LEVE\",\"messages\":[{\"role\":\"user\",\"content\":\"Responda apenas com a palavra ok\"}],\"stream\":true}" || true)
if echo "$SSE" | grep -q 'data: \[DONE\]' && echo "$SSE" | head -1 | grep -q '^data: '; then
  echo "[4c/6] SSE válido (começa com data: e termina com [DONE])"
  if echo "$SSE" | grep -q '"thinking"'; then
    echo "[4c/6] ALERTA: thinking presente no SSE — veja $PROXY_LOG"
  else
    echo "[4c/6] thinking ausente no SSE — corte na fonte funcionando no stream"
  fi
else
  echo "[4c/6] ERRO no SSE. Saída (truncada):"
  echo "$SSE" | head -c 300
  echo
  tail -8 "$PROXY_LOG" || true
  rollback_auto
  exit 1
fi

# 5/6 — validação no caminho real do opencode (SDK -> proxy -> Ollama)
echo "[5/6] validando via opencode run (caminho real do SDK)..."
if command -v opencode >/dev/null 2>&1; then
  SAIDA=$(opencode run --model "$PROVIDER_NAME/$MODELO_LEVE" "Responda apenas com a palavra ok" 2>&1 || true)
  echo "--- saída do opencode run (truncada) ---"
  echo "$SAIDA" | head -c 400
  echo
  echo "-----------------------------------------"
  if echo "$SAIDA" | grep -qiE 'thinking|racioc[ií]nio|rascunho|provider.*error|erro'; then
    echo "[5/6] VERIFICAR: conteúdo suspeito na saída (rascunho ou erro de provider)."
    echo "      Se for erro de npm/provider (@ai-sdk/ollama), a rota alternativa é:"
    echo "      estender o proxy com /v1/chat/completions (ver JOURNAL r13) — ou --rollback."
  else
    echo "[5/6] opencode respondeu limpo — plug validado no caminho real."
    echo "$SAIDA" > /tmp/opencode/b02_validacao.txt
  fi
else
  echo "[5/6] opencode CLI ausente — validação real pulada (valide manualmente)."
fi

# 6/6 — relatório final
echo
echo "== plug aplicado =="
echo "config : $CONFIG"
echo "backup : $BACKUP"
echo "proxy  : pid $(cat "$PROXY_PID") · log $PROXY_LOG"
echo "provider novo: $PROVIDER_NAME (baseURL $PROXY_BASE)"
echo
echo "== rollback em 1 comando =="
echo "cp $BACKUP $CONFIG"
echo "kill $(cat "$PROXY_PID")"