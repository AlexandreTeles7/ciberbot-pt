"""Modelos de dados partilhados por todos os módulos."""
from __future__ import annotations

import re
import urllib.parse
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime

CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE)

ETQ_EXPLORADA = "Explorada ativamente"
ETQ_RANSOMWARE = "Usada em ransomware"
ETQ_NA_KEV = "Na lista KEV da CISA"


def url_segura(url: str) -> str:
    """Devolve o URL apenas se for http(s). Bloqueia 'javascript:' e afins."""
    url = (url or "").strip()
    try:
        p = urllib.parse.urlparse(url)
    except ValueError:
        return ""
    return url if p.scheme in ("http", "https") and p.netloc else ""


@dataclass
class Item:
    id: str
    titulo: str
    resumo: str
    url: str
    fonte: str
    idioma: str  # "pt" ou "en"
    categoria: str  # portugal | exploradas | criticas | noticias (ou outra, definida na config)
    publicado: datetime  # sempre com fuso (UTC)
    pontuacao: float = 0.0
    cves: list[str] = field(default_factory=list)
    etiquetas: list[str] = field(default_factory=list)
    titulo_pt: str = ""
    resumo_pt: str = ""
    traduzido: bool = False

    @property
    def titulo_final(self) -> str:
        return self.titulo_pt or self.titulo

    @property
    def resumo_final(self) -> str:
        return self.resumo_pt or self.resumo

    @property
    def em_ingles(self) -> bool:
        """True se o texto apresentado ainda está em inglês (sem tradução)."""
        return self.idioma == "en" and not self.traduzido

    def para_dict(self) -> dict:
        d = asdict(self)
        d["publicado"] = self.publicado.isoformat()
        return d

    @classmethod
    def de_dict(cls, d: dict) -> "Item":
        validos = {f.name for f in fields(cls)}
        d = {k: v for k, v in d.items() if k in validos}
        d["publicado"] = datetime.fromisoformat(d["publicado"])
        return cls(**d)
