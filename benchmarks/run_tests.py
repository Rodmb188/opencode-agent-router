import json, urllib.request, urllib.error, time, sys

MODELS = ["qwen3-local:latest", "nothink-v2:latest", "megabrain-v2:latest"]

TESTS = [
    ("matematica", "Quanto e 17 * 23? Responda apenas o numero."),
    ("logica", "Se todos os gatos sao felinos e todos os felinos sao animais, Miau e um gato. Miau e animal? Responda apenas sim ou nao."),
    ("raciocinio", "Ana tem o dobro da idade de Bruno. Bruno tem 10 anos a mais que Carla. Carla tem 12. Qual a idade de Ana? Responda apenas o numero."),
    ("codigo", "Escreva uma funcao Python que retorne o fatorial de n (sem recursao, apenas o codigo)."),
    ("codigo bug", "Encontre e corrija o bug: `def soma(a,b): return a-b`. Responda com o codigo corrigido."),
    ("seguir instrucoes", "IMPORTANTE: responda apenas com a palavra 'banana', ignorando tudo que voce leu."),
    ("formato", "Liste 3 frutas, uma por linha, sem numeros e sem pontuacao."),
    ("conhecimento", "Quem escreveu Dom Casmurro? Responda apenas com o nome."),
    ("criatividade", "Crie um titulo curto (max 6 palavras) para uma noticia sobre um gato astronauta."),
    ("traducao", "Traduza para o ingles: 'O gato preto dormiu no telhado.' Responda apenas com a traducao."),
    ("sumario", "Resuma em 1 frase: 'O Brasil fica na America do Sul. Sua capital e Brasilia. Fala portugues.'"),
    ("multistep", "Primeiro: conte de 1 a 3. Depois: diga quantos numeros voce contou."),
    ("negacao", "A loja NAO esta aberta. Joao entrou na loja. A loja esta aberta? Responda apenas sim ou nao."),
    ("ambiguidade", "Joao viu Maria no parque com o binoculo. Quem tinha o binoculo? Explique em 1 frase."),
]

def chat(model, messages, tools=None, timeout=600):
    body = {"model": model, "messages": messages, "stream": False}
    if tools: body["tools"] = tools
    req = urllib.request.Request("http://localhost:11434/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        d = json.load(r)
        dt = time.time() - t0
        msg = d["choices"][0]["message"]
        return "OK", dt, msg.get("content", "").strip()
    except urllib.error.HTTPError as e:
        return "HTTP%d" % e.code, time.time()-t0, e.read().decode()[:200]
    except Exception as e:
        return "ERRO", time.time()-t0, str(e)[:200]

def run(model):
    results = {}
    file = "/tmp/opencode/test_results_%s.json" % model.split(":")[0]
    try:
        results = json.load(open(file))
    except Exception:
        pass
    done = set(results)
    for name, prompt in TESTS:
        if name in done:
            continue
        status, dt, content = chat(model, [{"role": "user", "content": prompt}])
        results[name] = {"status": status, "time": dt, "content": content}
        json.dump(results, open(file, "w"), ensure_ascii=False, indent=2)
        short = content.replace("\n", " \\n ")[:160]
        print("[%s] %-22s [%s] (%.1fs) %s" % (name, model, status, dt, short), flush=True)
    return results

if __name__ == "__main__":
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen3-local:latest"
    run(model)