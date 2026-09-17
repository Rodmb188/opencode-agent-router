# Instruções globais (opencode)

## Roteamento automático por níveis (obrigatório)

Ao receber uma pergunta nova, aplique a skill `roteador` e siga a escada de níveis dela:

| Nível | Quando | Ação |
|---|---|---|
| T00/T01 | Trivial, geral, código simples, conversa | Responda você mesmo — **não delegue** |
| **T02** | Matemática/lógica multi-etapas (idade, %, desconto, equação) | Agente `preciso` (qwen3-local) |
| **T03** | Contas financeiras (parcelas, juros, orçamento) | Agente `financeiro` |
| **T04** | Pesquisa web (produtos, preços, notícias, "melhor", R$) | Você busca (websearch) + agente `pesquisa` só sintetiza |
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
- Pesquisa web em T04: **quem busca é você**. Subagentes em `ollama` NÃO recebem a tool `websearch` (o opencode só expõe para provider `opencode`/`opencode-go` ou com `OPENCODE_ENABLE_EXA`/`OPENCODE_ENABLE_PARALLEL` — filtro no registry, testado real, seção 13). Rode 2–3 buscas você mesmo, embedde os trechos na mensagem e delegue ao `pesquisa` apenas síntese/ranqueamento/veredicto. `webfetch` em `.com.br` bloqueia bots.
- Imagem em T05: **o anexo não chega ao `ver` sozinho** — dele nem tenta adivinhar/locar o arquivo. Com caminho do usuário, repasse VERBATIM com `Caminho da imagem: <absoluto>` no prompt; SEM caminho, repasse o **diretório padrão** `Caminho padrão: /home/rodmb188/Imagens/Análise IA/` — o `ver` procura lá com `list` (1 imagem → abre; várias → pergunta qual; vazia → avisa e pede o caminho). O `ver` abre via `read`. **Caminho com espaço é válido**: repasse VERBATIM (não re-parseie "Capturas de tela", não invente `/src/index.ts` — alucinações já vistas quando o primário perdeu o chão). NUNCA delegue a `explore` para "descobrir onde está a screenshot" — teste real: varreu `/public`, `/assets`, `/static`, `/docs` e voltou vazio com a pasta (`Capturas de tela`) nominalmente dada na conversa. Mesmo com primário multimodal, NÃO analise a imagem você mesmo — delegue ao `ver` (primário no `vision` direto estourou o limite do provider e entrou em loop de retries). Se a tarefa exigir interpretação ALÉM da imagem (ex.: cargo atual de figura pública, dados que mudam), o `ver` entrega descrição + identificação e o primário roteia a interpretação para o agente adequado (`pesquisa`, `preciso`, `profundo`) — não force o `ver` a julgar o que ele não pode ver.
- Versões curtas de T07–T11 ficam na camada T00/T01 (responda você mesmo).
- **Nunca** lance subagentes pesados (nothink/megabrain 27B) em paralelo no mesmo provider — no teste real causou `ProviderHeaderTimeoutError`. Rode pesados em sequência; leves (qwen3-local) podem ir em paralelo.
- **Embedde o material na mensagem do subagente, não aponte arquivo**: os subagentes (T7/T12 sobretudo) não leem caminho de arquivo confiavelmente — embedar texto consertou aderência de 0/5 para 3/4 (revisor) e entregou a melhor revisão do stack (profundo, 7 achados reais).
- **Orçamento de contexto do `profundo`/megabrain (thinking ON)**: num_ctx 12288. Embedde no máx. ~4k tokens por chamada; textos maiores em chunks. README inteiro (8.675) + raciocínio estourou e voltou VAZIO (`reason: length`) — retry não resolve, reduza o escopo.
- **Orçamento de contexto canônico**: `num_ctx` e caps de embed por modelo em `docs/CONTEXT_BUDGET.md` (14B=8192/cap ~5k · 27B=12288/cap ~4k · vision=16384/1 imagem por turno). Fonte única — alterou um Modelfile, atualize o doc antes do commit.
- **Idioma pt-BR com rigor máximo — vale para VOCÊ e para TODOS os subagentes**: toda saída (raciocínio e resposta) em português, só caracteres latinos. Vazamento de outro alfabeto é artefato de decodificação do modelo (smoke T16 r5/B01) e reprova a entrega — **não escreva exemplos desses caracteres nas próprias regras**: eles funcionam como isca e podem aumentar o vazamento. Dever do primário: **inspecionar a saída completa do subagente (início, meio e fim)** e sanitizar antes de mostrar; nunca repassar resposta com caracteres estrangeiros. A sanitização é rede de segurança — a solução definitiva é estrutural (parser que corta o raciocínio na fonte); ver JOURNAL T16 r7.
- **Contagem de caracteres/vocábulos (bom senso)**: pedido com "N caracteres" exige entrega na 1ª tentativa com margem pequena (±5% ou ±10, o que for maior), contagem EXATA informada junto e SEM reescrita infinita atrás do número certo — a decisão de aceitar é do usuário, que não deve esperar meia hora por uma resposta simples.
- **Resumo final obrigatório — SOMENTE o assistente principal**: ao terminar QUALQUER tarefa, VOCÊ escreve um resumo curto começando com `Resumo:` (norma culta informal, sem emojis). **Subagentes NÃO escrevem "Resumo:"** — subagente que acrescenta resumo não pedido reprova a entrega; entregue apenas o que foi pedido. (Achado: subagentes herdavam a regra do AGENTS global; ver JOURNAL T16 r7.)
- Pedido manual de modelo do usuário vence qualquer regra automática.