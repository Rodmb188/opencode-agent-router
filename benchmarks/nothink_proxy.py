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
import os
import re
import sys
import time
import unicodedata
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---- bloco 1: parser determinístico REUTILIZADO do nothink_parser ---------
# (mesmo núcleo; importa a função que já passou 3/3 no self-test anterior)

from nothink_parser import sanitize, remove_nao_latino  # fonte única (nothink global)

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

def _remove_tool_call_nao_parseado(texto):
    """Remove do content o texto de tool_call que o Ollama NAO parseou
    (o modelo emitiu <tool_call>...{json}...</tool_call> como texto corrido;
    quando o Ollama parseia, o texto nao aparece e a chamada vai estruturada).
    Cobre dois formatos: com abertura <tool_call> e sem abertura (so o
    fechamento </tool_call> apos o JSON cru)."""
    t = re.sub(r"<tool_call>.*?</tool_call>", "", texto, flags=re.DOTALL)
    if "</tool_call>" in t:  # modelo emitiu so o JSON + fechamento
        idx = t.find("</tool_call>")
        t = t[idx + len("</tool_call>"):]
    return t

def _corta_rascunho_inline_qwen(texto):
    """O qwen3, mesmo com tools, as vezes emite o raciocinio inline no content
    terminado pelo marcador do template (token destokenizado como ' response').
    Corta tudo ate o fim do marcador; o que sobra e a resposta final.
    Aceita o marcador com quebra antes OU so espaco antes (variacoes do token)."""
    m = re.search(r"(?:^|[ \t\r\n])response[\r\n]", texto)
    if m:
        resto = texto[m.end():].strip()
        if len(remove_nao_latino(resto)) > 1:
            return resto
    return texto

def sanitize_stream_resposta(resposta_json):
    """Aplica a sanitização DENTRO do objeto de resposta do Ollama
    (formato /api/chat). Preserva o resto (modelo, timestamps).

    Remove o campo "thinking" da mensagem: o raciocínio do modelo chega
    do Ollama num campo separado (message.thinking, em ingês) e o rascunho
    NÃO deve sair da fonte — nem sanitizado, removido em bloco."""
    if isinstance(resposta_json, dict):
        msg = resposta_json.get("message", {})
        if isinstance(msg, dict):
            if "content" in msg:
                conteudo = msg["content"]
                conteudo = _remove_tool_call_nao_parseado(conteudo)
                conteudo = _corta_rascunho_inline_qwen(conteudo)
                msg["content"] = sanitize(conteudo)
            msg.pop("thinking", None)
            msg.pop("thinking_duration", None)
        return resposta_json
    return resposta_json

# ---- bloco 1b: tradução OpenAI <-> Ollama (endpoint /v1/chat/completions) ----

def traduz_oai_para_ollama(req):
    """Converte um request do formato OpenAI (openai-compatible SDK) para o
    corpo nativo do Ollama (/api/chat). Sempre pede stream=False ao Ollama;
    o streaming é reconstruído na resposta, após o corte do rascunho."""
    corpo = {
        "model": req.get("model", ""),
        "messages": req.get("messages", []),
        "stream": False,
    }
    # imagens do modelo de visao (SDK manda como content parts OpenAI):
    # o Ollama nativo nao aceita array no content — converte para content
    # string + campo 'images' (base64) por mensagem.
    for msg in corpo["messages"]:
        if isinstance(msg, dict):
            _converte_content_parts(msg)
    # tools do modelo (function calling): o Ollama precisa delas no corpo para
    # o qwen3 manter o raciocinio no campo 'thinking' (separado). SEM tools o
    # qwen3 embeve o raciocinio DENTRO do content e o corte do campo thinking
    # nao basta — achado B02/r16, o vazamento aparecia no caminho real do
    # SDK (subagents), que sempre manda tools.
    plataforma_oai = req.get("tools")
    if plataforma_oai:
        corpo["tools"] = req["tools"]
        # argumentos dos tool_calls do historico chegam do SDK em formato
        # OpenAI (string JSON); o /api/chat nativo do Ollama so aceita OBJETO.
        # Sem essa conversao, requests com historico de tool_call (2o turno
        # do fluxo de agente) caem com 400/502.
        for msg in corpo["messages"]:
            if isinstance(msg, dict) and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    fn = tc.get("function") or {}
                    args = fn.get("arguments")
                    if isinstance(args, str) and args.strip():
                        try:
                            fn["arguments"] = json.loads(args)
                        except json.JSONDecodeError:
                            pass  # deixa como esta; o Ollama devolve o erro
    if req.get("tool_choice") is not None:
        corpo["tool_choice"] = req["tool_choice"]
    opts = {"num_ctx": 12288}
    if "temperature" in req:
        opts["temperature"] = req["temperature"]
    if "max_tokens" in req:
        opts["num_predict"] = req["max_tokens"]
    if req.get("options") and isinstance(req["options"], dict):
        opts.update(req["options"])
    corpo["options"] = opts
    return corpo

