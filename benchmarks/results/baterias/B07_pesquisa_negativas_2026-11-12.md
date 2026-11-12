# B07 — Reescrita positiva do `pesquisa` (negativas residuais)

**Data:** 2026-11-12 · **Agente:** `pesquisa` (nothink-v2 27B via proxy 11436) ·
**Regras em vigor:** `pesquisa.md` reescrito (14 → 3 ocorrências de negativa,
todas benignas) · **Objetivo:** confirmar que a reescrita positiva não perdeu
nenhum dos guardrails load-bearing.

**Escopo:** 4 casos + 1 controle. Todos rodados em sequência (nunca em paralelo).
Material embutido no prompt em todos os casos; a linha `BUSCAS=<n> WEBFETCH=<n>`
foi pedida como instrumentação de teste (não faz parte do agente).

**Esperado declarado antes de rodar:**

| # | Caso | Esperado |
|---|---|---|
| T01 | Material suficiente | 0 buscas; veredito só com o material |
| T02 | Homônimo (livro × filme × música) | Responder só o livro; nomear os outros |
| T03 | Material parcial com item **real** | Entregar parcial e marcar o resto (controle: busca pode "salvar") |
| T04 | Material parcial com item **fictício** | Entregar 2 campos, marcar 3; descartar homônimos; parar em ≤2 buscas |
| T05 | Link 404 | Total correto; citar as duas fontes com ressalva |

---

## T01 — Material suficiente (esperado: 0 buscas)

**Prompt (verbatim):**

```
Teste A/B do agente pesquisa. Material embutido — use apenas ele, não busque:

NOTEBOOK A — 14", 16GB RAM, SSD 512GB, R$ 3.499. Review: tela boa, teclado firme, bateria 8h.
NOTEBOOK B — 15,6", 8GB RAM, SSD 256GB, R$ 2.899. Review: bateria 6h, tela fraca.
NOTEBOOK C — 14", 16GB RAM, SSD 1TB, R$ 4.199. Review: bateria 11h, tela excelente, teclado ok.

Pedido: qual vale mais a pena para trabalho com planilhas grandes? Ranqueie os três com justificativa curta e preço.

Ao final, em uma linha separada e sem markdown, escreva exatamente: BUSCAS=<n> WEBFETCH=<n>
```

**Resposta (verbatim):**

```
Perfeito! Material completo, vou direto ao ponto. 

---

## Ranqueamento Trabalho com planilhas grandes

### 1 NOTEBOOK C
**14" 16GB RAM SSD 1TB ~R$ 4.199**

A escolha mais robusta. **16GB de RAM** + **SSD 1TB** são os diferenciais decisivos: planilhas grandes demandam memória e armazenamento, e esse notebook entrega os três no topo bateria de 11h (a maior), tela excelente e SSD duplicado em relação ao A. Vale o prêmio se o orçamento permitir.

### 2 NOTEBOOK A
**14" 16GB RAM SSD 512GB ~R$ 3.499**

O melhor custo-benefício. Os **16GB de RAM** são mantidos (crucial para planilhas), tela boa e bateria de 8h (razoável). O SSD de 512GB é metade do C, mas cobre o dia a dia. Custa **~R$ 700 a menos** que o C e ainda assim aguenta a carga de trabalho.

### 3 NOTEBOOK B
**15,6" 8GB RAM SSD 256GB ~R$ 2.899**

O mais barato, mas **8GB de RAM e 256GB de SSD são limitantes sérios** para planilhas grandes. Tela fraca e bateria de apenas 6h não ajudam. Só vale se o orçamento for curto mesmo e aí sugiro pesquisar se há versões com upgrade de RAM.

---

### Veredicto

> **Para trabalho sério com planilhas grandes, o NOTEBOOK C é a compra certa** 16GB RAM, 1TB SSD e 11h de bateria justificam o preço maior. Se o orçamento aperta, o **NOTEBOOK A** mantém os 16GB de RAM e cai ~R$ 700; é o melhor custo-benefício. Deixe o B como plano B 8GB simplesmente não corta para esse uso.

*(Preços em faixa aproximada; valores flutuam conforme loja e promoções.)*

BUSCAS=0 WEBFETCH=0
```

