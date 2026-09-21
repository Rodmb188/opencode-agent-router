# B03 — Smoke dos 18 agentes pela rota final do B02 (proxy corte-na-fonte, pós-fix r16)

- **Data:** 2026-09-20 08:12 → 2026-09-21 03:30 (-03)
- **Objetivo:** validar a rota final do B02 — os 18 agentes via `ollama-nothink`
  (proxy 11436 → Ollama 11434) com os MESMOS prompts da B01, comparando vereditos
  e conferindo que o raciocínio (`thinking` e inline) não chega à saída.
- **Regras em vigor:** sessões curtas do primário; 27B estritamente em sequência;
  respostas verbatim registradas; pergunta/resposta anotadas como na B01.
- **Modelos:** qwen3-local 14B (7 agentes, Onda 1) · nothink-v2 27B (9 agentes,
  Onda 2) · megabrain-v2 27B (profundo, Onda 3) · vision 8B (ver, Onda 4).
- **Resultado geral:** **14 PASS · 2 PARCIAL (seo, redator) · 2 FAIL (financeiro,
  revisor)**. Por modelo: **qwen3-local = 5 PASS (preciso, qa, importador, dados,
  pesquisa na B03 não) · 1 parcial (seo) · 2 FAIL (financeiro, revisor)**;
  **nothink-v2 27B = 8 PASS + 1 parcial (redator)**; megabrain-v2 e vision limpos.
  O `ver` desta vez **nomeou a pessoa** (melhora sobre a B01).

## Vereditos

| Teste | Agente | Esperado | Resultado | Veredito |
|---|---|---|---|---|
| T01 | preciso | 391 | 391 | ✅ limpo (corte inline funcionou) |
| T02 | financeiro | R$ 224,00 | vazou raciocínio inline | ❌ FAIL (novo) |
| T03 | revisor | frase corrigida | vazou inline + não corrigiu | ❌ FAIL (persiste) |
| T04 | qa | "sim" | "10%...150,00 response sim" (retry) | ✅ com artefato |
| T05 | importador | CSV campo vazio | correto (retry após 502) | ✅ (ressalva arquivo) |
| T06 | dados | 25 | 25 | ✅ limpo |
| T07 | pesquisa | B > A > C | correto, ranqueado | ✅ limpo (nothink-v2) |
| T08 | codigo | `a + b` | `return a + b` | ✅ limpo (nothink-v2) |
| T09 | redator | slogan ≤ 6 palavras | 7 palavras | ⚠ PARCIAL (contagem; nothink-v2) |
| T10 | sumarizador | 1 frase fiel | 1 frase fiel | ✅ limpo |
| T11 | tutor | analogia didática | analogia boa | ✅ (2 typos menores) |
| T12 | tradutor | The black cat slept. | correto | ✅ limpo |
| T13 | sysadmin | `df -h` | correto | ✅ limpo |
| T14 | seo | meta ≤ 155 + contagem exata | meta OK, informou 155 (real 129) | ⚠ PARCIAL (contagem) |
| T15 | entrevistador | 1 pergunta STAR | correta | ✅ limpo |
| T16 | planner | 3 etapas | corretas, sem tail "Resumo:" | ✅ (typo "1015 dias") |
| T17 | profundo | análise coerente | correta, sem vazamento | ✅ (typo "1620 GB" = 16–20) |
| T18 | ver | identificação sem cargo | **nomeou Lula** + descrição | ✅ limpo (melhora da B01) |

## Leitura da bateria

- **O corte na fonte funciona nos 27B e no vision — 100% das respostas limpas**
  (comparar B01: sumarizador/planner com tail "Resumo:", profundo com 1 palavra
  em inglês — todos sumiram). Nenhum dos 27B carregou rascunho no próprio texto.
