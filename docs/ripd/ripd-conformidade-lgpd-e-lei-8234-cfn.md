# RIPD & Conformidade Ético-Legal (LGPD e Lei Federal nº 8.234/1991 - CFN)

## 1. Conformidade com a Lei Federal nº 8.234/1991 (Conselho Federal de Nutricionistas)
Nos termos do **Art. 3º, inciso VIII da Lei Federal nº 8.234/1991**, a prescrição dietética é atividade **privativa do nutricionista**.

Para garantir conformidade estrita:
1. **Input Guardrail & PICO Reframing (`src/guardrails/prescricao/`):** Toda solicitação de cardápio personalizado, cálculo calórico individual, diagnóstico por exames laboratoriais ou posologia individual de suplementos é interceptada antes do LLM, recebe o aviso legal obrigatório e é reenquadrada para uma consulta científica populacional.
2. **Output Tone Sanitizer (`src/guardrails/tom/`):** Toda resposta gerada pelo LLM passa por auditoria de expressões regulares que remove verbos imperativos/prescritivos (`"você deve comer"`, `"prescrevo"`, `"tome X cápsulas"`).

## 2. Proteção de Dados Sensíveis de Saúde (LGPD - Lei nº 13.709/2018, Art. 11)
* **Minimização de Dados:** O consultor opera de forma *stateless* (sem armazenamento de prontuários, nomes, CPF ou histórico clínico identificável).
* **Segurança de Credenciais:** Chaves de API (`GROQ_API_KEY`) são lidas exclusivamente via variáveis de ambiente (`.env`), bloqueadas no controle de versão via `.gitignore`.
