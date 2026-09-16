---
name: roteador
description: Roteamento automático por níveis de tarefa. Use SEMPRE que receber uma mensagem nova do usuário (a menos que seja continuação óbvia de trabalho em andamento ou resposta a pergunta do próprio assistente). Classifica o pedido nas pré-definições abaixo e delega ao agente com o modelo/velocidade certos, respeitando o orçamento de latência de cada nível.
---

# Roteador de modelos — sistema completo (pré-definições editáveis)

Classifique a pergunta e aplique a resposta ao nível correto. As pré-definições podem ser
ajustadas aqui e valem para todo o opencode.

## Escada de níveis (orçamento de latência)

| Nível | Categoria | Sinais na pergunta | Modelo/Agente | Latência |
|---|---|---|---|---|
| **T00** | Trivial / continuidade | "ok", "continua", agradecimento, conversa leve, resposta à pergunta do próprio assistente | modelo principal (`nothink-v2`) | instantâneo — **nunca delegar** |
| **T01** | Geral / rápido | perguntas de cultura, tradução curta, resumo curto, opinião, código simples no chat, formatação | modelo principal | ~2–10s — **nunca delegar** |
| **T02** | Cálculo e lógica multi-etapas | idade, dobro, porcentagem "%", desconto, equação, raiz, média, "quantos", troco, conversões | agente `preciso` (qwen3-local) | ~5–10s |
| **T03** | Contas financeiras | parcelas, juros, taxa, financiamento, orçamento, custo, rendimento, CET | agente `financeiro` (qwen3-local) | ~5–15s |
| **T04** | Pesquisa web | "pesquisar", "buscar", "qual o melhor", "quanto custa", produto (celular, notebook...), preços, benchmarks, notícias, atualidades, tutoriais, "R$", orçamento, comparações | você busca (websearch) + agente `pesquisa` (nothink-v2) só sintetiza | ~30–90s |
| **T05** | Visão / imagem | imagem/foto/print/screenshot anexada, "descreva a imagem", "o que tem nessa foto", OCR | agente `ver` (vision) — caminho absoluto verbatim no prompt, OU o diretório padrão (`/home/rodmb188/Imagens/Análise IA/`) quando o usuário não der caminho | ~30–40s |
| **T06** | Escrita criativa | título, slogan, e-mail, texto publicitário, história, postagem | agente `redator` (nothink-v2) | ~5–15s |
| **T07** | Revisão / QA de texto | "revise", "corrija o texto", "está bem escrito?", reescrever com mais coesão | agente `revisor` (qwen3-local) | ~5–15s |
| **T08** | Código isolado | função, script, corrigir bug, refatorar, revisar código, regex, converter formatos (fora do fluxo de edição do projeto) | agente `codigo` (nothink-v2) | ~5–15s |
| **T09** | Tutoria / didática | "explique", "me ensine", "não entendi", conceito passo a passo | agente `tutor` (nothink-v2) | ~5–15s |
| **T10** | Resumo de texto longo | "resuma", "TL;DR", "principais pontos" de documento/artigo longo colado | agente `sumarizador` (nothink-v2) | ~15–45s |
| **T11** | Tradução (técnica/extensa) | "traduza", "versão em inglês" de texto não trivial | agente `tradutor` (nothink-v2) | ~15–30s |
| **T12** | Análise profunda | "analise a fundo", "avalie os prós e contras", decisão crítica, prova, planejamento estratégico, otimização, arquitetura de código, tese | agente `profundo` (megabrain) | ~1–4 min |
| **T13** | Análise de dados | planilha, CSV, "analise esse arquivo", média/mediana, limpeza de dados, gráficos | agente `dados` (qwen3-local) | ~5–15s |
| **T14** | Sysadmin / automação Linux | comando Linux, shell, docker, systemd, monitoramento, manutenção | agente `sysadmin` (nothink-v2) | ~5–15s |
| **T15** | Simulação de entrevista | "simule uma entrevista", "me treine para entrevista" | agente `entrevistador` (nothink-v2) | interativo |
| **T16** | Planejamento de projetos | "planeje", "quebre em etapas", "monte um cronograma", "por onde começo" | agente `planner` (nothink-v2) | ~10–30s |
| **T17** | SEO pt-BR | "otimize para SEO", "meta description", "palavras-chave" | agente `seo` (qwen3-local) | ~5–15s |
| **T18** | QA / conferência final | "confere isso", "verifique se está certo", "confira os números" | agente `qa` (qwen3-local) | ~5–15s |
| **T19** | Conversão de formatos | CSV→JSON, XLS para CSV, encoding, timestamps, regex de transformação | agente `importador` (qwen3-local) | ~5–15s |