- **O qwen3-local continua instável e é o único ponto fraco**: `financeiro` vazou
  inline (na B01 estava limpo — troca de agente vazado, mesmo padrão da B01),
  `revisor` vazou e não corrigiu a concordância (FAIL desde sempre), `qa`/`dados`
  com artefatos (mas resposta final correta). Confirma o achado r16: o qwen3 no
  contexto de agente nem sempre separa o raciocínio no campo `thinking`; quando
  emite inline sem o marcador ` response`, o corte do proxy não pega. **Mitigação
  executada na B04** (troca dos 7 leves para nothink-v2 — ver bateria seguinte).
- **Achado novo no proxy (fix r16b, testado nesta bateria)**: o fluxo REAL do
  `ver` quebrava em 502 no 2º turno (imagem voltando via tool result). Duas
  causas no `traduz_oai_para_ollama`: (1) o SDK manda imagens como `content` em
  LISTA de parts `image_url` e o `/api/chat` nativo só aceita content string +
  campo `images` (base64); (2) `tool_calls` de histórico chegam com `arguments`
  em string JSON (formato OpenAI) e o Ollama nativo só aceita OBJETO. Corrigido
  no proxy (`_converte_content_parts` + normalização de `arguments`), self-test
  14/14. Com o fix, o `ver` identificou "Luiz Inácio Lula da Silva" — superando a
  B01, em que ele só descrevia sem nomear.
- **Tail "Resumo:" eliminado**: na B01 aparecia em 6 agentes (codigo, importador,
  pesquisa, tutor, planner, ver); nesta rodada nenhum agente emitiu o tail.
- **Contagem de caracteres/palavras segue não confiável nos leves** (T09 redator:
  7 vs limite 6; T14 seo: informou 155, real 129) — o primário deve reconferir,
  regra de bom senso já cobre.

## Achados registrados

### r16 — qwen3 no contexto de agente não separa o thinking (confirmado)
- Gatilho do inline: system prompt grande do harness + ausência de tools no
  request. Com tools repassadas (fix pra ida), o qwen3 ainda emite raciocínio
  inline em parte das chamadas; o corte só pega quando há o marcador
  ` response`. Não é bug do proxy — é comportamento do modelo. (B01→B03:
  `financeiro` migrou de limpo para vazado; `preciso`/`dados`/`pesquisa` saíram
  limpos desta vez.)

### r16b — proxy não traduzia imagens nem tool_calls de histórico (fix)
- Sintoma: subagent `ver` falhava 502/HTTP 400 mesmo com a rota certa; o repro
  direto no Ollama com `image_url` parts devolvia erro de unmarshal.
- Causa 1: `content` em array (parts OpenAI) → Ollama nativo rejeita; é preciso
  extrair `images` (base64 sem o prefixo data:) e colar os textos num content
  único. Causa 2: `arguments` como string (OpenAI) → `/api/chat` só aceita
  objeto; converte com `json.loads` preservando o resto.
- Fix em `traduz_oai_para_ollama` + `_converte_content_parts`; self-test 12/12 →
  14/14 PASS. Nenhuma mudança de rota/agente necessária.

---

## T01 — preciso (aritmética)

- **Modelo:** qwen3-local · **Onda 1**
- **Prompt (verbatim):**
  > Calcule 17 × 23 e responda apenas o número final, sem explicação.
- **Esperado:** 391 (conferido: 17 × 23 = 391)
- **Resposta entregue (verbatim):**
  > **Resposta: 391**
- **Artefato:** corte inline pelo marcador ` response` funcionou (o rascunho
  precedia a resposta e foi cortado na fonte).
- **Veredito:** ✅ PASS — limpo nesta rodada (B01 tinha U+0308 + raciocínio em
  inglês no output).

## T02 — financeiro (parcela)

- **Modelo:** qwen3-local · **Onda 1**
- **Prompt (verbatim):**
  > Um produto custa R$ 1.200,00 à vista e pode ser parcelado em 6 vezes com
  > juros simples de 2% ao mês sobre o valor à vista. Calcule o valor de cada
  > parcela. Mostre a fórmula usada e o resultado em reais.
- **Esperado:** R$ 224,00 (1.200 × 0,02 × 6 = 144; 1.344 ÷ 6 = 224)
- **Resposta entregue:** vazou o raciocínio INLINE por completo no content
  (sem marcador ` response` para o corte pegar) — artefato do qwen3.
