"""Autenticação dos endpoints de chat e de exclusão do Histórico (issue #108).

Ainda não existe App nem provedor de identidade. Este módulo confere o token que o App emitiria
depois de autenticar o Usuário: um token assinado com HMAC-SHA256 (biblioteca padrão, sem dependência
nova), no formato

    v1.<payload em base64url>.<assinatura em base64url>

O payload é um JSON com `sub` (o id do Usuário), `exp` (expiração, em segundos desde a época Unix) e
`iat` (emissão). A assinatura cobre `v1.<payload>`, com o segredo de `CULTIVA_AUTH_SEGREDO`, e é
comparada em tempo constante (`hmac.compare_digest`).

Comportamento conforme o ambiente (lido a cada chamada, para valer o `.env` e os testes):

* `CULTIVA_AUTH_SEGREDO` definido (pelo menos 32 caracteres): todo pedido precisa de token válido;
* sem segredo e `CULTIVA_AUTH_DESLIGADA=true`: modo de desenvolvimento, sem autenticação, com o
  `usuario_id` vindo do cliente como antes (só uso local e dados sintéticos);
* sem segredo e sem a flag: os endpoints recusam (503), para que esquecer a configuração não deixe a
  API aberta.

O token e o segredo nunca vão para log, Langfuse ou mensagem de erro.

Token de teste local:

    uv run python -m src.chat.autenticacao gerar-segredo
    CULTIVA_AUTH_SEGREDO=... uv run python -m src.chat.autenticacao emitir --usuario u1
"""

import argparse
import base64
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Optional

from src.config import AUTH_VALIDADE_PADRAO_S  # importar src.config também carrega o .env

VERSAO = "v1"
TAMANHO_MINIMO_DO_SEGREDO = 32
TAMANHO_MAXIMO_DO_TOKEN = 4096
TAMANHO_MAXIMO_DO_USUARIO = 200
_VERDADEIRO = {"1", "true", "sim", "yes"}


class TokenInvalido(Exception):
    """Token ausente, malformado, com assinatura errada ou expirado (a API responde 401)."""


class AutenticacaoNaoConfigurada(Exception):
    """Sem segredo e sem o modo de desenvolvimento explícito (a API responde 503)."""


@dataclass(frozen=True)
class ConfiguracaoDeAutenticacao:
    segredo: Optional[bytes]
    desligada: bool

    @property
    def modo(self) -> str:
        if self.segredo is not None:
            return "token"
        return "desligada" if self.desligada else "nao_configurada"


def configuracao_do_ambiente() -> ConfiguracaoDeAutenticacao:
    """Lê `CULTIVA_AUTH_SEGREDO` e `CULTIVA_AUTH_DESLIGADA`. Com segredo, a flag não desliga nada."""
    segredo = os.getenv("CULTIVA_AUTH_SEGREDO", "").strip()
    if segredo and len(segredo) < TAMANHO_MINIMO_DO_SEGREDO:
        raise AutenticacaoNaoConfigurada(
            f"CULTIVA_AUTH_SEGREDO precisa ter pelo menos {TAMANHO_MINIMO_DO_SEGREDO} caracteres.")
    desligada = os.getenv("CULTIVA_AUTH_DESLIGADA", "false").strip().lower() in _VERDADEIRO
    return ConfiguracaoDeAutenticacao(segredo=segredo.encode("utf-8") if segredo else None, desligada=desligada)


def _b64(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode("ascii")


def _de_b64(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def _assinatura(segredo: bytes, conteudo: str) -> str:
    return _b64(hmac.new(segredo, conteudo.encode("ascii"), hashlib.sha256).digest())


def emitir_token(usuario_id: str, segredo: bytes, validade_s: int = AUTH_VALIDADE_PADRAO_S,
                 agora: Optional[float] = None) -> str:
    """Emite um token para `usuario_id`. No produto, quem emite é o App; aqui serve a testes e à demo."""
    if not usuario_id or len(usuario_id) > TAMANHO_MAXIMO_DO_USUARIO:
        raise ValueError("usuario_id vazio ou longo demais.")
    if validade_s <= 0:
        raise ValueError("A validade precisa ser positiva.")
    emitido = int(agora if agora is not None else time.time())
    payload = _b64(json.dumps({"sub": usuario_id, "iat": emitido, "exp": emitido + validade_s},
                              separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    conteudo = f"{VERSAO}.{payload}"
    return f"{conteudo}.{_assinatura(segredo, conteudo)}"


def verificar_token(token: str, segredo: bytes, agora: Optional[float] = None) -> str:
    """Devolve o `sub` (id do Usuário) de um token válido; senão, `TokenInvalido` sem detalhar o motivo."""
    if not token or len(token) > TAMANHO_MAXIMO_DO_TOKEN:
        raise TokenInvalido("Token inválido.")
    partes = token.split(".")
    if len(partes) != 3 or partes[0] != VERSAO:
        raise TokenInvalido("Token inválido.")
    conteudo = f"{partes[0]}.{partes[1]}"
    try:
        esperada = _assinatura(segredo, conteudo)
    except UnicodeEncodeError as erro:
        raise TokenInvalido("Token inválido.") from erro
    # A assinatura é conferida antes de qualquer leitura do payload, em tempo constante.
    if not hmac.compare_digest(esperada.encode("ascii"), partes[2].encode("utf-8", "replace")):
        raise TokenInvalido("Token inválido.")
    try:
        dados = json.loads(_de_b64(partes[1]))
    except ValueError as erro:
        raise TokenInvalido("Token inválido.") from erro
    if not isinstance(dados, dict):
        raise TokenInvalido("Token inválido.")
    usuario_id, expira = dados.get("sub"), dados.get("exp")
    if not isinstance(usuario_id, str) or not usuario_id or len(usuario_id) > TAMANHO_MAXIMO_DO_USUARIO:
        raise TokenInvalido("Token inválido.")
    if isinstance(expira, bool) or not isinstance(expira, int):
        raise TokenInvalido("Token inválido.")
    if expira <= (agora if agora is not None else time.time()):
        raise TokenInvalido("Token expirado.")
    return usuario_id


def _main() -> None:
    parser = argparse.ArgumentParser(description="Token de teste local dos endpoints de chat (issue #108).")
    comandos = parser.add_subparsers(dest="comando", required=True)
    emitir = comandos.add_parser("emitir", help="Emite um token com o segredo de CULTIVA_AUTH_SEGREDO")
    emitir.add_argument("--usuario", required=True, help="id do Usuário (use só ids sintéticos)")
    emitir.add_argument("--validade", type=int, default=AUTH_VALIDADE_PADRAO_S, help="segundos até expirar")
    comandos.add_parser("gerar-segredo", help="Gera um segredo aleatório para o .env local")
    args = parser.parse_args()
    if args.comando == "gerar-segredo":
        print(secrets.token_urlsafe(48))
        return
    configuracao = configuracao_do_ambiente()
    if configuracao.segredo is None:
        parser.error("Defina CULTIVA_AUTH_SEGREDO (gere um com o comando gerar-segredo).")
    print(emitir_token(args.usuario, configuracao.segredo, args.validade))


if __name__ == "__main__":
    _main()
