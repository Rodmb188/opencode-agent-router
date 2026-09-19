#!/usr/bin/env python3
# nothink_parser.py — sanitizacao deterministica global (T16 r9 / nothink-v3)
#
# Objetivo: transformar a saida crua de QUALQUER subagente qwen3 em texto
# 100% latino (pt-BR) por REGRAS MECANICAS — nenhum julgamento de modelo.
#
# Camadas (aplicadas sempre, nesta ordem):
#   1. charset  — remove todo caractere cujo bloco Unicode nao e latino-pt/ascii.
#      Rede principal: deterministica, barata, imune a criatividade do modelo.
#   2. rascunho — corta o bloco de raciocinio quando o modelo o entrega marcado.
#      (configuravel via _MARCADORES_RASCUNHO; ver nota de arquitetura).
#
# Uso como modulo:
#   from nothink_parser import sanitize
#   limpo = sanitize(resposta_crua)
# Uso como CLI (stdin -> stdout):
#   cat saida_crua.txt | python3 nothink_parser.py > limpa.txt
#
# Auto-teste (sem literal estrangeiro no codigo-fonte — gerado em runtime):
#   python3 nothink_parser.py --self-test
#
# NOTA DE ARQUITETURA (corte na fonte):
#   Este modulo roda por padrao na camada de apresentacao. Para cortar NA
#   FONTE — de modo que nem o primario receba o rascunho — rode-o como proxy
#   local na porta 11435 escutando o fluxo do Ollama e aponte o provider do
#   opencode para `http://127.0.0.1:11435`. A camada 1 (charset) e a mesma
#   nas duas posicoes; a camada 2 so tem efeito no proxy (ve ENGINEERING_JOURNAL T16 r9).
import re, sys, unicodedata

# ---- camada 1: charset deterministico ------------------------------------
# Whitelist por bloco Unicode. Libera ASCII + latim estendido + espacos +
# pontuacao/digitos/simbolos latinos comuns. Tudo fora disso e cortado.
_NOME_BLOCO = "LATIN"
def _tem_acento_latino(ch):
    # Latin-1 / Latin Extended-A/B usados pelo pt-BR (á, ã, ç, ê, ô, ...)
    o = ord(ch)
    return (0x00C0 <= o <= 0x024F) or (o in (0x0152, 0x0153, 0x0178))

def _caractere_latino(ch):
    o = ord(ch)
    if o < 0x80:            # ASCII 7-bit
        return True
    if _tem_acento_latino(ch):
        name = unicodedata.name(ch, "?")
        if _NOME_BLOCO in name:
            return True
        return False
    return False

def remove_nao_latino(texto):
    """Remove mecanicamente todo caractere fora do alfabeto latino/ascii."""
    return "".join(c for c in texto if _caractere_latino(c))

# ---- camada 2: corte de bloco de rascunho --------------------------------
# Marcadores que o subagente pode usar para isolar o raciocinio da resposta.
# Ajuste conforme o formato observado no provider local (qwen3/ollama).
_MARCADORES_RASCUNHO = ("<thinking>", "RASCUNHO", "Raciocinio:", "rascunho:")

def corta_bloco_rascunho(texto, marcadores=None):
    """Se o texto comeca por um bloco de raciocinio marcado, corta so o bloco.

    Regra simples e deterministica: se o texto cru tem um dos marcadores e o
    texto resultante, apos removido o trecho, ainda tem conteudo latino restante,
    devolve o restante; caso contrario devolve o texto sanitizado de qualquer
    forma (a camada 1 ja garante o charset).
    """
    m2 = marcadores or _MARCADORES_RASCUNHO
    menor = None
    for m in m2:
        idx = texto.find(m)
        if idx >= 0:
            # pega o menor corte possivel entre um marcador e o fim do bloco
            fim = len(texto)
            for fechamento in ("</thinking>", "\n\n**Resposta", "\n\nResposta"):
                f = texto.find(fechamento, idx)
                if f >= 0:
                    fim = min(fim, f)
                    break
            candidato = texto[:idx] + texto[fim:]
            if len(remove_nao_latino(candidato)) > 1:
                if menor is None or len(candidato) < len(menor):
                    menor = candidato
    return menor if menor is not None else texto

def sanitize(texto):
    """Pipeline completo: corte de rascunho (se houver) + rede de charset."""
    t = corta_bloco_rascunho(texto)
    t = remove_nao_latino(t)
    # colapso de espacos multiplos deixados pelo corte + limpeza de borda
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

# ---- CLI / self-test -----------------------------------------------------
def _self_test():
    # Gera caracteres de outros alfabetos em RUNTIME (chr) — nada de literais
    # no fonte, para nao funcionar como isca. Alvos reais vistos em B01:
    # ideogramas e blocos de raciocinio em ingles.
    cjk = chr(0x9897)          # ideograma
    kana = chr(0x3044)         # hiragana "i"
    ciril = chr(0x0416)        # cirilico Zhe
    cenario_rascunho = (
        "RASCUNHO: calculei passo a passo e pensei em %s e %s por aqui; "
        "depois confiro. </thinking>\n\n"
        "**Resposta:** 2 + 2 = 4, aplicando a formula s = a + b." % (cjk, kana)
    )
    cenario_limpo = "Taxa de 5% sobre 200 = 10. Resultado: R$ 210."

    saida = sanitize(cenario_rascunho)
    ok1 = (cjk not in saida) and (kana not in saida) and ("2 + 2 = 4" in saida) and ("RASCUNHO" not in saida)
    ok2 = sanitize(cenario_limpo) == "Taxa de 5% sobre 200 = 10. Resultado: R$ 210."
    ok3 = (ciril not in sanitize("Valor %s misturado %s fim" % (cjk, ciril)))

    print("self-test:")
    print("  corta rascunho + rede charset :", "PASS" if ok1 else "FAIL")
    print("  texto limpo segue intacto      :", "PASS" if ok2 else "FAIL")
    print("  cira/ideograma removidos       :", "PASS" if ok3 else "FAIL")
    return ok1 and ok2 and ok3

if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(0 if _self_test() else 1)
    if not sys.stdin.isatty():
        sys.stdout.write(sanitize(sys.stdin.read()))
        sys.stdout.write("\n")
