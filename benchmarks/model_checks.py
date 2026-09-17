#!/usr/bin/env python3
"""
model_checks.py — C1b: sanity check dos modelos, 100% headless (sem TUI).

Chama o Ollama DIRETO pela porta de serviço (/api/generate), sem o opencode:
é o "fiscal 2" do C1 (liga o motor e confere a resposta). Roda só na máquina
local — os modelos não existem no runner do GitHub (32 GB de RAM + 47 GB de
modelos não cabem lá), por isso este script NÃO vai para o Actions.

O que confere:
  - presença dos 4 modelos via /api/tags (nothink-v2, megabrain-v2,
    qwen3-local, vision);
  - resposta de sanidade do qwen3-local (matemática: T02 é ferro, o 14B é o
    único que acerta aritmética multi-etapas — se regredir, o roteador inteiro
    de matemática está em risco);
  - resposta de sanidade do nothink-v2 (tradução simples, idioma pt-BR).

Uso:
  python3 benchmarks/model_checks.py          # roda e saí 0/1
  python3 benchmarks/model_checks.py --log    # grava em benchmarks/results/
"""
import json
import os
import sys
import time
import urllib.request

OLLAMA = "http://localhost:11434"
OLLAMA_TIMEOUT = 300  # dá folga ao load de 27B/14B em swap

CHECKS = [
    # (nome, modelo, prompt, trecho esperado na resposta)
    ("qwen3-local", "qwen3-local:latest", "Quanto é 17 × 23? Responda apenas o número.", "391"),
    ("nothink-v2", "nothink-v2:latest", "Traduza para o português: good morning.", "bom dia"),
]

REQUIRED_MODELS = ["qwen3-local:latest", "nothink-v2:latest", "megabrain-v2:latest", "vision:latest"]


def api_tags():
    with urllib.request.urlopen(OLLAMA + "/api/tags", timeout=20) as r:
        return [m.get("name") for m in json.loads(r.read().decode()).get("models", [])]


def api_generate(model, prompt):
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        # num_predict alto: os Qwen3 "pensam" antes de responder — com
        # num_predict baixo o corte cai DENTRO do raciocínio e a resposta final
        # nunca chega (medido: 64 → resposta vazia no qwen3-local).
        "options": {"num_predict": 1024},
    }).encode()
    req = urllib.request.Request(
        OLLAMA + "/api/generate", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as r:
        return json.loads(r.read().decode()).get("response", "")


def main():
    log_path = None
    if "--log" in sys.argv:
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "benchmarks", "results")
        os.makedirs(log_dir, exist_ok=True)
        from datetime import datetime
        log_path = os.path.join(log_dir, f"model_checks_{datetime.now():%Y%m%d_%H%M}.log")

    problems = []
    results = []

    try:
        models = api_tags()
    except Exception as e:
        print(f"[ERRO] Ollama indisponível em {OLLAMA}: {e}")
        print("  (o serviço precisa estar rodando — `systemctl status ollama` ou `ollama serve`)")
        sys.exit(1)

    for required in REQUIRED_MODELS:
        if required not in models:
            problems.append(f"modelo ausente no Ollama: {required}")

    for name, model, prompt, expected in CHECKS:
        t0 = time.time()
        try:
            out = api_generate(model, prompt)
        except Exception as e:
            problems.append(f"{name}: erro ao gerar: {e}")
            continue
        dt = time.time() - t0
        ok = expected.lower() in out.lower()
        results.append((name, ok, dt, out.strip()))
        if not ok:
            problems.append(f"{name}: resposta não contém '{expected}' → {out.strip()[:80]}")

    lines = ["== MODEL CHECKS (headless via /api/generate) =="]
    for name, ok, dt, snippet in results:
        lines.append(f"  [{'PASS' if ok else 'FAIL'}] {name} ({dt:.1f}s): {snippet[:70]}")
    for p in problems:
        lines.append(f"  PROBLEMA -> {p}")
    report = "\n".join(lines) + "\n"
    print(report, end="")

    if log_path:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"[log gravado] {log_path}")

    sys.exit(0 if not problems else 1)


if __name__ == "__main__":
    main()