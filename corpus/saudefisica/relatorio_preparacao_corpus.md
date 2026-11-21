# Relatório Técnico de Preparação do Corpus Documental — Saúde Física

## 1. Sumário Executivo

Este relatório documenta as atividades de engenharia e curadoria documental executadas para a construção e organização do corpus de **Saúde Física (CULTIVA Move)**. 

Todas as atividades respeitaram a restrição estrita de isolamento: **o RAG existente de Nutrição permaneceu totalmente intocado**, nenhum modelo ou banco vetorial foi acionado, e nenhuma funcionalidade de recuperação semântica foi implementada.

---

## 2. Estatísticas da Preparação

- **Documentos pré-existentes no repositório:** 11 fontes catalogadas (8 com originais e derivados já gerados; 3 com status de indisponibilidade prévia registrada).
- **Novas fontes documentais candidatas avaliadas:** 15 fontes (Categorias A, B, C e D).
- **Novos arquivos originais baixados com sucesso:** 12 arquivos (6 PDFs e 6 HTMLs).
- **Novos arquivos Markdown convertidos e estruturados:** 12 documentos (6 a partir de PDF, 6 a partir de HTML).
- **Total final de arquivos Markdown válidos no corpus de Saúde Física:** **20 documentos Markdown estruturados** (8 pré-existentes + 12 novos gerados).
- **Total de relatórios de auditoria gerados:** 20 relatórios JSON em `corpus/saudefisica/relatorios/`.
- **Fontes com acesso inviabilizado tecnicamente:** 7 fontes (analisadas e documentadas no inventário).

---

## 3. Detalhamento das Fontes Preparadas Nesta Etapa

### 3.1 Originais em PDF Convertidos

1. **`who-physical-activity-at-a-glance-2020`**
   - Arquivo original: `11-who-physical-activity-at-a-glance-2020.pdf` (1.486.992 bytes, SHA-256: `37c822c430ccf8c1...`)
   - Páginas físicas: 24
   - Markdown gerado: `11-who-physical-activity-at-a-glance-2020.md`
   - Relatório: `11-who-physical-activity-at-a-glance-2020.json`
   - Observação: Síntese executiva oficial da OMS, complementar à diretriz principal de 104 páginas.

2. **`hhs-physical-activity-scientific-report-2018`**
   - Arquivo original: `12-hhs-physical-activity-scientific-report-2018.pdf` (29.676.586 bytes, SHA-256: `c13c25e34ab607dd...`)
   - Páginas físicas: 779
   - Markdown gerado: `12-hhs-physical-activity-scientific-report-2018.md`
   - Relatório: `12-hhs-physical-activity-scientific-report-2018.json`
   - Observação: Documento científico de referência integral com todas as 779 páginas transcritas e indexadas por página física.

3. **`jospt-patellofemoral-pain-infographic-2019`**
   - Arquivo original: `18-jospt-patellofemoral-pain-cpg-2019.pdf` (523.878 bytes, SHA-256: `5702bbe3f3a8e586...`)
   - Páginas físicas: 1
   - Markdown gerado: `18-jospt-patellofemoral-pain-infographic-2019.md`
   - Relatório: `18-jospt-patellofemoral-pain-infographic-2019.json`
   - Observação: Infográfico oficial de síntese da diretriz clínica da APTA/JOSPT.

4. **`jospt-ankle-ligament-sprains-cpg-2021`**
   - Arquivo original: `19-jospt-ankle-ligament-sprains-cpg-2021.pdf` (1.204.846 bytes, SHA-256: `7aaf19cd4ca5a2fb...`)
   - Páginas físicas: 80
   - Markdown gerado: `19-jospt-ankle-ligament-sprains-cpg-2021.md`
   - Relatório: `19-jospt-ankle-ligament-sprains-cpg-2021.json`
   - Observação: Revisão da diretriz clínica de entorses ligamentares laterais de tornozelo (CPG integral).

5. **`who-rehabilitation-musculoskeletal-annex-2023`**
   - Arquivo original: `20-who-rehabilitation-musculoskeletal-annex-2023.pdf` (3.360.144 bytes, SHA-256: `97569ce2547759a5...`)
   - Páginas físicas: 110
   - Markdown gerado: `20-who-rehabilitation-musculoskeletal-annex-2023.md`
   - Relatório: `20-who-rehabilitation-musculoskeletal-annex-2023.json`
   - Observação: Tabelas completas de evidência (GRADE) do Módulo 2 de Reabilitação da OMS.

6. **`ms-guia-atividade-fisica-gestores-profissionais-2021`**
   - Arquivo original: `21-ms-guia-atividade-fisica-gestores-profissionais-2021.pdf` (2.072.878 bytes, SHA-256: `2fc0e130090b1269...`)
   - Páginas físicas: 20
   - Markdown gerado: `21-ms-guia-atividade-fisica-gestores-profissionais-2021.md`
   - Relatório: `21-ms-guia-atividade-fisica-gestores-profissionais-2021.json`
   - Observação: Guia oficial do Ministério da Saúde para o SUS (recomendações técnicas aos gestores e profissionais da Atenção Primária).