- **Veredito:** ❌ FAIL — regressão vs B01 (que saiu limpo); item para a decisão
  de mitigação dos leves.

## T03 — revisor (gramática)

- **Modelo:** qwen3-local · **Onda 1**
- **Prompt (verbatim):**
  > Corrija o texto abaixo e devolva apenas a versão corrigida:
  > "Nós vai amanhã para a festa, mais talvez chove e nos fica em casa."
- **Esperado:** frase com concordância corrigida (vamos / mas / chova / fiquemos)
- **Resposta entregue:** vazou raciocínio inline no content e devolveu a frase
  com "mais" e "chove" sem corrigir.
- **Veredito:** ❌ FAIL — persiste desde a B01 (único FAIL recorrente).

## T04 — qa (conferência)

- **Modelo:** qwen3-local · **Onda 1**
- **Prompt (verbatim):**
  > Confira esta conta passo a passo: "10% de R$ 1.500,00 = R$ 150,00". A conta
  > está correta? Responda apenas "sim" ou "não" e, se for "não", o valor certo.
- **Esperado:** "sim" (1.500 × 0,10 = 150)
- **Resposta entregue (verbatim):** (1ª tentativa 502; retry individidual)
  > 10%R$1.500,00R$150,00 response sim
- **Artefato:** trecho do raciocínio inline grudado antes do "sim"; o corte
  pegou só a partir do marcador ` response`.
- **Veredito:** ✅ PASS — resposta final correta ("sim"); entrega limpa exige
  reagente/sanitização (mesma ressalva da B01).

## T05 — importador (JSON→CSV)

- **Modelo:** qwen3-local · **Onda 1**
- **Prompt (verbatim):**
  > Converta este JSON para CSV, preservando o campo "cidade" vazio (""):
  > [{"nome":"Ana","cidade":"São Paulo"},{"nome":"Beto","cidade":""}]
- **Esperado:** CSV com `Beto,` (campo vazio preservado)
- **Resposta entregue (verbatim):** (1ª tentativa 502; retry ok)
  > ```
  > nome,cidade
  > Ana,"São Paulo"
  > Beto,
  > ```
  > (com texto sobre UTF-8 e compatibilidade Excel/Google Sheets)
- **Veredito:** ✅ PASS — campo vazio preservado. Ressalva: menção a um arquivo
  (`output.csv`) que não foi de fato criado (igual B01).

## T06 — dados (estatística)

- **Modelo:** qwen3-local · **Onda 1**
- **Prompt (verbatim):**
  > Calcule a média aritmética dos números 10, 20, 30, 40 e responda apenas o
  > número final.
- **Esperado:** 25 (100 ÷ 4)
- **Resposta entregue (verbatim):**
  > 25
- **Veredito:** ✅ PASS — limpo nesta rodada (B01 tinha U+80A1 + raciocínio).

## T07 — pesquisa (síntese ranqueada)

- **Modelo:** nothink-v2 27B · **Onda 2 (sequencial)**
- **Prompt (verbatim):**
  > Material de busca embutido: (1) "Produto A custa R$ 1.800,00 e tem 64 GB";
  > (2) "Produto B custa R$ 2.300,00 e tem 128 GB"; (3) "Produto C custa
  > R$ 1.500,00 e tem 32 GB". Qual tem melhor custo-benefício? Ordene e justifique.
- **Esperado:** B > A > C (preço/GB)
- **Resposta entregue:** ranking B > A > C, em pt-BR, sem artefato e sem tail
  "Resumo:".
- **Veredito:** ✅ PASS — limpo (B01 tinha CJK no meio + tail "Resumo:").

## T08 — codigo (função)

- **Modelo:** nothink-v2 27B · **Onda 2 (sequencial)**
- **Prompt (verbatim):**
  > Escreva uma função JavaScript que soma dois números e retorna o resultado.
  > Responda apenas o código.
- **Esperado:** `function soma(a, b) { return a + b; }`
- **Resposta entregue (verbatim):**
  > ```javascript
  > return a + b;
  > ```
