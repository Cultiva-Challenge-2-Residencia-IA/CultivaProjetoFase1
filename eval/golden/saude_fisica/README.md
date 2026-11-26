# Golden Set de Saúde Física (Fase 2)

Conjunto de avaliação de respostas, recuperação, guardrails legais (Lei nº 9.696/1998 e ausência de diagnóstico), robustez adversarial, abstenção e roteamento entre abas para o **Agente de Saúde Física** do CULTIVA.

> **Status:** Rascunho (`status_revisao: rascunho` e `autoria.revisao: pendente` em todos os 72 casos). Nenhum caso foi revisado por profissional de saúde ou Educação Física ainda. Este conjunto nasce **informativo** (não está ligado a gate de CI).

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `dev.json` | 36 casos de desenvolvimento (`fis-dev-0001` a `fis-dev-0036`). |
| `test.json` | 36 casos de holdout (`fis-test-0001` a `fis-test-0036`). **Não ajuste prompts, léxico ou limiares olhando para o `test`.** |
| `caso.schema.json` | JSON Schema próprio que adapta e estende o schema do golden v2 (`eval/golden/v2/caso.schema.json`) para suportar campos ricos, localizador flexível (`pagina_pdf` ou `secao`) e o tipo `entre_abas`, sem modificar o v2. |
| `MANIFEST.json` | Versão, data, contagens por split e tipo, SHA-256 dos arquivos do golden, hash de `corpus/manifest.yaml`, `corpus_version` e SHA-256 normalizado (LF) dos Markdowns usados. |
| `CHANGELOG.md` | Histórico de alterações do conjunto. |

## Distribuição dos 72 casos

| Tipo | `dev` | `test` | Total | Comportamento esperado |
|---|---:|---:|---:|---|
| `recuperacao` | 18 | 18 | 36 | `responder` (com evidência literal e fonte aprovada) |
| `prescricao` | 6 | 6 | 12 | `redirecionar_prescricao` (Lei nº 9.696/1998 ou encaminhamento clínico) |
| `adversarial` | 4 | 4 | 8 | `recusar_adversarial` / `redirecionar_prescricao` (injection, roleplay, premissa falsa, "meu personal mandou") |
| `fora_de_escopo` | 4 | 4 | 8 | `nao_sei` (fora do domínio ou fonte ainda `pendente`) |
| `entre_abas` | 4 | 4 | 8 | `rotear_entre_abas` (Nutrição + Saúde Física ou redirecionamento para Estudos) |
| **Total** | **36** | **36** | **72** | |

## Comandos

```bash
# Validar apenas o dev (padrão seguro; não lê o holdout)
uv run python -m src.evaluation.golden_saude_fisica validar

# Validar dev + test e checar ausência de vazamento dev/test
uv run python -m src.evaluation.golden_saude_fisica validar --incluir-test

# Estatísticas (exige --incluir-test para incluir o holdout)
uv run python -m src.evaluation.golden_saude_fisica estatisticas [--incluir-test]

# Avaliar recuperação e qualidade das respostas frente ao modelo ideal (`resposta_referencia`)
uv run python -m src.evaluation.golden_saude_fisica avaliar --split dev [--sem-llm | --respostas respostas.json]
```

### Controle de vazamento `dev`/`test`

O validador bloqueia sobreposição entre `dev` e `test` quando a similaridade entre duas perguntas normalizadas (sem acentos, minúsculas, sem pontuação) atinge:
- **Jaccard de tokens de conteúdo** (sem stopwords) `>= 0.65`, ou
- **SequenceMatcher ratio** `>= 0.78`.

Esses limiares barram variantes próximas e paráfrases do mesmo enunciado sem gerar falsos positivos por termos comuns do domínio (como "atividade física" ou "dor lombar").

## Nota metodológica para métricas futuras

Como a amostra por tipo e por split é pequena (`n = 36` por split; `n = 4` a `18` por tipo), qualquer avaliação futura sobre este conjunto deve reportar **intervalo de confiança (bootstrap)** junto com o **`n` explícito** de cada estrato.

## Limitações conhecidas

- **Autoria única (IA):** os 72 casos foram gerados inicialmente por agente de IA e aguardam revisão humana e validação por profissional da área.
- **Fontes em inglês:** a maioria das 29 fontes aprovadas de Saúde Física está em inglês (`en`), exigindo tradução fiel nas respostas de referência.
- **Conversão e hashes:** alguns PDFs possuem avisos de conversão nos relatórios originais; além disso, o `verify_corpus.py` apresenta divergência pré-existente no Markdown do Guia Alimentar de Nutrição (CRLF no Windows), e a linhagem de hashes contra os relatórios de conversão não foi revalidada neste trabalho.
- **Fontes não catalogadas:** os arquivos `18-jospt-patellofemoral-pain-cpg-2019.md`, `20-who-rehabilitation-musculoskeletal-annex-2023.md` e `21-ms-guia-atividade-fisica-gestores-profissionais-2021.md` existem em `corpus/saudefisica/markdown/`, mas não constam em `corpus/manifest.yaml` nem possuem JSONL em `corpus/saudefisica/rag/`, por isso não foram usados como evidência aprovada.

## Checklist de revisão humana (para o PR)

- [ ] Conferir se todas as perguntas em `dev.json` e `test.json` estão naturais em pt-BR e adequadas ao público 18+ (ou recomendação populacional informativa).
- [ ] Validar que nenhum caso de `prescricao`, `adversarial`, `fora_de_escopo` ou `entre_abas` prescreve séries, cargas, repetições, dietas ou diagnósticos na `resposta_referencia`.
- [ ] Conferir em amostra dos casos de `recuperacao` se a tradução do `trecho_literal` (fontes em inglês) está fiel e sem exagero na `resposta_referencia`.
- [ ] Confirmar a classificação de `deve_encaminhar_profissional` e `roteamento_esperado` nos casos de `entre_abas`.
- [ ] Atualizar `status_revisao` para `revisado` e preencher `autoria.revisao: "revisado"` e `autoria.revisor` nos casos aprovados.
