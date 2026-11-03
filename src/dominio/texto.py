import re
import unicodedata


def normalizar(texto: str) -> str:
    """Minúsculas, sem acentos e com espaços simples, para comparar texto por regras."""
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()
