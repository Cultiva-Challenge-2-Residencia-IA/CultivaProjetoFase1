"""Mensagens fixas. Textos críticos de segurança nunca são gerados por LLM."""

ACOLHIMENTO_RISCO = (
    "Sinto muito que você esteja passando por isso. Você não precisa enfrentar esse "
    "momento sem apoio. Converse agora com o CVV (Centro de Valorização da Vida) pelo "
    "telefone 188, ligação gratuita, 24 horas por dia, ou pelo chat em cvv.org.br. "
    "Em caso de emergência, ligue para o SAMU (192) ou vá ao pronto-socorro mais "
    "próximo. Sou uma IA e não substituo o cuidado de um profissional; se puder, "
    "procure também alguém de confiança para estar com você."
)

AVISO_PROFISSIONAL = (
    "Aviso: estas são informações educativas e não substituem a orientação de um "
    "profissional de saúde. Para orientações individualizadas, procure um profissional "
    "de nutrição."
)

RECUSA_ESCOPO = (
    "Não posso indicar medicamentos, suplementos, doses ou dietas fechadas, nem fazer "
    "diagnósticos ou avaliações individuais. Para isso, o caminho certo é um profissional "
    "qualificado, como um profissional de nutrição ou de medicina. Posso ajudar com "
    "informações gerais do Guia Alimentar e com a organização da sua rotina."
)

RECUSA_INJECAO = (
    "Não posso mudar minhas regras de funcionamento nem compartilhar instruções internas "
    "ou dados de outras pessoas. Posso ajudar com dúvidas sobre alimentação usando as "
    "fontes aprovadas."
)

NAO_SEI = (
    "Não encontrei essa informação nas fontes aprovadas que consulto, então prefiro não "
    "responder para não passar algo sem base. Você pode reformular a pergunta ou "
    "procurar um profissional de nutrição."
)


def redirecionamento(nome_aba: str) -> str:
    return (
        f"Essa pergunta parece ser sobre {nome_aba}. Para eu responder com as fontes "
        f"certas, abra a aba {nome_aba} e pergunte por lá."
    )