def _converte_content_parts(mensagem):
    """O SDK OpenAI manda imagens como content em LISTA de parts
    ({type: text} / {type: image_url, image_url: {url: data:...}}). O Ollama
    nativo (/api/chat) NAO aceita array no content: espera content string +
    campo 'images' com base64 puro (sem o prefixo data:...). Converte aqui,
    preservando a ordem dos textos. Sem parts de imagem, devolve intocado."""
    conteudo = mensagem.get("content")
    if not isinstance(conteudo, list):
        return
    textos = []
    imagens = []
    for part in conteudo:
        if not isinstance(part, dict):
            continue
        t = part.get("type")
        if t == "text":
            textos.append(part.get("text", ""))
        elif t == "image_url":
            url = (part.get("image_url") or {}).get("url", "")
            b64 = url.split(",", 1)[1] if "," in url else url
            if b64:
                imagens.append(b64)
    mensagem["content"] = "\n".join(textos) if textos else ""
    if imagens:
        mensagem["images"] = imagens

def _normaliza_tool_calls(tool_calls):
    """Converte tool_calls do formato Ollama para o OpenAI (que o SDK
    openai-compatible espera): arguments como string JSON, com id e type."""
    saida = []
    for i, tc in enumerate(tool_calls or []):
        fn = tc.get("function", {}) or {}
        args = fn.get("arguments", {})
        if not isinstance(args, str):
            args = json.dumps(args, ensure_ascii=False)
        saida.append({
            "id": tc.get("id") or ("call_%d" % (i + 1)),
            "type": "function",
            "function": {"name": fn.get("name", ""), "arguments": args},
        })
    return saida