---

### 3.2 Originais em HTML Convertidos

1. **`nhs-physical-activity-adults-19-64`**
   - Arquivo original: `13-nhs-physical-activity-adults-19-64.html` (39.452 bytes, SHA-256: `49b93f8d374b7d1c...`)
   - Markdown gerado: `13-nhs-physical-activity-adults-19-64.md`
   - Relatório: `13-nhs-physical-activity-adults-19-64.json`
   - Seletor utilizado: `main`

2. **`nhs-warm-up-before-exercise`**
   - Arquivo original: `14-nhs-warm-up-before-exercise.html` (41.102 bytes, SHA-256: `78158db4b007d63a...`)
   - Markdown gerado: `14-nhs-warm-up-before-exercise.md`
   - Relatório: `14-nhs-warm-up-before-exercise.json`
   - Seletor utilizado: `main`

3. **`nice-low-back-pain-sciatica-ng59`**
   - Arquivo original: `15-nice-low-back-pain-sciatica-ng59.html` (52.427 bytes, SHA-256: `193f3e60e845dde5...`)
   - Markdown gerado: `15-nice-low-back-pain-sciatica-ng59.md`
   - Relatório: `15-nice-low-back-pain-sciatica-ng59.json`
   - Seletor utilizado: `main` (capítulo de recomendações clínicas)

4. **`cochrane-exercise-chronic-low-back-pain-2021`**
   - Arquivo original: `16-cochrane-exercise-chronic-low-back-pain-2021-pt.html` (77.110 bytes) e original de apoio em inglês `16-cochrane-exercise-chronic-low-back-pain-2021-en.html` (72.748 bytes)
   - Markdown gerado: `16-cochrane-exercise-chronic-low-back-pain-2021.md`
   - Relatório: `16-cochrane-exercise-chronic-low-back-pain-2021.json`
   - Seletor utilizado: `main` (resumo em linguagem clara e sumário de evidências da revisão sistemática)

5. **`nice-osteoarthritis-ng226`**
   - Arquivo original: `17-nice-osteoarthritis-ng226.html` (61.916 bytes, SHA-256: `e34c6fecdddf3ba6...`)
   - Markdown gerado: `17-nice-osteoarthritis-ng226.md`
   - Relatório: `17-nice-osteoarthritis-ng226.json`
   - Seletor utilizado: `main` (recomendações diagnósticas e de exercícios para osteoartrite)

6. **`jospt-patellofemoral-pain-cpg-2019`**
   - Arquivo original: `18-jospt-patellofemoral-pain-cpg-2019.html` (31.643 bytes, SHA-256: `354007b682ed7474...`)
   - Markdown gerado: `18-jospt-patellofemoral-pain-cpg-2019.md`
   - Relatório: `18-jospt-patellofemoral-pain-cpg-2019.json`
   - Seletor utilizado: `main` (apresentação oficial da diretriz clínica da AOPT)

---

## 4. Registro de Fontes Indisponíveis ou com Restrição Técnica

Durante o processo de obtenção das 15 candidatas, 4 fontes apresentaram barreiras técnicas e legais intransponíveis sem violação de diretrizes éticas:

1. **`cdc-adult-physical-activity-overview` (CDC) & `cdc-heat-and-athletes` (CDC):**
   - Os servidores governamentais do CDC utilizam defesa perimetral Akamai Bot Manager (`Reference #18... errors.edgesuite.net`), retornando HTTP 403 Forbidden para requisições automatizadas. Conforme as regras do projeto e as diretrizes éticas de segurança, nenhum mecanismo anti-bot foi contornado.
2. **`world-guidelines-falls-prevention-2022` (Age and Ageing / OUP):**
   - As páginas da Oxford University Press e PMC retornaram HTTP 403 / bloqueio Cloudflare. Não foi possível obter o HTML ou PDF integral por rota pública desprotegida.
3. **`brazilian-physical-activity-recommendations-report-2022` (JPAH / UFRGS Lume):**
   - O repositório digital da UFRGS (`lume.ufrgs.br`) retornou falha interna contínua (HTTP 500 / timeout de leitura de socket). A página do periódico JPAH oferece apenas visualização comercial fechada (sem PDF aberto).

---

## 5. Auditoria de Conformidade e Integridade do Repositório

Foi realizada uma checagem rigorosa de integridade com o Git:
- **Corpus de Nutrição:** Nenhuma linha, arquivo original, markdown, relatório ou JSONL de Trecho de Nutrição foi alterado (`git diff` limpo).
- **Código do RAG e Aplicação:** Nenhum arquivo em `src/`, `tests/` ou configuração de banco vetorial foi tocado.
- **Novos arquivos:** Todos os novos arquivos foram confinados estritamente à pasta `corpus/saudefisica/` (subdiretórios `originais/`, `markdown/`, `relatorios/` e arquivos de governança na raiz).
