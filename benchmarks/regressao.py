#!/usr/bin/env python3
"""
Regressão rápida do roteador.

Duas camadas, separadas honestamente:

1. ESTÁTICA (automática, rápida, determinística)
   - Valida os frontmatters YAML dos 18 agentes (parse, description, mode, model,
     15 chaves de permission).
   - Confere que a permission reflete o papel do agente (leves são "deny-all";
     codigo/dados/importador/sysadmin têm ferramentas; ver tem só read para abrir
     a imagem via caminho — T05 fix; task sempre deny).
   - Cruzamento: cada nível T02–T19 do roteador aponta para um agente existente.
   - Integridade de links internos do README (arquivos citados existem).
   - Verifica que o bloco "Tom e energia" está presente nos 18 (T9).

2. SMOKE VIVA (orientada, exige o TUI)
   - `opencode run --agent <x>` NÃO funciona headless neste stack: subagente não é
     agente primário (cai para default) e o CLI abre sessão interativa que trava
     até `2+2` (medido). Por isso a regressão viva é um checklist que você roda no
     TUI — cada linha imprime o prompt exato e a expectativa.

Uso:
  python3 regressao.py            # validação estática + exibe checklist
  python3 regressao.py --log      # idem + grava benchmarks/results/regressao_<data>.log
"""

import glob
import os
import re
import sys
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS_DIR = os.path.join(ROOT, "agent")
SKILL = os.path.join(ROOT, "skills", "roteador", "SKILL.md")
README = os.path.join(ROOT, "README.md")

TOOL_KEYS = [
    "read", "edit", "glob", "grep", "list", "bash", "task",
    "external_directory", "todowrite", "question", "webfetch", "websearch",
    "lsp", "doom_loop", "skill",
]

TOOLED_AGENTS = {"codigo", "dados", "importador", "sysadmin"}
READ_TOOLED_AGENTS = {"ver"}  # visão: só read, para abrir a imagem via caminho (T05 fix)
QUESTION_OK = {"entrevistador"}


def static_checks():
    """Realiza as verificações estáticas. Retorna (ok: bool, problemas: list[str])."""
    problems = []

    # 1) Frontmatter YAML dos agentes
    agents = sorted(glob.glob(os.path.join(AGENTS_DIR, "*.md")))
    if len(agents) != 18:
        problems.append(f"esperava 18 agentes, encontrados {len(agents)}")

    for path in agents:
        name = os.path.basename(path)[:-3]
        text = open(path, encoding="utf-8").read()
        fm = text.split("---")
        if len(fm) < 3:
            problems.append(f"{name}: frontmatter ausente/mal formado")
            continue
        try:
            meta = yaml.safe_load(fm[1])
        except Exception as e:
            problems.append(f"{name}: YAML inválido: {e}")
            continue
        if not isinstance(meta, dict):
            problems.append(f"{name}: frontmatter não é dict")
            continue
        for req in ("description", "mode", "model"):
            if req not in meta:
                problems.append(f"{name}: falta '{req}'")
        perm = meta.get("permission", {})
        if len(perm) != len(TOOL_KEYS):
            problems.append(f"{name}: permission tem {len(perm)} chaves (esperado {len(TOOL_KEYS)})")
        for k in TOOL_KEYS:
            if k not in perm or perm[k] not in ("allow", "deny"):
                problems.append(f"{name}: permission['{k}'] = {perm.get(k)}")

        # Papel da permission
        if name in TOOLED_AGENTS:
            if perm.get("task") != "deny":
                problems.append(f"{name}: tooled agent deve ter task deny")
            for k in ("read", "edit", "glob", "grep", "list", "bash", "external_directory"):
                if perm.get(k) != "allow":
                    problems.append(f"{name}: deveria ter {k} allow")
        elif name in READ_TOOLED_AGENTS:
            if perm.get("task") != "deny":
                problems.append(f"{name}: tooled agent deve ter task deny")
            allow = [k for k, v in perm.items() if v == "allow"]
            if allow != ["read"]:
                problems.append(f"{name}: visão deveria ter SÓ read allow (tem {allow})")
        else:
            allow = [k for k, v in perm.items() if v == "allow"]
            if name in QUESTION_OK:
                if allow not in ([], ["question"]) and allow != ["question"]:
                    problems.append(f"{name}: permitiu {allow} (esperado só question)")
            elif allow:
                problems.append(f"{name}: agente de texto não deveria ter tools ({allow})")

        # Bloco tom/energia (T9)
        if "## Tom e energia" not in text:
            problems.append(f"{name}: falta bloco 'Tom e energia'")
        if "primeira palavra" not in text:
            problems.append(f"{name}: bloco de tom sem regra da primeira palavra")

    # 2) Cruzamento roteador x agentes
    skill = open(SKILL, encoding="utf-8").read()
    for m in re.finditer(r"agente `([a-z]+)`", skill):
        name = m.group(1)
        if not os.path.exists(os.path.join(AGENTS_DIR, f"{name}.md")):
            problems.append(f"roteador cita agente inexistente: {name}")
    # 3) Links internos do README
    readme = open(README, encoding="utf-8").read()
    for m in re.finditer(r"\]\(([^)#]+)\)", readme):
        target = m.group(1).split("#")[0].strip()
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        full = os.path.normpath(os.path.join(os.path.dirname(README), target))
        if not os.path.exists(full):
            problems.append(f"README: link quebrado -> {target}")

    return (len(problems) == 0, problems)


