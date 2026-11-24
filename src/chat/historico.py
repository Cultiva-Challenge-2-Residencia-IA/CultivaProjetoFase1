"""Histórico das Conversas em SQLite local (issue #99).

Uma tabela, uma linha por mensagem. O texto fica sem máscara, porque é a conversa do próprio
Usuário; a máscara de dados pessoais é aplicada no que sai da máquina (LLM e Langfuse, ADR 0003).
Mensagem que o portão de risco detecta é guardada só com as categorias. A Conversa fica guardada
até o Usuário apagar (`apagar_conversa`, `apagar_usuario`).

Posse da Conversa (issue #108): a tabela `conversas` liga cada `conversa_id` ao Usuário que o usou
primeiro. Outro Usuário com o mesmo id é recusado (`reservar_conversa` devolve False), e todas as
leituras e exclusões continuam filtradas pelo `usuario_id`.
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

_ESQUEMA_CONVERSAS = """CREATE TABLE IF NOT EXISTS conversas (
    conversa_id TEXT PRIMARY KEY,
    usuario_id TEXT NOT NULL,
    criada_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)"""

# Bancos criados antes da #108 não têm a tabela de posse: cada Conversa fica com o Usuário da
# primeira mensagem dela.
_PREENCHER_CONVERSAS = """INSERT OR IGNORE INTO conversas (conversa_id, usuario_id)
SELECT m.conversa_id, m.usuario_id FROM mensagens m
WHERE m.id = (SELECT MIN(id) FROM mensagens WHERE conversa_id = m.conversa_id)"""


class HistoricoSQLite:
    def __init__(self, caminho: Path) -> None:
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self._conectar() as conexao:
            conexao.execute(_ESQUEMA)
            conexao.execute(_ESQUEMA_CONVERSAS)
            conexao.execute(_PREENCHER_CONVERSAS)

    @contextmanager
    def _conectar(self):
        """Uma conexão por operação, fechada no fim, com commit (ou rollback em erro)."""
        with closing(sqlite3.connect(self.caminho)) as conexao, conexao:
            yield conexao

    def reservar_conversa(self, usuario_id: str, conversa_id: str) -> bool:
        """Liga a Conversa ao Usuário na primeira vez; True se ela é dele, False se é de outro.

        O INSERT OR IGNORE na chave primária torna a reserva atômica: dois Usuários com o mesmo id
        ao mesmo tempo não ficam os dois como donos.
        """
        with self._conectar() as conexao:
            conexao.execute("INSERT OR IGNORE INTO conversas (conversa_id, usuario_id) VALUES (?, ?)",
                            (conversa_id, usuario_id))
            dono = conexao.execute("SELECT usuario_id FROM conversas WHERE conversa_id = ?",
                                   (conversa_id,)).fetchone()
        return dono is not None and dono[0] == usuario_id

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
        """Apaga as mensagens e a posse da Conversa, só se ela é do Usuário; devolve as mensagens apagadas."""
        with self._conectar() as conexao:
            conexao.execute("DELETE FROM conversas WHERE usuario_id = ? AND conversa_id = ?",
                            (usuario_id, conversa_id))
            return conexao.execute("DELETE FROM mensagens WHERE usuario_id = ? AND conversa_id = ?",
                                   (usuario_id, conversa_id)).rowcount

    def apagar_usuario(self, usuario_id: str) -> int:
        with self._conectar() as conexao:
            conexao.execute("DELETE FROM conversas WHERE usuario_id = ?", (usuario_id,))
            return conexao.execute("DELETE FROM mensagens WHERE usuario_id = ?", (usuario_id,)).rowcount
