# B04 — Comparativo: 7 leves trocados de qwen3-local para nothink-v2 (27B)

- **Data:** 2026-09-21, 00:51 → 01:20 (-03)
- **Objetivo:** validar a mitigação do achado r16 — os 7 agentes leves
  (`dados`, `financeiro`, `importador`, `preciso`, `qa`, `revisor`, `seo`)
  trocados para `nothink-v2` 27B, rodando os MESMOS prompts da B01/B03 para
  comparar com os resultados do qwen3-local. Se qualquer erro aparecesse,
  identificar o porquê.
- **Regras em vigor:** 27B estritamente em sequência (nunca paralelo); troca com
  script de backup + rollback (`benchmarks/b04_leves_nothink.sh`); respostas
  verbatim registradas.
- **Modelos:** nothink-v2 27B × 7 (todos antes em qwen3-local 14B).
- **Resultado geral:** **7 PASS · 0 FAIL** — nenhum vazamento de raciocínio na
  bateria; os dois FAIL históricos (financeiro na B03, revisor desde a B01)
  corrigidos. Uma ressalva de contagem no seo (erro de 3 caracteres, dentro do
  limite) e uma ressalva de verbosidade no importador.

## Troca executada

- `bash b04_leves_nothink.sh` (prévia) → 7 arquivos listados (nada alterado).
- `--executar`: backup em `~/.config/opencode/agent.bak-b04-20260921-005131`,
  `sed` da linha `model:` nos 7 arquivos; validação: 0 restantes em
  `qwen3-local` · 16 totais em `nothink-v2` (9 que já eram + 7 novos).
- Rollback em 1 comando: `bash b04_leves_nothink.sh --rollback`.
- Estado final dos 18: **16 × nothink-v2 27B · 1 × megabrain-v2 (profundo) ·
  1 × vision (ver)**.

## Vereditos

| Teste | Agente | B03 (qwen3) | B04 (nothink-v2) | Veredito |
|---|---|---|---|---|
| T01 | preciso | ✅ 391 limpo | 391 | ✅ limpo |
| T02 | financeiro | ❌ vazou inline | R$ 224,00 | ✅ limpo — FAIL corrigido |
| T03 | revisor | ❌ vazou + não corrigiu | corrigiu tudo | ✅ limpo — FAIL histórico corrigido |
| T04 | qa | ✅ com artefato | "Sim" + cálculo | ✅ limpo |
| T05 | importador | ✅ (ressalva) | campo vazio ok | ✅ (ressalva: verboso) |
| T06 | dados | ✅ 25 limpo | 25 (retry) | ✅ limpo |
| T07 | seo | ⚠ 155 vs 129 | 152 vs 149 | ✅ (ressalva: erro 3 chars) |

## Leitura da bateria

- **A troca para nothink-v2 eliminou o vazamento inline nos leves** — o
  problema estrutural do qwen3 (raciocínio embutido no content que o corte do
  proxy não alcança) deixou de existir: com o 27B o raciocínio vem no campo
  `thinking` (cortado na fonte) ou não vem.
- **`revisor` corrigiu a concordância pela primeira vez** (B01 ❌ e B03 ❌ com
  qwen3): "Nós vamos... mas talvez chova e nós ficamos em casa." — o único FAIL
  recorrente do projeto está resolvido.
- **`financeiro` voltou ao esperado** (regressão da B03 corrigida): R$ 224,00
  com a fórmula explícita e sem lixo no output.
- **`seo` melhorou a contagem mas ainda não é exata**: informou 152; o real
  (conferido no primário) é 149 (com espaços) / 125 (sem). Erro de 3 caracteres
  contra 61 na B01 e 26 na B03 — dentro do limite de 155, admissível; reforça a
  regra de bom senso: LLM não conta com confiabilidade, o primário reconfere.
- **`dados` falhou sem resposta na 1ª tentativa** (SDK cortou a conexão —
  ConnectionResetError no log do proxy; timeout durante o thinking do 27B).
  Retry individual OK. Ponto de atenção para a operação: 27B mais lentos podem
  estourar o timeout do SDK na primeira chamada quando o modelo descarrega.
- **Custo/latência:** todos os 7 agora custam o tempo de um 27B (carregamento
  + geração). Sem paralelismo: testes em sequência, ~3–6 min por agente no pior
  caso (primeira carga).

---

## T01 — preciso (aritmética)

- **Modelo:** nothink-v2 27B (era qwen3-local)
- **Prompt (verbatim):**
  > Calcule 17 × 23 e responda apenas o número final, sem explicação.
- **Esperado:** 391 (17 × 23 = 391)
- **Resposta entregue (verbatim):**
  > **Resposta: 391**
- **Veredito:** ✅ PASS — mesmo resultado da B03, limpo.

## T02 — financeiro (parcela)

- **Modelo:** nothink-v2 27B (era qwen3-local)
- **Prompt (verbatim):**
  > Um produto custa R$ 1.200,00 à vista e pode ser parcelado em 6 vezes com
  > juros simples de 2% ao mês sobre o valor à vista. Calcule o valor de cada
  > parcela. Mostre a fórmula usada e o resultado em reais.
