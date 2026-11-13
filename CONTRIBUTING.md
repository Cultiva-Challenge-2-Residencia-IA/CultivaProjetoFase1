# Como contribuir com o CULTIVA

Este repositório tem o corpus de Nutrição e o RAG que o consome. As regras completas estão em [`AGENTS.md`](AGENTS.md), escrito também para agentes de IA, e o estado do código e os comandos estão em [`CLAUDE.md`](CLAUDE.md). Este guia resume o fluxo de trabalho para quem contribui.

Requisitos (RN, RF-A, RF-IA, RNF) e arquitetura são discutidos no repositório [Documentacao-Cultiva](https://github.com/Cultiva-Challenge-2-Residencia-IA/Documentacao-Cultiva).

## Limites do produto

Nenhuma contribuição pode contradizer estes pontos:

- **A IA não diagnostica nem prescreve** (RN01, RN02). Pedidos de dieta, dose ou diagnóstico individual são redirecionados.
- **Toda resposta técnica cita fonte aprovada do corpus** (RN04, RN16, RN17). Sem evidência, a resposta é "não sei" (RF-IA01).
- **Sinal de risco interrompe o fluxo** com a mensagem fixa de acolhimento e o CVV 188 (RF-IA03).
- **Dados de usuários não entram no corpus,** nos casos de avaliação nem nos logs em texto claro (RNF05).

## Ambiente

```bash
uv sync                                   # aplicação (Python 3.11+)
python3 -m venv corpus/.venv              # pipeline de corpus
corpus/.venv/bin/python -m pip install -r corpus/scripts/requirements.txt
```

O LLM padrão é o Ollama local (ADR 0003, `docs/adrs/0003-provedor-llm-e-dados-pessoais.md`). Sem Ollama rodando, o consultor usa a síntese extrativa local, que é o modo do CI. A Groq só é usada com `LLM_PROVIDER=groq` e `ALLOW_EXTERNAL_LLM=true`, e não com dados pessoais reais. Chaves de API ficam no `.env`, que o Git ignora.

## Fluxo de trabalho

1. **Issue primeiro.** Abra ou escolha uma issue com um dos modelos (tarefa, bug, fonte para o corpus ou decisão). Atribua a issue a você antes de começar.
2. **Branch a partir da `main`,** com o tipo e o número da issue: `feat/issue-13-benchmark-v2`, `fix/issue-36-italico`, `docs/...`.
3. **Commits em [Conventional Commits](https://www.conventionalcommits.org/pt-br/), em português:** `feat(rag): …`, `fix(corpus): …`, `docs: …`, `eval(risco): …`. O corpo explica o porquê, não só o quê.
4. **Pull request com o modelo do repositório.** Use `Closes #N` quando o PR fecha a issue e `Refs #N` quando fecha só uma parte, dizendo o que falta.
5. **CI.** Ruff, pytest e integridade do corpus são obrigatórios. O job "Gates de avaliação" é informativo, mas uma falha nova nele precisa de explicação no PR.
6. **Revisão.** Peça revisão de pelo menos uma pessoa que não escreveu o código. Quem revisa pode pedir mudanças; responda a cada ponto no próprio PR.
7. **Merge com squash,** para a `main` ficar com um commit por PR e com o título no padrão.

## Regras por área

### Corpus

- Siga "Como incluir outro documento" e "Aprovação" em [`corpus/README.md`](corpus/README.md). Converter não é aprovar.
- **Não edite os `.md` convertidos à mão.** Correções vão para `corpus/scripts/config/` ou `corpus/scripts/ajustes/`, seguidas de nova conversão.
- **Mudou o manifesto, o `prepare_rag.py` ou o `rag.yaml`?** Regenere os Trechos no mesmo PR. Senão, o `verify_corpus.py` falha.
- Registre a licença real de cada fonte, ou `pendente`. Ela não bloqueia a aprovação (aceite de risco de 06/11/2026), mas o aceite não vale para uso comercial nem para publicar o corpus.

### Recuperação, respostas e guardrails

- **Meça antes e depois.** Mudanças que podem afetar respostas rodam o benchmark v1 duas vezes (os relatórios precisam ser idênticos), o golden set v2 e o `gate.py`. Registre no PR todas as métricas, inclusive as que pioraram.
- **Baseline do CI:** se as métricas mudaram de propósito, atualize `eval/baselines/benchmark_offline.json` no mesmo PR e justifique.

### Avaliação

- **Ajuste só no `dev`.** O split `test` e os holdouts servem para medir, nunca para orientar mudanças.
- **Holdout é de outra pessoa.** Quem altera o léxico de risco ou outra regra não acrescenta casos ao holdout no mesmo PR (`eval/risco/README.md`). Quando um holdout orientar uma mudança, ele vai para o `dev`, e alguém escreve um lote novo, sem olhar as regras.
- **Resultado desfavorável fica registrado.** Não escolha só os exemplos que funcionam, nem afrouxe um gate sem explicar por quê.

### Segurança e privacidade

- Nada de dados pessoais reais, segredos ou endereços de infraestrutura no código, nos testes, nos casos de avaliação ou nas issues.
- Mudanças no léxico de risco ou na mensagem de acolhimento são revisadas no PR e medidas nos dois conjuntos de `eval/risco/`.

## Dúvidas

Abra uma issue com o modelo **Decisão** quando a dúvida for uma escolha da equipe, ou comente na issue em que você está trabalhando.
