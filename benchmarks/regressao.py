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
    - Confere o shape do modelo `vision` no config/opencode.jsonc: modalities DEVE ser
      objeto {input:[...], output:[...]} com "image" na entrada — `attachment: true` sozinho
      não habilita imagem no opencode (capabilities derivam de modalities, T05).

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
import json
import os
import re
import sys
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS_DIR = os.path.join(ROOT, "agent")
SKILL = os.path.join(ROOT, "skills", "roteador", "SKILL.md")
README = os.path.join(ROOT, "README.md")
CONFIG = os.path.join(ROOT, "config", "opencode.jsonc")


def strip_jsonc(text):
    """Remove comentários // e /* */ conservando strings."""
    out = []
    i = 0
    in_str = False
    while i < len(text):
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < len(text):
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < len(text):
            n = text[i + 1]
            if n == "/":
                while i < len(text) and text[i] != "\n":
                    i += 1
                continue
            if n == "*":
                i += 2
                while i + 1 < len(text) and not (text[i] == "*" and text[i + 1] == "/"):
                    i += 1
                i += 2
                continue
        out.append(c)
        i += 1
    return "".join(out)

TOOL_KEYS = [
    "read", "edit", "glob", "grep", "list", "bash", "task",
    "external_directory", "todowrite", "question", "webfetch", "websearch",
    "lsp", "doom_loop", "skill",
]

TOOLED_AGENTS = {"codigo", "dados", "importador", "sysadmin"}
READ_TOOLED_AGENTS = {"ver"}  # visão: só list (diretório padrão) + read (abre via caminho — T05 fix)
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
            if sorted(allow) != ["list", "read"]:
                problems.append(f"{name}: visão deveria ter SÓ list+read allow (tem {allow})")
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

    # 4) Modelo `vision` no config: modalities tem que ser OBJETO {input:[...], output:[...]},
    #    não array de strings. O schema do opencode (Model.modalities, v1/config/provider.ts)
    #    só reconhece a forma de objeto; `input.image` = input.includes("image").
    #    `attachment: true` sozinho NÃO habilita imagem (capabilities derivam de modalities).
    try:
        cfg = json.loads(strip_jsonc(open(CONFIG, encoding="utf-8").read()))
        vision = (cfg.get("provider", {}).get("ollama", {}).get("models", {})).get("vision")
    except Exception as e:
        problems.append(f"config/opencode.jsonc: falha ao parsear: {e}")
        vision = None
    if vision is None:
        problems.append("config/opencode.jsonc: modelo `vision` ausente em provider.ollama.models")
    else:
        if not vision.get("attachment"):
            problems.append("config/opencode.jsonc: vision deveria ter attachment: true")
        mod = vision.get("modalities")
        if not isinstance(mod, dict):
            problems.append(f"config/opencode.jsonc: vision.modalities deve ser OBJETO {{input,output}}, achado {type(mod).__name__}")
        else:
            if not isinstance(mod.get("input"), list) or "image" not in mod.get("input", []):
                problems.append(f"config/opencode.jsonc: vision.modalities.input deve conter 'image' (tem {mod.get('input')})")
            if not isinstance(mod.get("output"), list) or "text" not in mod.get("output", []):
                problems.append(f"config/opencode.jsonc: vision.modalities.output deve conter 'text' (tem {mod.get('output')})")

    # 5) Diretório padrão do T05: quando o usuário não dá caminho, o `ver`
    #    procura em /home/rodmb188/Imagens/Análise IA/ via `list` e avisa se
    #    estiver vazia (1 imagem → abre; várias → pergunta qual; vazia → avisa).
    #    A regra precisa existir no agente E no roteador — sem ela o fluxo
    #    "sem caminho" volta a perguntar ao usuário/inventar arquivos.
    default_ver = open(os.path.join(AGENTS_DIR, "ver.md"), encoding="utf-8").read()
    skill_txt = open(SKILL, encoding="utf-8").read()
    if "Análise IA" not in default_ver:
        problems.append("ver.md: falta o diretório padrão 'Análise IA'")
    if "Análise IA" not in skill_txt:
        problems.append("SKILL.md: falta o diretório padrão 'Análise IA'")

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
    ("ver", "Anexe uma imagem e peça 'Descreva o que vê' com O CAMINHO VERBATIM no prompt, mesmo com espaço (ex.: Caminho da imagem: \"/home/rodmb188/Imagens/Capturas de tela/Teste.png\").", "descrição/OCR em pt-BR; NÃO deve responder 'não vejo imagem' nem re-parsear o path (espaços são válidos)"),
    ("ver-sem-caminho", "Peça 'Descreva a imagem' SEM caminho, com a pasta padrão /home/rodmb188/Imagens/Análise IA/ vazia. O ver deve usar list nela, achar nada e AVISAR.", "aviso 'não há imagem no diretório padrão' + pedido do caminho; NUNCA inventar nome de arquivo"),
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