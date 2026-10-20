"""Utilitários de texto: limpeza de HTML, corte e deteção de idioma."""
from __future__ import annotations

import html
import re

_PT = {
    "de", "que", "não", "para", "com", "uma", "os", "as", "em", "do", "da", "dos",
    "das", "um", "por", "se", "mais", "foi", "são", "ao", "no", "na", "nos", "nas",
    "como", "pelo", "pela", "também", "está", "estão", "sobre",
}
_EN = {
    "the", "and", "of", "to", "is", "with", "in", "for", "that", "on", "are", "was",
    "has", "from", "by", "this", "an", "be", "have", "been", "which", "their", "its",
    "could", "allows", "attackers", "via",
}


def limpar_html(texto: str) -> str:
    """Remove etiquetas HTML, resolve entidades e normaliza espaços."""
    texto = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", texto or "")
    texto = re.sub(r"(?s)<[^>]+>", " ", texto)
    texto = html.unescape(texto)
    return re.sub(r"\s+", " ", texto).strip()


def cortar(texto: str, limite: int) -> str:
    """Corta no último espaço antes do limite e acrescenta reticências."""
    texto = (texto or "").strip()
    if len(texto) <= limite:
        return texto
    base = texto[:limite]
    if " " in base:
        base = base.rsplit(" ", 1)[0]
    return base.rstrip(" ,;:.-") + "…"


def detetar_idioma(texto: str) -> str:
    """Heurística simples: 'pt' se houver mais palavras funcionais portuguesas, senão 'en'."""
    palavras = re.findall(r"[a-zà-úç]+", (texto or "").lower())
    pt = sum(p in _PT for p in palavras)
    en = sum(p in _EN for p in palavras)
    return "pt" if pt > en else "en"


def sem_controlo(texto: str) -> str:
    """Remove caracteres de controlo (mantém quebras de linha e tabulações simples)."""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", texto or "")
