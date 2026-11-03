"""FastAPI: saúde do serviço e chat da Aba Nutrição.

Sem autenticação nesta fase: usa o Perfil e os Registros de exemplo em memória.
"""

from fastapi import FastAPI
from pydantic import BaseModel, Field

from config import carregar_configuracao
from dominio.exemplos import PERFIL_EXEMPLO, REGISTROS_EXEMPLO
from modelo import ModeloDeLinguagem, criar_modelo
from orquestracao import Cultiva


class PedidoChat(BaseModel):
    mensagem: str = Field(min_length=1, max_length=2000)


class Fonte(BaseModel):
    id: str
    fonte: str
    pagina_pdf: int


class RespostaChat(BaseModel):
    resposta: str
    fontes: list[Fonte]
    sinais: dict


def criar_app(modelo: ModeloDeLinguagem | None = None) -> FastAPI:
    if modelo is None:
        # Falha ao iniciar se o .env ou alguma variável faltar.
        modelo = criar_modelo(carregar_configuracao())
    cultiva = Cultiva(modelo)
    app = FastAPI(title="CULTIVA", version="0.1.0")

    @app.get("/saude")
    def saude() -> dict:
        return {"status": "ok", "modelo": cultiva.modelo.nome}

    @app.post("/abas/nutricao/chat", response_model=RespostaChat)
    def chat_nutricao(pedido: PedidoChat) -> RespostaChat:
        r = cultiva.responder(pedido.mensagem, PERFIL_EXEMPLO, REGISTROS_EXEMPLO)
        return RespostaChat(resposta=r.texto, fontes=r.fontes, sinais=r.sinais)

    return app
