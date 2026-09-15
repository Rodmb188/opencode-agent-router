import json, urllib.request, random, time, sys

MODELS = ["qwen3-local:latest", "nothink-v2:latest"]
REPEAT = 3

PROMPTS = [
    ("slogan-cafe", "Crie um slogan premium para uma cafeteria artesanal (máximo 8 palavras). Responda apenas o slogan."),
    ("titulo-materia", "Crie um título chamativo (máximo 8 palavras) para uma matéria sobre a aposentadoria de um robô após 30 anos numa montadora. Responda apenas o título."),
    ("email-empresa", "Escreva um e-mail formal e curto (3-5 linhas) para um cliente avisando que o pedido atrasou e será entregue amanhã. Responda apenas o corpo do e-mail."),
    ("microconto", "Escreva um microconto de 2 a 3 frases sobre um elevador que só funciona quando chove."),
    ("anuncio-tenis", "Crie uma copy publicitária de até 2 linhas para um tênis de corrida que promete amortecimento excepcional."),
    ("legenda-gato", "Escreva uma legenda engraçada (máximo 15 palavras) para a foto de um gato que pulou da prateleira e derrubou um vaso."),
]

def chat(model, prompt, predict=280, timeout=300):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "stream": False, "keep_alive": "30m", "think": False,
            "options": {"num_ctx": 4096, "num_predict": predict}}
    req = urllib.request.Request("http://localhost:11434/api/chat",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    d = json.load(urllib.request.urlopen(req, timeout=timeout))
    return time.time() - t0, (d["message"].get("content") or "").strip()

def main():
    out = []
    mapping = {}
    blind_id = 0
    for key, prompt in PROMPTS:
        for rep in range(REPEAT):
            for model in MODELS:
                dt, text = chat(model, prompt)
                blind_id += 1
                mapping[str(blind_id)] = model
                out.append({"prompt": key, "id": blind_id, "text": text, "time": dt})
    random.shuffle(out)
    with open("/tmp/opencode/writing_outputs.txt", "w") as f:
        for o in out:
            f.write("### ID %03d | %s | repetição %d (%.1fs)\n%s\n\n" %
                    (o["id"], o["prompt"], sum(1 for x in out if x["prompt"] == o["prompt"]) + 0, o["time"], o["text"]))
    with open("/tmp/opencode/writing_map.json", "w") as f:
        json.dump(mapping, f, indent=2)
    print("Gerados %d outputs. Blinded em writing_outputs.txt, mapa em writing_map.json" % len(out))

if __name__ == "__main__":
    main()