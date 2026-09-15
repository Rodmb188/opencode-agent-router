# Instruções globais (opencode)

## Roteamento automático por níveis (obrigatório)

Ao receber uma pergunta nova, aplique a skill `roteador` e siga a escada de níveis dela:

| Nível | Quando | Ação |
|---|---|---|
| T0/T1 | Trivial, geral, código simples, conversa | Responda você mesmo — **não delegue** |
| T2 | Matemática/lógica multi-etapas (idade, %, desconto, equação) | Agente `preciso` (qwen3-local) |
| T3 | Contas financeiras (parcelas, juros, orçamento) | Agente `financeiro` |
| T4 | Pesquisa web (produtos, preços, notícias, "melhor", R$) | Agente `pesquisa` |
| T5 | Imagem/foto/print/OCR | Agente `ver` |
| T6 | Escrita criativa (título, slogan, e-mail, texto) | Agente `redator` (nothink-v2, venceu A/B) |
| T7 | Revisão de texto (gramática, coesão, QA) | Agente `revisor` |
| T8 | Código isolado (função, bug, refactor) | Agente `codigo` |
| T9 | Tutoria didática ("explique", "me ensine") | Agente `tutor` |
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
- **Nunca** delegue tarefas banais (T0/T1) — o roteador existe para evitar latência desnecessária.
- **Nunca** resolva matemática de múltiplas etapas no modelo principal: ele erra aritmética mesmo quando instruído a verificar. Use `preciso` ou `financeiro`. `megabrain`/`profundo` é só para T12.
- Pesquisa web sempre via `pesquisa` (websearch; webfetch em `.com.br` falha).
- Versões curtas de T7–T11 ficam no T1 (responda você mesmo).
- **Nunca** lance subagentes pesados (nothink/megabrain 27B) em paralelo no mesmo provider — no teste real causou `ProviderHeaderTimeoutError`. Rode pesados em sequência; leves (qwen3-local) podem ir em paralelo.
- Pedido manual de modelo do usuário vence qualquer regra automática.