def traduz_ollama_para_oai(resposta_ollama, model, stream_pedido):
    """Converte a resposta já sanitizada do Ollama para o formato OpenAI
    (chat.completion). O 'thinking' nem entra aqui: é descartado por
    construção na tradução (o content é o único campo levado)."""
    mensagem = resposta_ollama.get("message", {}) or {}
    conteudo = mensagem.get("content", "")
    tool_calls = _normaliza_tool_calls(mensagem.get("tool_calls"))
    agora = int(time.time())
    base = {"id": "chatcmpl-local", "created": agora, "model": model}
    msg_oai = {"role": "assistant", "content": conteudo}
    if tool_calls:
        msg_oai["tool_calls"] = tool_calls
    if not stream_pedido:
        return {
            **base,
            "object": "chat.completion",
            "choices": [{
                "index": 0,
                "message": msg_oai,
                "finish_reason": "stop",
            }],
        }
    chunks = []
    if conteudo:
        chunks.append(
            {**base, "object": "chat.completion.chunk",
             "choices": [{"index": 0, "delta": {"role": "assistant", "content": conteudo}, "finish_reason": None}]}
        )
    if tool_calls:
        chunks.append(
            {**base, "object": "chat.completion.chunk",
             "choices": [{"index": 0, "delta": {"role": "assistant", "tool_calls": tool_calls}, "finish_reason": None}]}
        )
    chunks.append(
        {**base, "object": "chat.completion.chunk",
         "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
    )
    corpo_sse = "".join("data: %s\n\n" % json.dumps(c, ensure_ascii=False) for c in chunks)
    return corpo_sse + "data: [DONE]\n\n"

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
        caminho = self.path.rstrip("/")
        eh_openai = caminho == "/v1/chat/completions"
        if caminho not in ("/api/chat", "/api/generate", "/v1/chat/completions"):
            self.send_error(404, "caminho nao suportado: %s" % caminho)
            return
        try:
            tamanho = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(tamanho) if tamanho else b"{}"
            req = json.loads(body.decode("utf-8"))
        except Exception as e:
            self.send_error(400, "json invalido: %s" % e)
            return

        if os.environ.get("PROXY_DEBUG"):
            print("REQ %s %s" % (self.path, body.decode("utf-8")[:60000]), flush=True)

        # Internamente SEMPRE stream=False ao Ollama: resposta completa de uma
        # vez, mais simples de sanitizar de forma determinística na borda.
        if eh_openai:
            stream_pedido = bool(req.get("stream", False))
            modelo = req.get("model", "")
            corpo_up = traduz_oai_para_ollama(req)
            url = "http://%s/api/chat" % self._upstream()
        else:
            stream_pedido = False
            modelo = req.get("model", "")
            corpo_up = req
            corpo_up["stream"] = False
            if "options" not in corpo_up:
                corpo_up["options"] = {}
            corpo_up["options"].setdefault("num_ctx", 12288)
            url = "http://%s%s" % (self._upstream(), self.path)

        data = json.dumps(corpo_up).encode("utf-8")
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
        if eh_openai:
            if stream_pedido:
                corpo = traduz_ollama_para_oai(resp, modelo, True).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)
                return
            saida = json.dumps(
                traduz_ollama_para_oai(resp, modelo, False), ensure_ascii=False
            ).encode("utf-8")
        else:
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
    # cenário do achado r13: Ollama devolve message.thinking separado; o rascunho
    # nao deve sair da fonte NEM sanitizado — removido em bloco
    resposta_tipo_ollama = {
        "model": "qwen3-local",
        "message": {"role": "assistant", "content": "resposta limpa", "thinking": "pensei em %s em ingles" % cjk},
        "done": True,
    }
    saida4 = sanitize_stream_resposta(resposta_tipo_ollama)
    msg4 = saida4.get("message", {})
    ok4 = ("thinking" not in msg4) and ("thinking_duration" not in msg4) and (msg4["content"] == "resposta limpa")

    # cenário do endpoint /v1/chat/completions: request OpenAI vira corpo
    # Ollama nativo (stream sempre False dentro do proxy)
    req_oai = {
        "model": "qwen3-local",
        "messages": [{"role": "user", "content": "ola"}],
        "stream": True,
        "temperature": 0.2,
        "max_tokens": 40,
    }
    corpo_up = traduz_oai_para_ollama(req_oai)
    ok5 = (
        corpo_up["model"] == "qwen3-local"
        and corpo_up["stream"] is False
        and len(corpo_up["messages"]) == 1
        and corpo_up["options"]["num_ctx"] == 12288
        and corpo_up["options"]["temperature"] == 0.2
        and corpo_up["options"]["num_predict"] == 40
    )

    # resposta do Ollama (com thinking) vira chat.completion OpenAI SEM thinking;
    # o modo stream devolve SSE com [DONE] no fim
    resp_ollama = {
        "model": "qwen3-local",
        "message": {"role": "assistant", "content": "resposta ok %s" % cjk, "thinking": "rascunho %s" % cjk},
        "done": True,
    }
    resp_sanitizada = sanitize_stream_resposta(resp_ollama)
    resp_oai = traduz_ollama_para_oai(resp_sanitizada, "qwen3-local", False)
    msg_oai = resp_oai["choices"][0]["message"]
    ok6 = (
        resp_oai["object"] == "chat.completion"
        and msg_oai["content"] == "resposta ok"
        and "thinking" not in msg_oai
        and resp_oai["choices"][0]["finish_reason"] == "stop"
    )
    sse = traduz_ollama_para_oai(resp_sanitizada, "qwen3-local", True)
    ok7 = sse.startswith("data: ") and sse.rstrip().endswith("data: [DONE]") and cjk not in sse

    # achado r16: o request do SDK manda tools; a tradução deve repassá-las ao
    # Ollama (sem tools, o qwen3 embeve o raciocínio no content e o corte do
    # campo thinking deixa de dar conta)
    req_oai_tools = {
        "model": "qwen3-local",
        "messages": [{"role": "user", "content": "ola"}],
        "tools": [{"type": "function", "function": {"name": "ler", "description": "le", "parameters": {"type": "object", "properties": {}}}}],
        "tool_choice": "auto",
        "stream": True,
    }
    corpo_up2 = traduz_oai_para_ollama(req_oai_tools)
    ok8 = (
        corpo_up2.get("tools") == req_oai_tools["tools"]
        and corpo_up2.get("tool_choice") == "auto"
    )

    # resposta do Ollama com tool_calls vira OpenAI com id/type e arguments em
    # string JSON (formato que o SDK openai-compatible espera)
    resp_ollama_tc = {
        "model": "qwen3-local",
        "message": {"role": "assistant", "content": "",
                    "tool_calls": [{"function": {"name": "ler", "arguments": {"arquivo": "x.txt"}}}]},
        "done": True,
    }
    resp_tc_sanitizada = sanitize_stream_resposta(resp_ollama_tc)
    out_tc = traduz_ollama_para_oai(resp_tc_sanitizada, "qwen3-local", False)
    msg_tc = out_tc["choices"][0]["message"]
    tc = (msg_tc.get("tool_calls") or [{}])[0]
    ok9 = (
        len(msg_tc.get("tool_calls") or []) == 1
        and tc.get("type") == "function"
        and tc.get("id", "").startswith("call_")
        and tc.get("function", {}).get("name") == "ler"
        and json.loads(tc.get("function", {}).get("arguments", "{}")) == {"arquivo": "x.txt"}
    )

    # defesa em profundidade: raciocinio inline do qwen3 termina no marcador
    # ' response' com quebras; o corte preserva so a resposta final
    inline_qwen = ("Okay, let me think: 17x20=340, 17x3=51, 340+51=391, "
                   "esta certo.\n response\n\n**Resposta:** 391")
    saida_inline = _corta_rascunho_inline_qwen(inline_qwen)
    ok10 = saida_inline == "**Resposta:** 391"
    ok10b = _corta_rascunho_inline_qwen("resposta normal sem marcador") == "resposta normal sem marcador"

    # tool_call nao-parseada (lixo no content) e removida
    com_toolcall = ('{"name": "execute", "arguments": {"code": "1+1"}}\n'
                    "</tool_call>\n\n**Resposta:** 2")
    ok11 = _remove_tool_call_nao_parseado(com_toolcall) == "\n\n**Resposta:** 2"

    # imagens em content parts (SDK OpenAI) viram content string + images base64
    req_visao = {"model": "vision", "messages": [
        {"role": "user", "content": [
            {"type": "text", "text": "o que ve?"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}},
        ]},
    ]}
    corpo_visao = traduz_oai_para_ollama(req_visao)
    m_visao = corpo_visao["messages"][0]
    ok12 = (
        m_visao["content"] == "o que ve?"
        and m_visao.get("images") == ["QUJD"]
    )
    # tool_calls de historico (2o turno do fluxo de agente) chegam em formato
    # OpenAI (arguments string); o /api/chat nativo so aceita OBJETO.
    # Sem essa conversao o request cai com 400/502 (caso real do ver).
    req_hist = {"model": "qwen3-local", "tools": [{}], "messages": [
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": "c1", "type": "function",
                          "function": {"name": "ler", "arguments": "{\"a\": 1}"}}]},
    ]}
    corpo_hist = traduz_oai_para_ollama(req_hist)
    tc_hist = (corpo_hist["messages"][0].get("tool_calls") or [{}])[0]
    ok5b = tc_hist.get("function", {}).get("arguments") == {"a": 1}

    print("self-test:")
    print("  corta rascunho + rede charset :", "PASS" if ok1 else "FAIL")
    print("  texto limpo segue intacto      :", "PASS" if ok2 else "FAIL")
    print("  cira/ideograma removidos       :", "PASS" if ok3 else "FAIL")
    print("  campo thinking removido        :", "PASS" if ok4 else "FAIL")
    print("  oai -> ollama (corpo nativo)   :", "PASS" if ok5 else "FAIL")
    print("  ollama -> oai (sem thinking)   :", "PASS" if ok6 else "FAIL")
    print("  SSE com [DONE] e sem rascunho  :", "PASS" if ok7 else "FAIL")
    print("  tools repassados na traducao   :", "PASS" if ok8 else "FAIL")
    print("  tool_calls na volta (OpenAI)   :", "PASS" if ok9 else "FAIL")
    print("  corta inline qwen (response)   :", "PASS" if (ok10 and ok10b) else "FAIL")
    print("  remove tool_call nao-parseada  :", "PASS" if ok11 else "FAIL")
    print("  content parts imagem -> nativo  :", "PASS" if ok12 else "FAIL")
    print("  tool_calls historico -> objeto  :", "PASS" if ok5b else "FAIL")
    return ok1 and ok2 and ok3 and ok4 and ok5 and ok6 and ok7 and ok8 and ok9 and ok10 and ok10b and ok11 and ok12 and ok5b

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