## Regras obrigatórias (baseadas em testes reais)

1. **T00/T01: nunca delegar.** Delegar coisas banais é desperdício grosseiro de latência. Entregue direto.
2. **Matemática no modo principal é PROIBIDA para multi-etapas**: o `nothink-v2` (think off) erra
   consistentemente aritmética encadeada (respostas tipo "34" em vez de "44"), mesmo quando mandado verificar.
   Qualquer conta com mais de 1 operação → nível T02 (`preciso`) ou T03 (`financeiro`).
3. **`megabrain`/`profundo` apenas em T12** — nunca para cálculo rápido. Para cálculo, `qwen3-local`
   resolve passo a passo e conferindo (mais rápido E mais correto que o modo rápido do 27B).
4. **Pesquisa web (T04): você busca, o subagente SÓ sintetiza.** `websearch` só existe no provider
   `opencode`/`opencode-go` (ou com `OPENCODE_ENABLE_EXA`/`OPENCODE_ENABLE_PARALLEL`) — subagentes em `ollama` NÃO recebem
   a tool, mesmo com permission `allow` (prova: registry.ts `webSearchEnabled`, teste real seção 13). Então:
   - **Você** roda 2–3 buscas `websearch` (na camada T00/T01, no chat) e extrai os trechos essenciais.
   - **Embeba os trechos na mensagem** do agente `pesquisa` (nunca aponte arquivo) e peça: ranquear por relevância,
     justificar, dar veredicto. O `pesquisa` NÃO usa ferramenta — material já vem pronto.
   - `webfetch` em sites .com.br bloqueia bots (Transport error) — use só em domínio confirmado.
5. **Versões curtas dos níveis T07–T11** (ex.: "traduza essa frase", "resuma 1 parágrafo") ficam na camada T00/T01; só delega quando a tarefa for substancial ("revise este e-mail de 2 páginas", "resuma o artigo de 10 páginas").
6. **T05 (imagem): o anexo NÃO chega sozinho ao `ver`; repasse o caminho absoluto, VERBATIM.** O primário não repassa a
    imagem anexada ao subagente automaticamente — em teste real o `ver` recebeu 3 chamadas após o envio de uma
    foto e em todas respondeu "não vejo imagem" (correto: nada chegou). O `ver` só enxerga a imagem se (a) o anexo
    vier dentro do task (raro) ou (b) você incluir o **caminho absoluto do arquivo no prompt** e contar com o `read`
    do `ver` (permitido por config) para abrir. **PASSO A PASSO OBRIGATÓRIO**: (1) se o usuário der um caminho,
    use-o verbatim; se NÃO der, NÃO pergunte de cara — inclua no prompt do `ver` o **diretório padrão**
    (`/home/rodmb188/Imagens/Análise IA/`); o `ver` procura lá com a tool `list` e avisa se não achar
    (1 imagem → abre; várias → pergunta qual; vazia → avisa e pede o caminho); (2) chame o
    `ver` com o pedido COMPLETO + `Caminho da imagem: <absoluto>` (quando houver) ou
    `Caminho padrão: /home/rodmb188/Imagens/Análise IA/` (quando não houver) no prompt; (3) NUNCA delegue a
    `explore` para "descobrir onde fica a screenshot" — em teste real o explore saiu varrendo `/public`, `/assets`,
    `/static`, `/docs` e voltou com "nenhum diretório de screenshots" enquanto a pasta certa (`Capturas de tela`)
    estava dada na conversa. Se o caminho foi fornecido pelo usuário, use-o; se não, o diretório padrão resolve —
    só pergunte ao usuário se o `ver` reportar pasta vazia.
    **Caminhos com espaço**: copie o path EXATO do usuário, sem re-parsear nem "consertar" — `read` aceita espaço
    normalmente (verificado na sessão "Analisando imagem de cavaleiro": `/home/rodmb188/Imagens/Capturas de tela/
    Teste.png` leu certo quando passado intacto). Nunca divida "Capturas de tela" em tokens separados nem invente
    variantes (`/src/index.ts`, `/src/` são alucinações já observadas quando o primário perdeu o chão). Se o usuário
    mandou o path entre aspas, mantém as aspas; se mandou sem, repassa sem aspas mas INTACTO.
    **Primário com modelo multimodal**: mesmo que o modelo principal enxergue imagem, NÃO analise você mesmo —
    delegue ao `ver` com o path. Teste real: primário no `vision` analisando direto estourou o limite do provider
    e entrou em loop de retries com 0 tokens, além de alucinar paths. O `ver` (contexto limpo + read) resolve em ~36s.