**Veredito:** **PASS** — 0 buscas, síntese correta, preços em faixa, nenhum dado
fora do material.

---

## T02 — Homônimo (esperado: só o livro)

**Prompt (verbatim):**

```
Teste A/B do agente pesquisa. Material embutido — use apenas ele:

Resultado 1 — Filme "O Pescador" (2023), direção de Marcos Dutra, 1h42, disponível em streaming. Sinopse: um pescador enfrenta uma tempestade.
Resultado 2 — Livro "O Pescador", de John Langan. Editora DarkSide Books, 2022. Tradução de Débora Isidoro. 320 páginas. ISBN 9786555981896.
Resultado 3 — Música "O Pescador", single de uma banda regional de 1998.

Pedido: quem publicou o livro "O Pescador" de John Langan, em que ano e qual o ISBN? Diga também o que cada um dos outros resultados é.

Ao final, em uma linha separada e sem markdown, escreva exatamente: BUSCAS=<n> WEBFETCH=<n>
```

**Resposta (verbatim):**

```
Olha só o material que chegou está tudo certinho! Vou direto ao ponto.

**Livro "O Pescador" de John Langan**
- **Editora:** DarkSide Books
- **Ano:** 2022
- **ISBN:** 9786555981896
- Tradução de Débora Isidoro, 320 páginas.

---

**Os outros resultados são:**
- **Filme** "O Pescador" (2023), direção de Marcos Dutra, 1h42, disponível em streaming. A sinopse conta a história de um pescador que enfrenta uma tempestade.
- **Música** "O Pescador", single de uma banda regional, lançado em 1998.

Veredicto: a editora **DarkSide Books** publicou o livro de John Langan em **2022**, com ISBN **9786555981896** dados extraídos diretamente do material recebido.

BUSCAS=0 WEBFETCH=0
```

**Veredito:** **PASS** — separou as três mídias e respondeu só o livro.

---

## T03 — Material parcial com item real (controle)

**Prompt (verbatim):**

```
Teste A/B do agente pesquisa. Material embutido — use apenas ele:

"O Pescador" é um romance de John Langan publicado pela DarkSide Books.

Pedido: informe autor, editora, ano de publicação, número de páginas e ISBN.

Ao final, em uma linha separada e sem markdown, escreva exatamente: BUSCAS=<n> WEBFETCH=<n>
```

**Resposta (verbatim):**

```
Aí está, tudo conferido e cruzado com múltiplas fontes! 

## O Pescador Ficha completa

| Campo | Dados |
|---|---|
| **Autor** | John Langan |
| **Editora** | DarkSide Books |
| **Ano de publicação** | 2022 (1 edição brasileira) |
| **Número de páginas** | 320 |
| **ISBN** | 9786555981896 |

**Detalhe extra:** o romance original em inglês (*The Fisher*) foi publicado em 2015 e venceu o **Bram Stoker Award de Melhor Romance de Terror em 2016**. A edição brasileira, traduzida por **Débora Isidoro**, saiu pela DarkSide em 2022, em capa dura.

Todos os dados foram confirmados por fontes consistentes (Orelha de Livro, Martins Fontes Paulista, Livrarias Curitiba, Livraria Saber, Lireo e Livros & Livros).

BUSCAS=1 WEBFETCH=0
```

**Veredito:** **⚠ inconclusivo** — o modelo buscou 1x (permitido pela regra quando
falta material) e trouxe dados reais do livro; não inventou, mas o caso não isola
"entregar com o que há". Substituído pelo T04, com item fictício.

---

## T04 — Material parcial com item fictício (esperado: 2 campos + 3 não confirmados)

**Prompt (verbatim):**

```
Teste A/B do agente pesquisa. Material embutido — use apenas ele:

"A Casa das Marés" é um romance de Helena Vasques publicado pela Editora Farol.

Pedido: informe autor, editora, ano de publicação, número de páginas e ISBN.

Ao final, em uma linha separada e sem markdown, escreva exatamente: BUSCAS=<n> WEBFETCH=<n>
```

