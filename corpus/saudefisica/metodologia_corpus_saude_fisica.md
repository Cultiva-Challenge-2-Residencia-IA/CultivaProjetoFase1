# Metodologia de Curadoria e Preparação do Corpus — Saúde Física (CULTIVA Move)

## 1. Objetivo do Corpus Documental

O corpus de **Saúde Física** tem como finalidade fornecer uma base bibliográfica e normativa sólida, com evidências científicas de alta qualidade e diretrizes governamentais/internacionais sobre atividade física, prescrição de exercícios, prevenção de lesões, manejo conservador de dores comuns (lombar, patelofemoral, manguito rotador, entorse de tornozelo) e reabilitação musculoesquelética para adultos saudáveis e populações clínicas especiais.

O objetivo desta etapa é construir e organizar um corpus de arquivos Markdown estruturados e auditáveis, **sem ativar ou integrar funcionalidades do RAG**, servindo de alicerce confiável para futuras expansões do projeto CULTIVA.

---

## 2. Critérios de Seleção e Elegibilidade Documental

As fontes foram selecionadas de acordo com os seguintes critérios:

1. **Relevância Temática:**
   - **Categoria A (Atividade física e saúde geral):** Recomendações globais e diretrizes populacionais (OMS, HHS, NHS).
   - **Categoria B (Exercícios e segurança):** Diretrizes de prescrição, aquecimento, fatores de segurança e monitoramento de carga esportiva (IOC, NHS).
   - **Categoria C (Dores, lesões e reabilitação):** Diretrizes de prática clínica (CPGs) e revisões sistemáticas de alta relevância (NICE, JOSPT/APTA, Cochrane, OMS).
   - **Categoria D (Fundamentação brasileira):** Diretrizes nacionais emitidas pelo Ministério da Saúde para assegurar contexto cultural, epidemiológico e do SUS.
2. **Autoridade Científica e Institucional:** Prioridade a órgãos de saúde pública (OMS, Ministério da Saúde do Brasil, NHS), sociedades profissionais reconhecidas (JOSPT, APTA, IOC) e redes de evidência sistemática (Cochrane, NICE).
3. **Disponibilidade e Legalidade:** Obtenção estrita de originais publicados sob licenças abertas (Creative Commons, Open Government Licence, Domínio Público) ou disponibilizados publicamente para consulta sem quebra de mecanismos de proteção técnica ou controle de acesso.

---

## 3. Procedimento de Obtenção e Conversão Técnica

O processamento seguiu rigorosamente os padrões já validados no pipeline de engenharia documental do repositório:

### 3.1 Tratamento de Arquivos PDF
- **Extração por Página Física:** Cada página do PDF é preservada como um bloco independente, demarcado por tags estruturadas (`<a id="pagina-pdf-NNN"></a>`, `<!-- PDF_PAGE: N -->`, `## Página PDF N`) e acompanhada de link direto para a página correspondente do PDF original (`.pdf#page=N`).
- **Layout Nativo e Sem Imagens PNG:** O conteúdo é extraído com o PyMuPDF Layout, mantendo texto nativo, formatação de títulos, listas e tabelas. Nenhuma imagem gráfica é extraída em arquivos soltos para evitar degradação de espaço e referências espúrias.
- **Auditoria Lexical:** Cada página passa por verificação de cobertura lexical (comparação entre o vocabulário bruto extraído e o Markdown final gerado), sinalizando páginas com pouco texto ou com potencial perda para revisão.
- **Relatório JSON Auditável:** Para cada PDF convertido, é gerado um relatório estruturado em `corpus/saudefisica/relatorios/<arquivo>.json`, registrando o SHA-256 do original, SHA-256 do Markdown, SHA-256 do script de extração, total de páginas físicas e anotações por página.

### 3.2 Tratamento de Arquivos HTML
- **Limpeza Semântica:** Apenas o container central de conteúdo (`main`, `article` ou seletor dedicado) é processado, eliminando tags de navegação (`nav`), cabeçalhos repetitivos (`header`), rodapés (`footer`), scripts, estilos e widgets sociais.
- **Conversão via MarkdownConverter Customizado:** Converte a árvore DOM em Markdown limpo (estilo ATX para cabeçalhos e marcadores `-`), registrando textos alternativos de figuras sem salvar arquivos de imagem binários.
- **Relatório de Extração:** Armazenamento do SHA-256 de origem, seletores aplicados, tabelas e figuras identificadas.

---

## 4. Tratamento de Documentos com Acesso Parcial ou Restrito

Em estrito cumprimento das diretrizes éticas e de conformidade legal:
- **Resumos x Texto Integral:** Documentos como a revisão Cochrane de dor lombar crônica (`cochrane-exercise-chronic-low-back-pain-2021`) e a página da diretriz de dor patelofemoral da APTA (`jospt-patellofemoral-pain-cpg-2019`) foram registrados explicitamente como **resumo ou conteúdo parcial**, evitando inferências de texto integral inexistente.
- **Barreiras de Acesso (Paywalls e Bot Gates):** Portais protegidos por Cloudflare Turnstile, Akamai Bot Manager ou controle de assinantes pagos (ex.: CDC, PMC, Oxford University Press) **não foram contornados**. Essas fontes foram catalogadas como `original_indisponivel` no inventário, mantendo o repositório auditável e livre de violações de segurança.
- **Erros de Servidores Externos:** Fontes cujo servidor institucional apresentou indisponibilidade (HTTP 500 no repositório Lume da UFRGS) tiveram o erro documentado tecnicamente para posterior tentativa quando o servidor for restabelecido.

---

## 5. Critérios de Validação Documental

Cada arquivo Markdown gerado foi validado contra os seguintes critérios:
1. Correspondência exata de metadados no frontmatter YAML (`source_id`, `title`, `source`, `license`, `source_sha256`).
2. Presença de aviso de responsabilidade científica institucional (isenção de prescrição do CULTIVA e aviso de revisão pendente).
3. Preservação de valores numéricos, minutos de atividade física, percentuais e dosagens de carga.
4. Ausência de texto inventado ou tradução automática não autorizada pelo protocolo.
5. Links relativos íntegros apontando para `../originais/` e `../relatorios/`.

---

## 6. Diretrizes para Utilização Futura em Sistemas RAG

Quando o time de engenharia implementar o sistema RAG para o CULTIVA Move:
- **Carregador de Corpus:** Desenvolver um carregador específico para `corpus/saudefisica/` (ou parametrizar o leitor de Trechos por domínio, como já prototipado no branch de desenvolvimento de Saúde Física).
- **Estratégia de Chunking:** Respeitar as fronteiras das páginas físicas do PDF e níveis máximos de seção para evitar contaminação de contexto entre diferentes faixas etárias (ex.: recomendações de idosos misturadas com as de crianças).
- **Guardrails e Portão de Risco:** Implementar guardrails de segurança específicos para exercício físico (identificação de sinais de alerta cardiovascular, bandeiras vermelhas musculoesqueléticas e restrição de prescrição médica/fisioterapêutica individualizada).
- **Aprovação de Fontes:** Manter as fontes em `approval_status: pendente` até validação formal pelo profissional de educação física e fisioterapia responsável técnico pelo produto.
