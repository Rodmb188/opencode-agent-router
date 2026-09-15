import json, urllib.request, time

def chat(model, prompt, predict=900, timeout=300):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "stream": False, "keep_alive": "30m", "think": False,
            "options": {"num_ctx": 8192, "num_predict": predict}}
    req = urllib.request.Request("http://localhost:11434/api/chat",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        d = json.load(urllib.request.urlopen(req, timeout=timeout))
        return time.time()-t0, (d["message"].get("content") or "").strip()
    except Exception as e:
        return time.time()-t0, "ERRO %s" % str(e)[:80]

MODELS = ["qwen3-local:latest", "nothink-v2:latest"]

csv_input = ('nome;idade;cidade\n"João da Silva";32;São Paulo\nMaria;25;\n"Ana Luísa";28;Recife')
TESTS = [
  ("importador-csv",
   'Converta o CSV abaixo (delimitador ;, aspas e campo vazio) para JSON. Entregue APENAS o JSON resultante, sem explicações.\n\n' + csv_input,
   None),
  ("dados-estat",
   'A lista de valores é: [10, 20, 30, 40, 50]. Calcule a média, a mediana e o desvio padrão amostral (sample). Entregue APENAS no formato "media=X; mediana=Y; desvio=Z" (números U.S. decimals).',
   None),
  ("seo-meta",
   'Crie para o artigo "Melhor café em São Paulo" exatamente: (1) meta description com EXATAMENTE max 155 caracteres, (2) title max 60 caracteres, (3) H1 + 2 H2. Entregue APENAS: META=... / TITLE=... / H1=... / H2=... .',
   None),
]

for cap, prompt, _ in TESTS:
    print("\n===== %s =====" % cap)
    for m in MODELS:
        dt, text = chat(m, prompt)
        print("\n>>> %s (%.1fs)\n%s" % (m, dt, text[:600]))