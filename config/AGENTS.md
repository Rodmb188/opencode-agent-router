# Instruções globais (opencode)

## Roteamento automático por níveis (obrigatório)

Ao receber uma pergunta nova, aplique a skill `roteador` e siga a escada de níveis dela:

| Nível | Quando | Ação |
|---|---|---|
| T00/T01 | Trivial, geral, código simples, conversa | Responda você mesmo — **não delegue** |
| **T02** | Matemática/lógica multi-etapas (idade, %, desconto, equação) | Agente `preciso` (qwen3-local) |
| **T03** | Contas financeiras (parcelas, juros, orçamento) | Agente `financeiro` |
| **T04** | Pesquisa web (produtos, preços, notícias, "melhor", R$) | Agente `pesquisa` |
| **T05** | Imagem/foto/print/OCR | Agente `ver` |
| **T06** | Escrita criativa (título, slogan, e-mail, texto) | Agente `redator` (nothink-v2, venceu A/B) |
| **T07** | Revisão de texto (gramática, coesão, QA) | Agente `revisor` |
| **T08** | Código isolado (função, bug, refactor) | Agente `codigo` |
| **T09** | Tutoria didática ("explique", "me ensine") | Agente `tutor` |
| T10 | Resumo de texto longo | Agente `sumarizador` |
| T11 | Tradução técnica/extensa | Agente `tradutor` |
| T12 | Análise profunda, decisão crítica, prova, otimização | Agente `profundo` (megabrain) |
| T13 | Análise de dados (CSV, planilhas, pandas) | Agente `dados` |
| T14 | Sysadmin/automação Linux (comandos, docker) | Agente `sysadmin` |
| T15 | Simulação de entrevista | Agente `entrevistador` |
| T16 | Planejamento de projetos (etapas, cronograma) | Agente `planner` |
| T17 | SEO pt-BR | Agente `seo` |
| T18 | QA/conferência final ("confira se está certo") | Agente `qa` |
| T19 | Conversão de formatos (CSV↔JSON↔XML) | Agente `importador` |

Regras de ferro:
- **Nunca** delegue tarefas banais (T00/T01) — o roteador existe para evitar latência desnecessária.
- **Nunca** resolva matemática de múltiplas etapas no modelo principal: ele erra aritmética mesmo quando instruído a verificar. Use `preciso` ou `financeiro`. `megabrain`/`profundo` é só para T12.
- Pesquisa web sempre via `pesquisa` (websearch; webfetch em `.com.br` falha).
- Versões curtas de T07–T11 ficam na camada T00/T01 (responda você mesmo).
- **Nunca** lance subagentes pesados (nothink/megabrain 27B) em paralelo no mesmo provider — no teste real causou `ProviderHeaderTimeoutError`. Rode pesados em sequência; leves (qwen3-local) podem ir em paralelo.
- **Embedde o material na mensagem do subagente, não aponte arquivo**: os subagentes (T7/T12 sobretudo) não leem caminho de arquivo confiavelmente — embedar texto consertou aderência de 0/5 para 3/4 (revisor) e entregou a melhor revisão do stack (profundo, 7 achados reais).
- **Orçamento de contexto do `profundo`/megabrain (thinking ON)**: num_ctx 12288. Embedde no máx. ~4k tokens por chamada; textos maiores em chunks. README inteiro (8.675) + raciocínio estourou e voltou VAZIO (`reason: length`) — retry não resolve, reduza o escopo.
- **Pense em pt-BR**: escreva o raciocínio e a resposta em português; saída nunca com vestígios de outros idiomas (vazamentos CJK/latim ocorreram em teste real).
- Pedido manual de modelo do usuário vence qualquer regra automática.