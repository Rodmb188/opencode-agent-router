#!/usr/bin/env bash
# b06_keepalive.sh — ajusta OLLAMA_KEEP_ALIVE do serviço ollama (systemd user)
# via drop-in, sem alterar o unit original. Backup + rollback em 1 comando.
#
# Uso:
#   bash b06_keepalive.sh            # prévia (mostra estado atual)
#   bash b06_keepalive.sh --executar # aplica o drop-in e reinicia o serviço
#   bash b06_keepalive.sh --rollback # remove o drop-in e reinicia o serviço
set -euo pipefail

DURACAO="${OLLAMA_KEEP_ALIVE_TARGET:-1h}"          # default: 1 hora
DROP_DIR="$HOME/.config/systemd/user/ollama.service.d"
DROP_FILE="$DROP_DIR/override.conf"
BACKUP_DIR="$HOME/.config/opencode/agent.bak-b06-keepalive-$(date +%Y%m%d-%H%M%S)"

echo "== alvo OLLAMA_KEEP_ALIVE: $DURACAO (para mudar: OLLAMA_KEEP_ALIVE_TARGET=<valor> bash $0 --executar)"

case "${1:-}" in
  --executar)
    mkdir -p "$BACKUP_DIR"
    if [ -f "$DROP_FILE" ]; then cp "$DROP_FILE" "$BACKUP_DIR/override.conf.bak"; fi
    mkdir -p "$DROP_DIR"
    cat > "$DROP_FILE" <<EOF
[Service]
Environment=OLLAMA_KEEP_ALIVE=$DURACAO
EOF
    systemctl --user daemon-reload
    systemctl --user restart ollama
    echo "drop-in aplicado: $DROP_FILE"
    sleep 2
    echo "== env no processo:"
    tr '\0' '\n' < /proc/$(pgrep -f "ollama serve" | head -1)/environ | grep OLLAMA_KEEP_ALIVE || true
    echo "backup: $BACKUP_DIR"
    ;;
  --rollback)
    if [ -f "$DROP_FILE" ]; then
      rm -f "$DROP_FILE"
      rmdir "$DROP_DIR" 2>/dev/null || true
      systemctl --user daemon-reload
      systemctl --user restart ollama
      echo "drop-in removido; valor retorna ao do unit original (15m)"
    else
      echo "não há drop-in para remover"
    fi
    ;;
  *)
    echo "== prévia:"
    echo "DROP_FILE: $DROP_FILE"
    echo "unit original usa:"
    systemctl --user cat ollama | grep -E "OLLAMA_KEEP_ALIVE" || echo "(não definido)"
    echo "rodar: bash $0 --executar | --rollback"
    ;;
esac