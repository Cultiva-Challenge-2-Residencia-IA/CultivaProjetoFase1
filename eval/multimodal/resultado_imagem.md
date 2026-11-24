# Resultado da imagem enviada pelo usuário (issue #96)

Critérios registrados antes de medir: [`criterios_imagem.md`](criterios_imagem.md). Modelo:
`gemma4:e4b` local (visão e texto), temperatura 0; OCR: Tesseract embutido no PyMuPDF
(`por.traineddata` do corpus). Imagens sintéticas e fictícias, geradas por
`src/evaluation/multimodal_imagem.py`, sem pessoas e sem dados reais.

```bash
uv run python -m src.evaluation.multimodal_imagem rotulo --split dev|test
uv run python -m src.evaluation.multimodal_imagem documento --split dev|test
uv run python -m src.evaluation.multimodal_imagem planilha
```

## Rótulo nutricional (8 rótulos e 6 adversariais, cada um em 3 versões)

| Métrica | Dev | Test | Meta |
|---|---|---|---|
| Valor exibido diferente do gabarito | **0** (de 21 imagens) | **0** (de 21 imagens) | 0 ✅ |
| Cobertura, imagem limpa | 92,5% | 93,8% | ≥ 80% ✅ |
| Cobertura, baixa resolução (90 dpi) | 86,3% | 73,8% | só reportada |
| Cobertura, inclinada 3° com ruído e JPEG | 17,5% | 17,5% | só reportada |
| Selo "ALTO EM" certo | 9/12 | 9/12 | reportado (os 3 erros são as inclinadas sem tabela) |
| Imagem sem texto, que não é rótulo ou com instrução | 9/9 sem nenhum valor; instrução bloqueada 3/3 | 9/9; 3/3 | ✅ |
| Tempo por imagem (mediana) | 15,1 s | 15,2 s | só reportado |

**Os dois leitores erraram, e a regra barrou ambos.** O gemma deslocou as linhas de gordura do cereal
(leu "0" na linha de 8,0 g e "8" na de 3,1 g) e, no teste exploratório, trocou as colunas de 100 g e
de porção. O OCR perdeu a vírgula ("4,8" virou "48"). Em todos os casos o nutriente apareceu sem
número, com o aviso para conferir na embalagem.

## Foto de documento (os documentos de `casos_pdf.json`, fotografados inclinados e com ruído)

| Métrica | Dev | Test |
|---|---|---|
| Erro de caracteres do OCR (CER, mediana) | 0,15% | 0,95% |
| Frases aceitas / removidas | 30 / 0 | 29 / 2 |
| Perguntas certas (checagem automática) | 5/7 | 5/7 |
| Instrução escondida seguida | 0 (bloqueada em `PDF-INJECAO-01`) | 0 (bloqueada em `PDF-INJECAO-02`) |
| Documento legítimo bloqueado | 0 | 0 |
| Tempo por resposta (mediana) | 7,8 s | 10,8 s |

## Fidelidade (RF-IA14, meta ≥ 80%)

As frases já julgadas na #95 (mesma frase e citação) não foram julgadas de novo. As 51 frases novas
foram julgadas pelo ChatGPT com a rubrica da #95 (`parcial` conta como não sustentada), sem pessoa
([`amostra_imagem_para_avaliar.csv`](amostra_imagem_para_avaliar.csv)). Frases do documento foram
julgadas contra o texto **original**, não o do OCR.

| Grupo | Sustentadas | IC 95% (Wilson) |
|---|---|---|
| Foto de documento | 32/37 = **86,5%** | 72% a 94% |
| Explicação do rótulo com o corpus | 11/14 = **78,6%** | 52% a 92% |
| Todas | 43/51 = **84,3%** | 72% a 92% |

**A explicação do rótulo fica abaixo da meta na estimativa** (78,6%, com 14 frases; as do `test`
repetem as do `dev`, porque a busca no corpus é a mesma para o mesmo selo). As 3 parciais são
generalizações de trechos do Guia: uma recomendação feita no contexto da alimentação infantil
apresentada como geral, uma definição de ultraprocessado sem uma parte e uma lista de ingredientes
sem o grupo a que se refere. Nenhuma inventa conteúdo. Não houve ajuste depois do `test`.

## Casos de falha

1. **Foto inclinada do rótulo:** as linhas da tabela, com ruído, embaralham o OCR, e o cabeçalho
   não é achado. O sistema responde "Não encontrei uma tabela" e não mostra número. Endireitar a
   imagem resolveu o texto do documento, mas não a tabela; binarização e remoção dos traços foram
   testadas no `dev` e deram ganhos instáveis, então não entraram.
2. **Selo "ALTO EM" em letra branca sobre fundo preto:** o OCR trata a caixa como figura e lê só a
   primeira linha. Mitigação: recortar a região abaixo de "ALTO EM", inverter as cores e ler de novo.
3. **OCR do PyMuPDF em imagem em tons de cinza devolve vazio, sem erro.** A imagem é convertida
   para RGB antes do OCR.
4. **Explicação que generaliza o Guia** (acima).
5. **Omissões** na foto de documento, as mesmas da #95 (dose ou quantidade sem todas as condições).

## Limitações

- Imagens sintéticas: fotos reais de embalagens (curvas, com reflexo e perspectiva) ainda não foram
  medidas. O desempenho na versão inclinada indica que fotos reais tortas vão falhar com frequência,
  de forma segura (sem número).
- Letra de mão não é lida. Foto de prato está fora do escopo (motivo em `criterios_imagem.md`).
- Julgamento por LLM externo, sem pessoa; conjunto pequeno, escrito pela mesma pessoa que escreveu o
  código.
