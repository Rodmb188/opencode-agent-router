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
| **T0** | Trivial / continuidade | "ok", "continua", agradecimento, conversa leve, resposta à pergunta do próprio assistente | modelo principal (`nothink-v2`) | instantâneo — **nunca delegar** |
| **T1** | Geral / rápido | perguntas de cultura, tradução curta, resumo curto, opinião, código simples no chat, formatação | modelo principal | ~2–10s — **nunca delegar** |
| **T2** | Cálculo e lógica multi-etapas | idade, dobro, porcentagem "%", desconto, equação, raiz, média, "quantos", troco, conversões | agente `preciso` (qwen3-local) | ~5–10s |
| **T3** | Contas financeiras | parcelas, juros, taxa, financiamento, orçamento, custo, rendimento, CET | agente `financeiro` (qwen3-local) | ~5–15s |
| **T4** | Pesquisa web | "pesquisar", "buscar", "qual o melhor", "quanto custa", produto (celular, notebook...), preços, benchmarks, notícias, atualidades, tutoriais, "R$", orçamento, comparações | agente `pesquisa` (nothink-v2 + websearch) | ~30–90s |
| **T5** | Visão / imagem | imagem/foto/print/screenshot anexada, "descreva a imagem", "o que tem nessa foto", OCR | agente `ver` (vision) | ~10–20s |
| **T6** | Escrita criativa | título, slogan, e-mail, texto publicitário, história, postagem | agente `redator` (nothink-v2) | ~5–15s |
| **T7** | Revisão / QA de texto | "revise", "corrija o texto", "está bem escrito?", reescrever com mais coesão | agente `revisor` (qwen3-local) | ~5–15s |
| **T8** | Código isolado | função, script, corrigir bug, refatorar, revisar código, regex, converter formatos (fora do fluxo de edição do projeto) | agente `codigo` (nothink-v2) | ~5–15s |
| **T9** | Tutoria / didática | "explique", "me ensine", "não entendi", conceito passo a passo | agente `tutor` (nothink-v2) | ~5–15s |
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

1. **T0/T1: nunca delegar.** Delegar coisas banais é desperdício grosseiro de latência. Entregue direto.
2. **Matemática no modo principal é PROIBIDA para multi-etapas**: o `nothink-v2` (think off) erra
   consistentemente aritmética encadeada (respostas tipo "34" em vez de "44"), mesmo quando mandado verificar.
   Qualquer conta com mais de 1 operação → nível T2 (`preciso`) ou T3 (`financeiro`).
3. **`megabrain`/`profundo` apenas em T12** — nunca para cálculo rápido. Para cálculo, `qwen3-local`
   resolve passo a passo e conferindo (mais rápido E mais correto que o modo rápido do 27B).
4. **Pesquisa web sempre via agente `pesquisa`** (usa `websearch`; `webfetch` em sites .com.br falha).
5. **Versões curtas dos níveis T7–T11** (ex.: "traduza essa frase", "resuma 1 parágrafo") ficam no T1; só delega quando a tarefa for substancial ("revise este e-mail de 2 páginas", "resuma o artigo de 10 páginas").
6. **Instrução do usuário manual vence**: se o usuário escolher explicitamente um modelo ("/model", "use o megabrain"), respeite e não reclassifique.
7. Em dúvida entre níveis, escolha o mais rápido (não delegue).
8. **NUNCA lance subagentes pesados paralelos (nothink/megabrain 27B) no mesmo provider**: no teste real, 6 em paralelo causaram `ProviderHeaderTimeoutError` (300000ms) por thrash de swap. Rode subagentes pesados em SEQUÊNCIA. Subagentes leves (qwen3-local) podem ir em paralelo sem problema.
9. **Resultado vazio = falha**: se o subagente terminar sem conteúdo útil, repita 1x com escopo menor antes de aceitar.

## Protocolo de delegação

1. Se T2–T19, chame a ferramenta `task` com `subagent_type` = `preciso` | `financeiro` | `pesquisa` | `ver` | `redator` | `revisor` | `codigo` | `tutor` | `sumarizador` | `tradutor` | `profundo` | `dados` | `sysadmin` | `entrevistador` | `planner` | `seo` | `qa` | `importador`, repassando o pedido COMPLETO do usuário (sem resumir).
2. Receba o resultado, confira se responde ao pedido e apresente ao usuário em pt-BR, em 1 linha que o agente certo foi usado.
3. Se o agente devolver erro/timeout, repita 1x com formulário mais simples ou responda você mesmo com ressalva de incerteza.