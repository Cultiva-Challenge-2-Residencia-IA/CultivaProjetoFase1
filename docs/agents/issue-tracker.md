# Rastreador de issues: GitHub

Issues e specs deste repositório ficam no GitHub Issues de `Cultiva-Challenge-2-Residencia-IA/CultivaProjetoFase1`. Use o `gh` em todas as operações. O `gh` descobre o repositório pelo `git remote`; se houver mais de um remoto (há forks configurados em alguns clones), passe `--repo Cultiva-Challenge-2-Residencia-IA/CultivaProjetoFase1`.

## Regras do projeto

- **Modelos de issue:** escreva o corpo seguindo o modelo de `.github/ISSUE_TEMPLATE/` que se aplica: `1-tarefa.yml` (tarefa e spec), `2-bug.yml`, `3-fonte-corpus.yml` (fonte para o corpus) ou `4-decisao.yml` (decisão da equipe). Os modelos são formulários: reproduza as seções deles no corpo em Markdown.
- **Idioma e estilo:** português do Brasil, sem emojis, como o restante do repositório.
- **Citação:** cite issues e PRs sempre com o título ou uma descrição curta, nunca só pelo número.
- **Sem rótulos de triagem:** o repositório não usa `needs-triage`, `needs-info`, `ready-for-agent` nem `ready-for-human`. Quando uma skill pedir um rótulo de triagem, não crie nem aplique; use só os rótulos que já existem (`enhancement`, `bug`, `documentation`, `question`, `wontfix`, `rag`, `corpus`, `avaliacao`, `seguranca`, `decisao`, `infra`, `prioridade:alta`) quando fizerem sentido.
- **Requisitos:** RN, RF-A, RF-IA e RNF vivem no repositório Documentacao-Cultiva. Uma issue que muda requisito diz isso no corpo e aponta o que precisa ser atualizado lá.

## Operações

- **Criar uma issue:** `gh issue create --title "..." --body-file <arquivo>` (prefira arquivo ou heredoc para corpos com várias linhas).
- **Ler uma issue:** `gh issue view <número> --json number,title,body,labels,comments`.
- **Listar issues:** `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`, com filtros de `--label` e `--state`.
- **Sub-issue de uma issue mãe:** `gh issue create --parent <mãe> ...`, ou `gh issue edit <mãe> --add-sub-issue <filha>` depois. Sem sub-issues, ponha `Parte de #<mãe>` no topo do corpo da filha.
- **Comentar:** `gh issue comment <número> --body "..."`.
- **Rótulos:** `gh issue edit <número> --add-label "..."` / `--remove-label "..."` (só os existentes, ver acima).
- **Fechar:** `gh issue close <número> --comment "..."`.

## Pull requests como entrada de pedidos

**PRs como entrada de pedidos: não.** _(Mude para `sim` se o repositório passar a tratar PRs externos como pedidos; o `/triage` lê esta linha.)_

O GitHub usa a mesma numeração para issues e PRs: um `#42` solto pode ser qualquer um dos dois. Resolva com `gh pr view 42` e, se não existir, `gh issue view 42`.

## Quando uma skill disser "publicar no rastreador"

Crie uma issue no GitHub, seguindo as regras do projeto acima.

## Quando uma skill disser "buscar o ticket"

Leia como em **Ler uma issue**.

## Operações da wayfinder

Usadas pelo `/wayfinder`. O **mapa** é uma issue com issues **filhas** como tickets. Os rótulos `wayfinder:*` são os únicos que a wayfinder cria; crie-os só quando um mapa for de fato aberto.

- **Mapa:** uma issue com o rótulo `wayfinder:map`, com o corpo de Notas, Decisões até agora e Ainda não especificado. `gh issue create --label wayfinder:map`.
- **Ticket filho:** issue ligada ao mapa como sub-issue (ver **Sub-issue de uma issue mãe**). Rótulo `wayfinder:<tipo>` (`research`, `prototype`, `grilling`, `task`). Ao ser assumido, o ticket recebe como responsável quem conduz o mapa.
- **Bloqueio:** dependências nativas do GitHub. Adicione com `gh api --method POST repos/Cultiva-Challenge-2-Residencia-IA/CultivaProjetoFase1/issues/<filha>/dependencies/blocked_by -F issue_id=<id-do-bloqueador>`, em que `<id-do-bloqueador>` é o **id de banco** da issue (`gh api repos/Cultiva-Challenge-2-Residencia-IA/CultivaProjetoFase1/issues/<n> --jq .id`), não o número. Sem dependências disponíveis, use uma linha `Bloqueada por: #<n>` no topo da filha. Um ticket está desbloqueado quando todos os bloqueadores estão fechados.
- **Fronteira:** as filhas abertas do mapa, sem bloqueador aberto e sem responsável; a primeira na ordem do mapa vem antes.
- **Assumir:** `gh issue edit <n> --add-assignee @me`, a primeira escrita da sessão.
- **Resolver:** `gh issue comment <n> --body "<resposta>"`, depois `gh issue close <n>`, depois uma linha com resumo e link nas Decisões até agora do mapa.