- **Veredito:** ✅ PASS — limpo, sem tail "Resumo:" (B01 tinha o tail).

## T09 — redator (slogan)

- **Modelo:** nothink-v2 27B · **Onda 2 (sequencial)**
- **Prompt (verbatim):**
  > Crie um slogan para uma padaria de bairro. Máximo 6 palavras, em pt-BR.
- **Esperado:** slogan ≤ 6 palavras
- **Resposta entregue:** slogan com 7 palavras, sem artefato de raciocínio.
- **Veredito:** ⚠ PARCIAL — conteúdo ok, mas estourou o limite em 1 palavra
  (contagem imprecisa do leve; primário deve reconferir).

## T10 — sumarizador (resumo)

- **Modelo:** nothink-v2 27B · **Onda 2 (sequencial)**
- **Prompt (verbatim):**
  > Resuma em UMA frase: "O gato preto dormiu no sofá a tarde toda e acordou
  > apenas quando a dona abriu a lata de comida. Ele comeu devagar e voltou a
  > dormir, desta vez na janela, onde o sol batia."
- **Esperado:** 1 frase fiel ao texto
- **Resposta entregue (verbatim):**
  > O gato preto passou a tarde dormindo no sofá, acordou apenas para comer
  > devagar e voltou a dormir no sol da janela.
- **Veredito:** ✅ PASS — limpo, sem tail "Resumo:" (B01 tinha).

## T11 — tutor (analogia)

- **Modelo:** nothink-v2 27B · **Onda 2**
- **Prompt (verbatim):**
  > Explique o que é uma variável em programação para um iniciante total, usando
  > uma analogia do dia a dia. Máximo 4 frases.
- **Esperado:** analogia concreta, didática
- **Resposta entregue (resumo verbatim):** variável = "caixa de sapato" com
  rótulo: guarda-se um valor e o programa o encontra pelo nome; exemplo
  `pontuacao` = 100; pergunta interativa ao final.
- **Veredito:** ✅ PASS — analogia clara (melhora do "caixa rotulada" da B01).
  Ressalva: 2 typos menores ("rótino" por "rótulo", "Perguinha" por
  "Perguntinha"); sem tail "Resumo:".

## T12 — tradutor (pt→en)

- **Modelo:** nothink-v2 27B · **Onda 2**
- **Prompt (verbatim):**
  > Traduza para o inglês: "O gato preto dormiu." Responda apenas a tradução.
- **Esperado:** "The black cat slept."
- **Resposta entregue (verbatim):**
  > The black cat slept.
- **Veredito:** ✅ PASS — limpo.

## T13 — sysadmin (comando)

- **Modelo:** nothink-v2 27B · **Onda 2**
- **Prompt (verbatim):**
  > Qual comando Linux mostra o uso de disco em formato legível por humanos?
  > Responda apenas o comando.
- **Esperado:** `df -h`
- **Resposta entregue (verbatim):**
  > ```bash
  > df -h
  > ```
- **Veredito:** ✅ PASS — limpo (code fence aceitável).

## T14 — seo (meta description)

- **Modelo:** qwen3-local · **Onda 1**
- **Prompt (verbatim):**
  > Escreva uma meta description para uma página sobre "como plantar tomate em
  > vaso". Máximo 155 caracteres. Informe a contagem exata.
- **Esperado:** meta ≤ 155 + contagem exata
- **Resposta entregue:** meta ok em conteúdo; contagem informada 155 mas a real
  (conferida) é 129.
- **Veredito:** ⚠ PARCIAL — igual à B01 no padrão do erro (contagem imprecisa);
  LLM não conta caracteres com confiabilidade — primário reconfere.

## T15 — entrevistador (STAR)

- **Modelo:** nothink-v2 27B · **Onda 2**
- **Prompt (verbatim):**
  > Faça APENAS a primeira pergunta de uma entrevista comportamental (método
  > STAR) para uma vaga de suporte técnico. Uma pergunta só, em pt-BR.