SMOKE_CHECKLIST = [
    ("preciso", "Quanto é 17 × 23? Responda apenas o número.", "391"),
    ("financeiro", "Parcela de R$1.200 em 6x sem juros? Responda com o valor.", "R$ 200,00/unidade"),
    ("pesquisa", "(primário busca e embute) 2 modelos + veredicto numa faixa de preço.", "não usa tools; 1 veredicto"),
    ("revisor", "Corrija a gramática: 'Nos vamos amanha para a festa.'", "nós / amanhã"),
    ("codigo", "Corrija: def soma(a,b): return a-b", "return a+b"),
    ("profundo", "Prós e contras de modularizar um monólito (cenário curto embutido).", "análise em pt-BR, decisão + riscos"),
    ("qa", "Confira: 10% de R$ 1500 = R$ 150? Está certo?", "sim, correto"),
    ("importador", 'Converta JSON {"a":1,"b":""} para CSV preservando o vazio.', 'preserva "" vazio'),
    ("tutor", "Explique o que é uma variável para um iniciante.", "analogia clara em pt-BR"),
    ("tradutor", "Traduza para inglês: 'O gato preto dormiu.'", "The black cat slept"),
    ("ver", "Anexe uma imagem e peça: 'Descreva o que vê' — SEMPRE com o caminho no prompt (Caminho: /.../foto.png).", "descrição/OCR em pt-BR; NÃO deve responder 'não vejo imagem' com caminho dado"),
]


def main():
    log_path = None
    if "--log" in sys.argv:
        log_dir = os.path.join(ROOT, "benchmarks", "results")
        os.makedirs(log_dir, exist_ok=True)
        from datetime import datetime
        log_path = os.path.join(log_dir, f"regressao_{datetime.now():%Y%m%d_%H%M}.log")

    ok, problems = static_checks()
    out = []
    out.append("== REGRESSÃO ESTÁTICA ===")
    out.append("PASS - 18 agentes com frontmatter YAML íntegro" if ok else "FAIL")
    for p in problems:
        out.append(f"  PROBLEMA -> {p}")
    out.append("")
    out.append("== SMOKE VIVA (rode no TUI; headless trava neste stack) ===")
    for agent, prompt, expect in SMOKE_CHECKLIST:
        out.append(f"  [{agent}] prompt: {prompt}")
        out.append(f"            esperado: {expect}")
    report = "\n".join(out)

    if log_path:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(report + "\n")
        print(f"[log gravado] {log_path}")
    print(report)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()