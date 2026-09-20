#!/usr/bin/env python3
# nothink_proxy.py — corte NA FONTE (B02) para o stack T16 r12
#
# O QUE E: um servidor HTTP local (stdlib pura, sem dependencias) que fica na
# porta 11436 e faz papel de "recepcao" entre o opencode e o Ollama real
# (127.0.0.1:11434). Ele recebe a chamada do opencode, repassa ao Ollama,
# e na resposta aplica a MESMA regra deterministica do nothink_parser —
# mas ANTES de devolver ao opencode. Ou seja: o rascunho (rascunho) e o
# charset estrangeiro sao cortados NA FONTE, antes de qualquer modelo ler.
#
# Por que isso importa: na rodada B01, o vazamento CJK apareceu em agentes
# DIFERENTES a cada execucao (nao "3 fixos"). Se o corte vive so na camada
# de apresentacao do primario, ele depende de o primario receber e aplicar
# a regra. Com o corte na fonte, NENHUM agente carrega o rascunho no proprio
# contexto — a solucao nao depende de lembrar "quais 3 vazaram".
#
# USO:
#   python3 benchmarks/nothink_proxy.py                 # sobe na 11436
#   OLLAMA_UPSTREAM=127.0.0.1:11434 python3 ...         # aponta pro Ollama real
#   PORT=11436 python3 ...                              # troca a porta
#
# SELF-TEST (sem precisar do Ollama):
#   python3 benchmarks/nothink_proxy.py --self-test     # 3/3
#
# COMO PLUGAR NO OPEncode (uma linha no provider do opencode):
#   "ollama-nothink": { "npm": "@ai-sdk/ollama", "options": { "baseURL": "http://127.0.0.1:11436" }, "models": { "nothink": { "name": "qwen3:8b" } } }
# E apontar os agentes com thinking para "ollama-nothink/nothink".
# O proxy repassa a porta 11436 -> 11434 e corta o rascunho antes de devolver.

import json
import re
import sys
import unicodedata
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---- bloco 1: parser determinístico REUTILIZADO do nothink_parser ---------
# (mesmo núcleo; importa a função que já passou 3/3 no self-test anterior)

from nothink_parser import sanitize  # fonte única (nothink global)

def _eh_latino(ch):
    """Um char é latino se: ASCII base, acentos latinos, cifrão, %, dígitos,
    espaços e pontuação latina comum. Negativo: remove por bloco Unicode."""
    o = ord(ch)
    if o < 0x80:
        return True
    if 0xC0 <= o <= 0x24F:      # Latin-1 suplemento + Extended-A (acentos)
        return True
    if 0x20A0 <= o <= 0x20BF:   # símbolos de moeda (R$, €→ não usado; R$ sim)
        return True
    return False

# sanitize vem de nothink_parser (import na linha 40, fonte única).
# NÃO redefinir localmente aqui: a fonte única é o parser; cópia local = drift.

def sanitize_stream_resposta(resposta_json):
    """Aplica a sanitização DENTRO do objeto de resposta do Ollama
    (formato /api/chat). Preserva o resto (modelo, timestamps)."""
    if isinstance(resposta_json, dict):
        msg = resposta_json.get("message", {})
        if isinstance(msg, dict) and "content" in msg:
            msg["content"] = sanitize(msg["content"])
        return resposta_json
    return resposta_json

# ---- bloco 2: proxy HTTP local ---------------------------------------------

_DEFAULT_UPSTREAM = "127.0.0.1:11434"
_DEFAULT_PORT = 11436

class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # silencia log de request
        pass

    def _upstream(self):
        return getattr(self.server, "upstream", _DEFAULT_UPSTREAM)

    def do_POST(self):
        if self.path.rstrip("/") not in ("/api/chat", "/api/generate"):
            self.send_error(404, "use /api/chat")
            return
        try:
            tamanho = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(tamanho) if tamanho else b"{}"
            req = json.loads(body.decode("utf-8"))
        except Exception as e:
            self.send_error(400, "json invalido: %s" % e)
            return

        # Força não-streaming (resposta completa de uma vez, mais simples
        # de sanitizar de forma determinística na borda)
        req["stream"] = False
        if "options" not in req:
            req["options"] = {}
        req["options"].setdefault("num_ctx", 12288)

        url = "http://%s%s" % (self._upstream(), self.path)
        data = json.dumps(req).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        try:
            r = urllib.request.urlopen(
                urllib.request.Request(url, data=data, headers=headers),
                timeout=300,
            )
            cru = r.read().decode("utf-8")
        except Exception as e:
            self.send_error(502, "falha ao repassar ao Ollama: %s" % e)
            return

        try:
            resp = json.loads(cru)
        except Exception:
            # resposta não-JSON (ex.: erro do Ollama com corpo texto) — devolve cru
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(cru.encode())))
            self.end_headers()
            self.wfile.write(cru.encode())
            return

        resp = sanitize_stream_resposta(resp)
        saida = json.dumps(resp, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(saida)))
        self.end_headers()
        self.wfile.write(saida)

    do_PUT = do_POST

# ---- bloco 3: self-test determinístico (sem Ollama) -------------------------

def _self_test():
    # Entradas geradas em runtime (chr), sem literal estrangeiro no fonte
    cjk = chr(0x9897)      # ideograma
    kana = chr(0x3044)     # hiragana 'i'
    ciril = chr(0x0416)    # cirílico Zhe

    cenario_rascunho = (
        "RASCUNHO: calculei passo a passo e pensei em %s e %s por aqui; "
        "depois confiro. </thinking>\n\n"
        "**Resposta:** 2 + 2 = 4, aplicando a formula s = a + b." % (cjk, kana)
    )
    cenario_limpo = "Taxa de 5% sobre 200 = 10. Resultado parcial: R$ 200. Resultado: R$ 210."

    saida = sanitize(cenario_rascunho)
    ok1 = (cjk not in saida) and (kana not in saida) and ("2 + 2 = 4" in saida) and ("RASCUNHO" not in saida)
    ok2 = sanitize(cenario_limpo) == cenario_limpo
    ok3 = (ciril not in sanitize("Valor %s misturado %s fim" % (cjk, ciril)))

    print("self-test:")
    print("  corta rascunho + rede charset :", "PASS" if ok1 else "FAIL")
    print("  texto limpo segue intacto      :", "PASS" if ok2 else "FAIL")
    print("  cira/ideograma removidos       :", "PASS" if ok3 else "FAIL")
    return ok1 and ok2 and ok3

if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(0 if _self_test() else 1)

    porto = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else _DEFAULT_PORT
    if len(sys.argv) > 1 and not sys.argv[1].isdigit:
        sys.exit("uso: python3 nothink_proxy.py [porta] [--self-test]")

    upstream = sys.argv[2] if len(sys.argv) > 2 else _DEFAULT_UPSTREAM

    server = ThreadingHTTPServer(("127.0.0.1", porto), _Handler)
    server.upstream = upstream
    print("corte-na-fonte B02 ativo: 127.0.0.1:%d -> %s (32260; sanitizacao na borda)" % (porto, upstream))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("  encerrado.")