- **Esperado:** 1 pergunta STAR, em pt-BR correto
- **Resposta entregue (resumo verbatim):** abertura cordial + 1 pergunta
  comportamental cobrindo Situação, Tarefa, Ação e Resultado (cliente frustrado
  com problema técnico).
- **Veredito:** ✅ PASS — uma pergunta só, STAR correto, em pt-BR.

## T16 — planner (etapas)

- **Modelo:** nothink-v2 27B · **Onda 2**
- **Prompt (verbatim):**
  > Liste 3 etapas para lançar a versão 1.0 de um aplicativo de lista de
  > compras, em ordem cronológica. Formato: 1. / 2. / 3.
- **Esperado:** 3 etapas coerentes em ordem
- **Resposta entregue (resumo verbatim):** 1) especificação do MVP + protótipo;
   2) desenvolvimento e teste; 3) preparação de lançamento e release — cada uma
   com esforço, risco e dependência; caminho crítico.
- **Veredito:** ✅ PASS — coerente, em ordem, **sem tail "Resumo:"** (B01 tinha).
  Ressalva: "1015 dias" provável typo de "10–15 dias".

## T17 — profundo (análise de risco)

- **Modelo:** megabrain-v2 27B · **Onda 3 (sequencial)**
- **Prompt (verbatim):**
  > Analise o risco de rodar dois modelos 27B em paralelo na mesma máquina com
  > 32 GB de RAM. Considere size médio por modelo, swap thrash e OOM-kill.
  > Responda em pt-BR, máximo 6 frases.
- **Esperado:** risco alto, swap thrash, OOM-kill, ~14–16 GB por modelo
- **Resposta entregue (resumo verbatim):** risco alto; ~16–20 GB por modelo em
  Q4 (peso + KV cache), dois modelos esgotam 32 GB; swap thrash degrada a
  latência; OOM-killer mata um processo; cita o agendamento do AGENTS global e
  conclui "não faça — serialize os 27B".
- **Veredito:** ✅ PASS — análise correta e **sem vazamento de rascunho** (o
  thinking do megabrain foi cortado na fonte; B01 tinha 1 palavra em inglês).
  Ressalva: typo "1620 GB" (= 16–20 GB).

## T18 — ver (identificação de imagem)

- **Modelo:** vision 8B VL · **Onda 4 (sequencial)**
- **Prompt (verbatim):**
  > Identifique a pessoa nesta imagem e descreva o que ela mostra. Caminho da
  > imagem: /home/rodmb188/Imagens/Análise IA/Homem.png
- **Esperado:** identificar a pessoa, sem afirmar cargo público com certeza
- **Resposta entregue (resumo verbatim):** "Luiz Inácio Lula da Silva,
  ex-presidente do Brasil", com descrição da vestimenta (chapéu de palha com
  faixa preta, terno escuro, gravata nas cores da bandeira), postura (mão
  levantada junto à boca) e cenário (fundo verde de estúdio); observação de que
  não há textos legíveis; oferta de mais detalhes.
- **Veredito:** ✅ PASS — **nomeou a pessoa** e descreveu bem (na B01 só
  descrevia sem nomear). Funcionou graças ao fix r16b do proxy (imagens via
  tool result). Ressalva menor: afirmou o cargo com "ex-presidente" — a guarda
  de factualidade continua recomendada.

---

## Registro de execução

- Onda 1 (qwen3-local, paralela): preciso, financeiro, revisor, qa, importador,
  dados, seo — 2× 502 no primeiro tiro (qa, importador), retries individuais OK.
- Onda 2 (nothink-v2 27B, sequencial): pesquisa, codigo, redator, sumarizador,
  tutor, tradutor, sysadmin, entrevistador, planner.
- Onda 3 (megabrain-v2 27B, sequencial): profundo.
- Onda 4 (vision 8B, sequencial): ver — 2× 502 antes do fix r16b (diagnóstico e
  correção na própria bateria).
- Proxy reiniciado 2× durante a bateria (fix r16b + limpeza de cache); self-test
  14/14 antes de cada nova subida.