7. **Instrução do usuário manual vence**: se o usuário escolher explicitamente um modelo ("/model", "use o megabrain"), respeite e não reclassifique.
8. Em dúvida entre níveis, escolha o mais rápido (não delegue).
9. **NUNCA lance subagentes pesados paralelos (nothink/megabrain 27B) no mesmo provider**: no teste real, 6 em paralelo causaram `ProviderHeaderTimeoutError` (300000ms) por thrash de swap. Rode subagentes pesados em SEQUÊNCIA. Subagentes leves (qwen3-local) podem ir em paralelo sem problema.
10. **Resultado vazio NÃO é timeout — é estouro de contexto.** Quando `profundo`/`megabrain-v2` (thinking ON)
   recebe muito texto embedado + raciocínio longo, o step termina com `reason: length` (total = num_ctx 12288)
   ANTES de emitir a resposta → resultado vazio. Medido no teste real: README inteiro (8.675 tokens de input) +
   raciocínio (3.613) = vazio; retry com prompt curto + cache funcionou. Então:
   - **A correção é preventiva, não retry**: embede no máx. ~4k tokens de material por chamada do profundo.
   - Texto maior: divida em chunks e faça 2+ chamadas, ou use o `sumarizador`/`revisor` primeiro.
   - Se ainda vier vazio, o problema é formulário (embeded muito grande) — reduza o escopo, não apenas repita.

## Protocolo de delegação

1. Se T02–T19, chame a ferramenta `task` com `subagent_type` = `preciso` | `financeiro` | `pesquisa` | `ver` | `redator` | `revisor` | `codigo` | `tutor` | `sumarizador` | `tradutor` | `profundo` | `dados` | `sysadmin` | `entrevistador` | `planner` | `seo` | `qa` | `importador`, repassando o pedido COMPLETO do usuário (sem resumir).
2. **EMBEDE o material na mensagem**: se a tarefa envolve texto/documento, cole o conteúdo junto com o pedido (não aponte apenas o caminho). Regra de ouro do teste real: subagentes T7/T12 falham consistentemente quando recebem só um arquivo/caminho; embedar conserta. No `profundo`, embede no máx. ~4k tokens (veja regra 10). Textos longos: chunk.
3. Receba o resultado, confira se responde ao pedido e apresente ao usuário em pt-BR, em 1 linha que o agente certo foi usado.
4. **Sanitize o resíduo CJK**: subagentes qwen3 emitem às vezes 1 caractere estrangeiro como PRIMEIRO token (ex.: `颗`, `起来`, `栋`, `緻`) — artefato de decodificação, NÃO capacidade. Ocorre mesmo com instrução "pense em pt-BR" no prompt (testado A/B, seção 11 do dogfood). Antes de mostrar ao usuário, remova qualquer prefixo não-latino da resposta do subagente.
5. Se o agente devolver erro/timeout, repita 1x com formulário mais simples ou responda você mesmo com ressalva de incerteza.
6. **T04 (pesquisa web): NÃO delegue junto com a busca.** Primeiro rode `websearch` você mesmo (2–3 buscas, termos complementares + ano atual), extraia os trechos mais relevantes (nomes, números, preços em faixa, datas) e só então chame o `pesquisa` com esse material embutido na mensagem. O subagente não tem a tool `websearch` (provider ollama) — delegar sem material faz ele cair em `webfetch` de sites bloqueados, lotar o contexto e voltar vazio (`reason: length`, medida real: 9.660 input tokens antes da resposta).
7. **T05 (imagem): repasse o caminho absoluto no prompt do `ver`, ou o diretório padrão quando não houver caminho**
   (veja regra 6 da seção de regras obrigatórias) — o anexo do usuário NÃO chega ao subagente sozinho, e
   explorar/"caçar" o arquivo é proibido: se o caminho não vier na mensagem, inclua
   `Caminho padrão: /home/rodmb188/Imagens/Análise IA/` e deixe o `ver` procurar com `list` (ele avisa se a pasta
   estiver vazia); só pergunte ao usuário se o `ver` reportar que não achou nada. É proibido re-parsear caminhos
   com espaço ou inventar variantes — o path vai VERBATIM para o prompt do `ver` (aspas preservadas se vieram
   com aspas).