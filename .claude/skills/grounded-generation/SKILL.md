---
name: grounded-generation
description: Use when generating final answers from retrieved context, enforcing source use, grounding, and explicit citation rules.
---
# grounded-generation

## Quando usar

- a resposta precisa ter citação, fonte e sustentação
- a geração usa trechos recuperados
- você precisa validar termo por termo antes de entregar

## Regras

- todo dado vem do contexto recuperado
- cada afirmação deve ter `source_id`
- janotas de estimativa e fato precisam ser separados
- use tom acolhedor e sem culpa
- IA deve se identificar e mostrar fonte e grau de certeza

## Passos

1. validar contexto e evidência
2. gerar resposta em schema
3. remover claims não sustentadas
4. anexar aviso padrão obrigatório
5. verificar groundedness e citar fonte final

## Checklist

- resposta sem fonte vira `não sei`
- afirmações sustentadas
- esquema validado
- aviso obrigatório presente

## Erros comuns

- inventar dado fora do contexto
- misturar estimativa com fato
- esquecer o aviso obrigatório
