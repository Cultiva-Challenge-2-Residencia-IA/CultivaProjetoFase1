"""Histórico das Conversas em SQLite local (issue #99).

Uma tabela, uma linha por mensagem. O texto fica sem máscara, porque é a conversa do próprio
Usuário; a máscara de dados pessoais é aplicada no que sai da máquina (LLM e Langfuse, ADR 0003).
Mensagem que o portão de risco detecta é guardada só com as categorias. A Conversa fica guardada
até o Usuário apagar (`apagar_conversa`, `apagar_usuario`).
"""

from contextlib import closing, contextmanager
from pathlib import Path
import sqlite3
from typing import List, Optional, Sequence

from src.orquestrador.reescrita import Mensagem

_ESQUEMA = """CREATE TABLE IF NOT EXISTS mensagens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id TEXT NOT NULL,
    conversa_id TEXT NOT NULL,
    chat TEXT NOT NULL,
    papel TEXT NOT NULL,
    areas TEXT NOT NULL DEFAULT '',
    texto TEXT NOT NULL,
    criada_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)"""


class HistoricoSQLite:
    def __init__(self, caminho: Path) -> None:
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self._conectar() as conexao:
            conexao.execute(_ESQUEMA)

    @contextmanager
    def _conectar(self):
        """Uma conexão por operação, fechada no fim, com commit (ou rollback em erro)."""
        with closing(sqlite3.connect(self.caminho)) as conexao, conexao:
            yield conexao

    def adicionar(self, usuario_id: str, conversa_id: str, chat: str, papel: str, texto: str,
                  areas: Sequence[str] = ()) -> None:
        with self._conectar() as conexao:
            conexao.execute(
                "INSERT INTO mensagens (usuario_id, conversa_id, chat, papel, areas, texto) VALUES (?, ?, ?, ?, ?, ?)",
                (usuario_id, conversa_id, chat, papel, ",".join(areas), texto),
            )

    @staticmethod
    def _mensagens(linhas: List[tuple]) -> List[Mensagem]:
        mensagens = []
        for papel, areas, texto in linhas:
            lista = [a for a in areas.split(",") if a]
            mensagens.append(Mensagem(papel=papel, texto=texto, area=lista[0] if len(lista) == 1 else None,
                                      areas=lista))
        return mensagens

    def recentes(self, usuario_id: str, conversa_id: str, limite: int) -> List[Mensagem]:
        """As últimas `limite` mensagens da Conversa, da mais antiga para a mais nova."""
        with self._conectar() as conexao:
            linhas = conexao.execute(
                "SELECT papel, areas, texto FROM mensagens WHERE usuario_id = ? AND conversa_id = ? "
                "ORDER BY id DESC LIMIT ?", (usuario_id, conversa_id, limite)).fetchall()
        return self._mensagens(list(reversed(linhas)))

    def recentes_de_chats(self, usuario_id: str, chats: Sequence[str], limite_por_chat: int,
                          excluir_conversa: Optional[str] = None) -> List[Mensagem]:
        """Últimas mensagens dos chats indicados do mesmo Usuário (o Chat geral lê os Chats de área)."""
        mensagens: List[Mensagem] = []
        with self._conectar() as conexao:
            for chat in chats:
                linhas = conexao.execute(
                    "SELECT papel, areas, texto FROM mensagens WHERE usuario_id = ? AND chat = ? "
                    "AND conversa_id != ? ORDER BY id DESC LIMIT ?",
                    (usuario_id, chat, excluir_conversa or "", limite_por_chat)).fetchall()
                mensagens.extend(self._mensagens(list(reversed(linhas))))
        return mensagens

    def apagar_conversa(self, usuario_id: str, conversa_id: str) -> int:
        with self._conectar() as conexao:
            return conexao.execute("DELETE FROM mensagens WHERE usuario_id = ? AND conversa_id = ?",
                                   (usuario_id, conversa_id)).rowcount

    def apagar_usuario(self, usuario_id: str) -> int:
        with self._conectar() as conexao:
            return conexao.execute("DELETE FROM mensagens WHERE usuario_id = ?", (usuario_id,)).rowcount
