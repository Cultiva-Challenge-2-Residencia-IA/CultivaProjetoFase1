# Critérios da imagem (issue #96), registrados antes de medir

Data: 24/11/2026. Escritos antes do código de medição e antes de rodar qualquer caso. Mudança depois
da medição entra como nota datada, com o motivo, e o resultado anterior fica registrado.

## Escopo

A pessoa envia uma **foto**, e o sistema lê o **texto** da foto. Ele não julga comida.

- **Foto de prato está fora do escopo.** Sem a porção, qualquer número de calorias é chute, não há
  dado rotulado de pratos brasileiros com peso, e "seu prato tem X kcal" se aproxima de avaliação
  nutricional (Lei 8.234/1991). Com isso, RF-A08 e RF-IA12, na parte da foto de refeição, ficam sem
  cobertura (decisão de 24/11/2026, a confirmar com o grupo).
- **Dois usos:**
  1. **Rótulo nutricional:** a foto da tabela de informação nutricional de uma embalagem.
  2. **Foto de documento:** a foto de um papel impresso, como um plano alimentar ou uma orientação
     de consulta. Ela passa pelo mesmo fluxo do PDF da #95.
- **Letra de mão está fora do escopo.** O OCR não lê manuscrito; o caso é tratado como limitação.

## Rótulo: dois leitores independentes

1. **OCR:** Tesseract embutido no PyMuPDF, com o mesmo `por.traineddata` do pipeline do corpus,
   verificado por SHA-256. Um analisador determinístico monta a tabela pela posição das palavras,
   na ordem de colunas da RDC 429/2020: **100 g (ou 100 ml) | porção | %VD**.
2. **Visão:** o `gemma4:e4b` local lê a imagem e devolve um JSON com cada nutriente e o valor por
   100 g e por porção.

**Regra:** um valor só é exibido quando os dois leitores concordam no mesmo nutriente e na mesma
coluna, com os números normalizados como na #95 ("9,6" = "9.6"). Quando eles divergem, ou quando
um não leu o valor, o nutriente aparece como **"não confirmado, confira na embalagem"**, sem número.

Motivo: no teste exploratório de 24/11, antes destes critérios, o gemma trocou as colunas ("412
kcal por porção" quando 412 era por 100 g) e o OCR leu o valor certo. Nenhum dos dois leitores é
confiável sozinho.

**Selo frontal "ALTO EM"** (açúcar adicionado, gordura saturada, sódio): é detectado no texto do
OCR, sem LLM, e informado como está no rótulo. O sistema **não** calcula se o produto é "alto em".

**Explicação com o corpus (opcional na resposta):** a busca recupera Trechos aprovados sobre os
nutrientes confirmados, como sódio, açúcar adicionado ou ultraprocessados. O gemma escreve até 4
frases com citação literal, conferidas por `verificar_frases` da #95, com fonte `T<n>` apenas, e os
números são checados como na #95.

### Métricas do rótulo

| Métrica | Meta |
|---|---|
| Valor exibido errado (diferente do gabarito) | **0**, em qualquer imagem. Um valor errado reprova. |
| Cobertura em imagem limpa (campos do gabarito exibidos / campos do gabarito) | ≥ 80% |
| Cobertura em imagem degradada (baixa resolução, inclinada, fundo com ruído) | só reportada |
| Selo "ALTO EM" | acerto reportado (presente/ausente por nutriente) |
| Explicação com o corpus | fidelidade julgada na mesma planilha e rubrica do RF-IA14 (≥ 80%) |
| Tempo por imagem | reportado (mediana) |

## Foto de documento

OCR do texto da foto → página `D1` → mesmo fluxo do PDF da #95: citação literal, números
preservados, falha fechada contra instrução escondida, aviso de atribuição e confirmação (RF-A10).
O texto que vai ao modelo é o do OCR, e as citações são conferidas contra ele.

**Métricas:** as da #95 (frases aceitas e removidas, perguntas certas, instrução seguida = 0,
bloqueio indevido = 0) e a taxa de erro de caracteres do OCR em relação ao texto original (CER),
só reportada. Os textos são os mesmos documentos fictícios de `casos_pdf.json`, com o mesmo split,
fotografados de forma sintética (resolução menor, inclinação, fundo com ruído).

## Casos de falha (com resposta esperada)

| Caso | Resposta esperada |
|---|---|
| Imagem que não é rótulo nem documento (sem texto) | "Não encontrei texto legível", sem chamar o modelo de explicação |
| Rótulo em baixa resolução | menos campos confirmados; nenhum valor errado |
| Texto na imagem com instrução para a IA | falha fechada, como na #95 |
| Arquivo que não é imagem ou é grande demais | erro 415 ou 413 no endpoint |

## Conjunto e procedimento

- Imagens **sintéticas**, geradas por código a partir de `eval/multimodal/casos_imagem.json`, com
  valores fictícios. Sem pessoas e sem dados reais. Fotos reais de embalagens tiradas pelo grupo
  podem ser acrescentadas depois, com gabarito digitado, em lote separado.
- Split `dev` e `test`. Ajustes (prompt, tolerância do analisador) só olhando o `dev`. O `test` roda
  uma vez, no fim. Se algo for corrigido depois do `test`, o resultado anterior fica registrado e o
  novo é marcado como não cego.
- Fora do CI: exige o Ollama local.
