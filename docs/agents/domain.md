# Documentação de domínio

Como as skills de engenharia devem usar a documentação de domínio deste repositório ao explorar o código.

## Antes de explorar, leia

- **`GLOSSARY.md`**, na raiz: o vocabulário do sistema multiagentes (Orquestrador, Agente de área, Sincronizador, Chat geral, Portão, Subpergunta e outros).
- **`docs/adrs/`** (no plural): os ADRs que tocam a área em que você vai trabalhar. Todo o repositório é um contexto só; não há ADRs por módulo.
- **Requisitos:** RN, RF-A, RF-IA e RNF ficam no repositório [Documentacao-Cultiva](https://github.com/Cultiva-Challenge-2-Residencia-IA/Documentacao-Cultiva) (`docs/requisitos/`, `docs/regras-de-negocio.md`). Leia os que a mudança toca; não os copie para cá.

Se algum desses arquivos não existir, siga sem avisar. A skill `/domain-modeling` (chamada pelo `/grill-with-docs` e pelo `/improve-codebase-architecture`) cria glossário e ADRs quando um termo ou uma decisão é de fato resolvido.

## Estrutura

```
/
├── GLOSSARY.md
├── docs/adrs/
│   ├── 0001-arquitetura-rag-hibrido-taco-grafo-4-camadas.md
│   ├── ...
│   └── 0006-provedor-embeddings-e-banco-vetorial.md
└── src/
```

ADR novo segue a numeração de `docs/adrs/` (`NNNN-titulo-em-kebab-case.md`), em português, no formato dos existentes (Status, Data, Escopo, Contexto, Decisão, Alternativas, Consequências).

## Use o vocabulário do glossário

Ao nomear um conceito de domínio (título de issue, proposta, hipótese, nome de teste), use o termo como está no `GLOSSARY.md` e evite os sinônimos marcados como "Evitar".

Se o conceito ainda não está no glossário, é um sinal: ou você está inventando um termo que o projeto não usa (reconsidere), ou há uma lacuna real (anote para o `/domain-modeling`).

## Aponte conflitos com ADRs e requisitos

Se o que você propõe contradiz um ADR ou um requisito, diga isso explicitamente em vez de passar por cima:

> _Contradiz o ADR 0005 (arquitetura multiagentes), mas vale reabrir porque..._

Decisão que muda um requisito precisa ser levada também ao Documentacao-Cultiva, num PR naquele repositório.