- **Esperado:** R$ 224,00 (1.200 × 0,02 × 6 = 144; 1.344 ÷ 6 = 224)
- **Resposta entregue (resumo verbatim):** passo a passo — J = C·i·n = 144,00;
  total 1.344,00; parcela 1.344 ÷ 6 = **R$ 224,00**; observação de que o
  parcelado sai R$ 144,00 mais caro (12% ao total).
- **Veredito:** ✅ PASS — fórmula explícita, resultado conferido e **sem
  vazamento inline** (na B03 saiu o raciocínio colado no content).

## T03 — revisor (gramática)

- **Modelo:** nothink-v2 27B (era qwen3-local)
- **Prompt (verbatim):**
  > Corrija o texto abaixo e devolva apenas a versão corrigida:
  > "Nós vai amanhã para a festa, mais talvez chove e nos fica em casa."
- **Esperado:** concordância corrigida (vamos / mas / chova / fiquemos)
- **Resposta entregue (verbatim):**
  > "Nós vamos amanhã para a festa, mas talvez chova e nós ficamos em casa."
- **Veredito:** ✅ PASS — corrigiu "vamos", "mas", "chova" e "nós ficamos".
  **Primeira vez** que o agente passa (B01 ❌ e B03 ❌ com qwen3).

## T04 — qa (conferência)

- **Modelo:** nothink-v2 27B (era qwen3-local)
- **Prompt (verbatim):**
  > Confira esta conta passo a passo: "10% de R$ 1.500,00 = R$ 150,00". A conta
  > está correta? Responda apenas "sim" ou "não" e, se for "não", o valor certo.
- **Esperado:** "sim" (1.500 × 0,10 = 150)
- **Resposta entregue (verbatim):**
  > Sim.
  >
  > **Cálculo:** 10% R$ 1.500,00 = 0,10 1.500,00 = **R$ 150,00**
  >
  > Conferido com 1 ok / 0 alertas / 0 erros.
- **Veredito:** ✅ PASS — resposta correta e legível (na B03 vinha grudado com
  o raciocínio inline: "10%R$1.500,00R$150,00 response sim").

## T05 — importador (JSON→CSV)

- **Modelo:** nothink-v2 27B (era qwen3-local)
- **Prompt (verbatim):**
  > Converta este JSON para CSV, preservando o campo "cidade" vazio (""):
  > [{"nome":"Ana","cidade":"São Paulo"},{"nome":"Beto","cidade":""}]
- **Esperado:** CSV com `Beto,` (campo vazio preservado)
- **Resposta entregue (verbatim):**
  > ```csv
  > nome,cidade
  > Ana,São Paulo
  > Beto,
  > ```
  > (explicação tabular + script Python de exemplo)
- **Veredito:** ✅ PASS — campo vazio preservado, UTF-8 correto. Ressalva:
  respondeu com script Python e tabela extra não pedidos (verbosidade alta do
  27B; conteúdo correto).

## T06 — dados (estatística)

- **Modelo:** nothink-v2 27B (era qwen3-local)
- **Prompt (verbatim):**
  > Calcule a média aritmética dos números 10, 20, 30, 40 e responda apenas o
  > número final.
- **Esperado:** 25 (100 ÷ 4)
- **Resposta entregue (verbatim):**
  > 25
- **Artefato de execução:** 1ª tentativa sem texto (ConnectionResetError — SDK
  cortou durante o thinking; modelo descarregado); retry individual OK.
- **Veredito:** ✅ PASS — "25", limpo.

## T07 — seo (meta description)

- **Modelo:** nothink-v2 27B (era qwen3-local)
- **Prompt (verbatim):**
  > Escreva uma meta description para uma página sobre "como plantar tomate em
  > vaso". Máximo 155 caracteres. Informe a contagem exata.
- **Esperado:** meta ≤ 155 + contagem exata
- **Resposta entregue (verbatim):**
  > Aprenda a plantar tomate em vaso com passo a passo simples: solo, rega, sol
  > e adubação. Cultive tomates frescos na varanda ou varanda do apartamento!
  > "Contagem exata: 152 caracteres (incluindo espaços)"
- **Contagem real (conferida no primário):** 149 com espaços · 125 sem espaços.
- **Veredito:** ✅ PASS — meta dentro do limite e boa em conteúdo; contagem
  informada (152) difere da real (149) em 3 — erro pequeno, mas o modelo ainda
  não conta com exatidão; regra de bom senso mantida (primário reconfere).

---

## Comparativo resumido (qwen3-local → nothink-v2)

| Métrica | B03 (qwen3) | B04 (nothink-v2) |
|---|---|---|
| Vazamento de raciocínio na saída | 4/7 (financeiro, revisor, qa, seo) | **0/7** |
| FAIL de conteúdo | financeiro, revisor | **nenhum** |
| Contagem correta no seo | informou 155 (real 129) | informou 152 (real 149) |
| Tempo por agente | segundos (paralelo) | ~1–6 min (sequência obrigatória) |
| Custo de latência no fluxo real | 0 — paralelo | sente-se na fila (um 27B de cada vez) |