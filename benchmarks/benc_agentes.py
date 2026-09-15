import json, urllib.request, random, time, sys, os

MODELS = ["qwen3-local:latest", "nothink-v2:latest"]
REPEAT = 2
BASE = "/tmp/opencode/agentes_bateria"
os.makedirs(BASE, exist_ok=True)

TEXTO_SP = ("O metrô de São Paulo enfrenta superlotação crescente no horário pico. As linhas 1 e 3 "
           "transportam, juntas, cerca de 1,2 milhão de passageiros por dia e os intervalos entre trens "
           "chegam a 2 minutos. Estudos apontam que a expansão das linhas 6 e 15, prevista até 2026, "
           "deve reduzir o tempo médio de deslocamento em até 15 minutos. A tarifa, atualmente R$ 5,00, "
           "não sofre reajuste desde 2021.")
TEXTO_REDE = ("Redes neurais convolucionais são usadas principalmente em visão computacional. Elas aplicam "
             "filtros sobre a imagem para detectar bordas, texturas e formas em diferentes camadas. "
             "A camada de pooling reduz a resolução, mantendo as informações mais relevantes. Modelos como "
             "o ResNet-50 atingem 95% de acurácia em benchmarks como o ImageNet, mas exigem muitas horas "
             "de treinamento em GPUs com grandes conjuntos de dados.")

CAPS = {
 "tutor": [
    "Explique o que é inflação para uma pessoa de 14 anos. Use analogias simples e passo a passo.",
    "Explique recursão em programação com um exemplo simples (passo a passo).",
    "Explique o conceito de custo de oportunidade em economia, de forma didática.",
 ],
 "sumarizador": [
    "Resuma o texto abaixo em 3 bullets mantendo todos os números e nomes:\n" + TEXTO_SP,
    "Resuma o texto abaixo em 3 bullets mantendo todos os números e nomes:\n" + TEXTO_REDE,
 ],
 "tradutor": [
    "Traduza para o inglês (registro técnico):\n'O servidor apresentou latência elevada durante o pico de tráfego; a equipe implementou cache distribuído para mitigar o problema.'",
    "Traduza para o português do Brasil (registro técnico):\n'The new firmware patches three critical vulnerabilities in the network stack, including a buffer overflow that allowed remote code execution.'",
    "Traduza para o inglês (registro formal, comercial):\n'Prezado Senhor, anexo a proposta revisada. Aguardo retorno até sexta-feira para prosseguirmos com o fechamento.'",
 ],
 "revisor": [
    "Revise o texto abaixo (gramática e ortografia), sem mudar o sentido.\n'Nós fomos na reunião ontém e vi que os relatorios estão com erros. Deveriamos corrigir antes da entrega, ou o cliente vai reclamar denovo.'",
    "Revise o texto abaixo (gramática e ortografia), sem mudar o sentido.\n'O contrato sera renovado automaticamente caso o cliente não manifeste sua saída. Nos termos do documento, a multa aplica-se sobre o valor da mensalidade e poderar ser parcelada em ate 3 vezes.'",
 ],
}

def chat(model, prompt, predict=600, timeout=300):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "stream": False, "keep_alive": "30m", "think": False,
            "options": {"num_ctx": 8192, "num_predict": predict}}
    req = urllib.request.Request("http://localhost:11434/api/chat",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    d = json.load(urllib.request.urlopen(req, timeout=timeout))
    return time.time() - t0, (d["message"].get("content") or "").strip()

def main():
    done = set()
    results = []
    mapf = os.path.join(BASE, "map.json")
    if os.path.exists(mapf):
        mapping = json.load(open(mapf))
        done = set(mapping.values())
    else:
        mapping = {}
    blind_id = 0
    for cap, prompts in CAPS.items():
        for pi, prompt in enumerate(prompts):
            for rep in range(REPEAT):
                for model in MODELS:
                    key = "%s|%d|%d|%s" % (cap, pi, rep, model)
                    if key in done:
                        continue
                    dt, text = chat(model, prompt)
                    blind_id += 1
                    mapping[key] = blind_id
                    results.append({"cap": cap, "idx": pi, "rep": rep,
                                    "model": model, "blind": blind_id,
                                    "text": text, "time": dt, "prompt": prompt})
    json.dump(mapping, open(mapf, "w"), indent=2)
    with open(os.path.join(BASE, "outputs.txt"), "w") as f:
        for o in results:
            f.write("### ID %03d | %s #%d (rep %d) | %.1fs\nPROMPT: %s\n%s\n\n"
                    % (o["blind"], o["cap"], o["idx"], o["rep"], o["time"], o["prompt"][:120], o["text"]))
    print("Fase 1: %d outputs." % len(results))

if __name__ == "__main__":
    main()