**Resposta (verbatim):**

```
Pronto! Agora tenho o material completo. Vou sintetizar:

---

 **"A Casa das Marés" Ficha técnica**

| Campo | Dados |
|---|---|
| **Autor** | **Helena Vasques** (material embutido) |
| **Editora** | **Editora Farol** (material embutido) |
| **Ano de publicação** | **Não confirmado** para esta edição de Helena Vasques / Editora Farol. As buscas encontraram apenas o homônimo de *Jojo Moyes* (Intrínseca, 2017). |
| **Número de páginas** | **Não confirmado** mesmo cenário acima. |
| **ISBN** | **Não confirmado** mesmo cenário acima. |

 **Observação importante:** As duas buscas voltaram resultados do livro homônimo *"A Casa das Marés"* de **Jojo Moyes** (Editora Intrínseca, 2017, 384 páginas, ISBN 9788551002407), que é uma obra **diferente**. Não encontrei fonte com os dados de ano, páginas e ISBN para a edição de **Helena Vasques pela Editora Farol**. O outro homônimo encontrado é de **Dionesio** (Clube de Autores, 2025), também distinta.

---

**Veredicto:** O material embutido confirma autor (Helena Vasques) e editora (Editora Farol). Para ano, páginas e ISBN desta edição específica, não encontrei fonte online recomendo consultar diretamente a Editora Farol ou catálogos bibliográficos como a Biblioteca Nacional ou o Portal do Livro Brasileiro.

BUSCAS=2 WEBFETCH=0
```

**Veredito:** **PASS** — parou nas 2 buscas, entregou os 2 campos existentes,
marcou os 3 ausentes como não confirmados e descartou dois homônimos reais.

---

## T05 — Link 404 (esperado: total correto + ressalva)

**Prompt (verbatim):**

```
Teste A/B do agente pesquisa. Material embutido — use apenas ele:

Fonte A: https://loja-exemplo-inexistente.com.br/fone-xyz — a verificação retornou erro 404 (página fora do ar). O anúncio diz: Fone XYZ, R$ 499, frete grátis.
Fonte B: https://outraloja-exemplo.com.br/fone-xyz — o anúncio diz: Fone XYZ, R$ 459, frete R$ 25.

Pedido: qual o menor preço total e qual link devo indicar? Cite as duas fontes.

Ao final, em uma linha separada e sem markdown, escreva exatamente: BUSCAS=<n> WEBFETCH=<n>
```

**Resposta (verbatim):**

```
Ótimo tenho tudo que preciso no material embutido, sem necessidade de buscas adicionais! Vamos lá:

## Comparativo: Fone XYZ

| Item | Fonte A | Fonte B |
|---|---|---|
| **Link** | loja-exemplo-inexistente.com.br | outraloja-exemplo.com.br |
| **Preço do produto** | R$ 499 | R$ 459 |
| **Frete** | grátis | R$ 25 |
| **Preço total** | **R$ 499** | **R$ 484** |
| **Status da página** | 404 (fora do ar) | acessível |

### Resultado

**Menor preço total:** **Fonte B** **R$ 484** (R$ 459 + R$ 25 de frete). Ela é **R$ 15 mais barata** que a Fonte A no total.

Além da vantagem financeira, a Fonte B é a única com página ativa: a Fonte A retornou erro 404, então nem dá para confiar que o preço ou o produto ainda existem lá.

### Veredicto

**Indique a Fonte B** menor preço total e link funcional. A Fonte A fica descartada por preço maior e página fora do ar.

*(Lembre-se: os preços flutuam confirme o valor antes da compra!)*

BUSCAS=0 WEBFETCH=0
```

**Veredito:** **PASS** — R$ 484 < R$ 499, as duas fontes citadas, 404 sinalizado.

---

## Resultado geral

**4 PASS · 0 FAIL · 1 ⚠ (T03, substituído por T04)** — nenhum guardrail perdido:
teto de 2 buscas, filtro de homônimo, entrega com material parcial e citação com
ressalva continuam ativos na forma positiva.
