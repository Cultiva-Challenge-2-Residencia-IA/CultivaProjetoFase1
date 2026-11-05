# Data model

## Entidades principais

### `Source`

```yaml
id: string
title: string
publisher: string | null
type: string
url: string | null
license: string | null
data_publicacao: string | null
```

### `Chunk`

```yaml
chunk_id: string
source_id: string
title: string
section: string
page: integer | null
url: string | null
corpus_version: string
text_raw: string
text_embed: string
```

### `RetrievalResult`

```yaml
chunk_id: string
source_id: string
score_dense: float
score_lexical: float
rrf_score: float
```

### `Answer`

```yaml
answer: string
claims:
  - texto: string
    source_ids: [string]
    tipo: string
confianca: string
recusou: boolean
motivo: string | null
avisos: [string]
trace_id: string
```

## Regras

- `chunk_id` deve ser estável por fonte e hash.
- `corpus_version` reflete hash do manifesto.
- `text_embed` concatena `[Documento > Seção]` + texto.
- `source_id` deve estar na whitelist.
- Respostas devem sempre citar `source_id` ou retornar `não sei`.
