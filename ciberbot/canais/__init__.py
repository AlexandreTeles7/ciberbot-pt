"""Canais de publicação. Cada módulo expõe ativo(cfg, env) e enviar(edicao, cfg, env)."""
from . import correio, discord, telegram, web
from .base import ErroCanal

CANAIS = {
    web.NOME: web,
    telegram.NOME: telegram,
    correio.NOME: correio,
    discord.NOME: discord,
}


def ativos(cfg: dict, env: dict, selecao: list[str] | None = None) -> list[str]:
    """Nomes dos canais configurados (e, opcionalmente, restritos a 'selecao')."""
    nomes = [n for n, m in CANAIS.items() if m.ativo(cfg, env)]
    if selecao:
        nomes = [n for n in nomes if n in selecao]
    return nomes


__all__ = ["CANAIS", "ErroCanal", "ativos"]
