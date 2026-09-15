---
name: pesquisa-web
description: Use quando o usuário pedir qualquer tipo de pesquisa, busca, consulta, comparação ou recomendação de informações na web — incluindo produtos, celulares, notícias, preços, benchmarks, tutoriais, notícias de tecnologia, clima, atualidades e fatos. Aplica-se a buscas em português do Brasil e mercados brasileiros (R$), mas também a buscas em geral. Instrui a usar a ferramenta websearch em vez de webfetch para obter resultados confiáveis.
---

# Pesquisa web confiável

Objetivo: obter resultados de pesquisa confiáveis e atuais sem cair em erros de transporte ("Transport error") do `webfetch`.

## Regra principal

Sempre que a tarefa envolver **pesquisar, buscar, consultar ou comparar informações na web** — de qualquer tipo (produtos, notícias, fatos, tutoriais, preços, specs, eventos atuais, etc.) — **prefira a ferramenta `websearch`** em vez do `webfetch`.

Motivo: vários sites (especialmente os `.com.br`) retornam "Transport error" ou bloqueiam o fetch direto. A ferramenta `websearch` retorna títulos, links, datas de publicação e trechos relevantes mesmo para esses sites.

## Fluxo sugerido

1. Rode **2 ou mais buscas `websearch`** paralelas com termos complementares e variações do tema (idioma, sinônimos, "2026", "melhor", "como", etc.).
2. Priorize fontes confiáveis e recentes: portais de notícias, sites oficiais, blogs reconhecidos e resultados com data de publicação próxima.
3. Extraia dos trechos (Highlights) os dados essenciais: nomes, números, datas, preços, opiniões e conclusões.
4. Se um link individual for absolutamente necessário, tente o `webfetch` apenas para URLs de sites que se sabe que funcionam (ex.: `tomsguide.com`, Wikipedia). Não insista em caso de erro: volte ao `websearch`.
5. Entregue a resposta no idioma do usuário, organizada e com a data/fonte da informação quando relevante.

## Diretrizes para a resposta

- Organize por relevância ao que o usuário pediu (critérios, orçamento, data, etc.).
- Inclua data da informação, faixas de preço (~R$1.950–2.097) ou números concretos quando fizer sentido.
- Justifique cada item em 1 linha.
- Quando apropriado, finalize com um "Veredicto"/conclusão escolhendo a opção principal e alternativas.
- Em pesquisas de mercado/compras, ressalte que preços flutuam e que vale conferir antes de fechar.