"""Canal Discord: webhook de um canal do servidor."""
from __future__ import annotations

import time

from ..edicao import Edicao, mensagens_discord
from ..rede import ErroRede, enviar_json
from .base import ErroCanal

NOME = "discord"
PREFIXOS = ("https://discord.com/api/webhooks/", "https://discordapp.com/api/webhooks/")


def ativo(cfg: dict, env: dict) -> bool:
    return bool(env.get("DISCORD_WEBHOOK_URL"))


def _enviar_uma(url: str, texto: str) -> None:
    carga = {
        "content": texto,
        "username": "CiberBot PT",
        "flags": 4,  # SUPPRESS_EMBEDS
        "allowed_mentions": {"parse": []},  # o conteúdo vem da internet: nunca mencionar ninguém
    }
    for _ in range(3):
        estado, corpo = enviar_json(url, carga)
        if estado == 429:
            espera = float(corpo.get("retry_after", 2)) if isinstance(corpo, dict) else 2.0
            time.sleep(min(espera, 30))
            continue
        if estado in (200, 204):
            return
        raise ErroCanal(f"Discord respondeu {estado}")
    raise ErroCanal("Discord: demasiados pedidos (429)")


def enviar(ed: Edicao, cfg: dict, env: dict) -> str:
    urls = [u.strip() for u in env["DISCORD_WEBHOOK_URL"].split(",") if u.strip()]
    for u in urls:
        if not u.startswith(PREFIXOS):
            raise ErroCanal("DISCORD_WEBHOOK_URL não parece um webhook do Discord")
    mensagens = mensagens_discord(ed)
    try:
        for u in urls:
            for m in mensagens:
                _enviar_uma(u, m)
                time.sleep(1)
    except ErroRede as e:
        raise ErroCanal(f"Discord inacessível ({e})") from None
    return f"{len(mensagens)} mensagem(ns) para {len(urls)} webhook(s)"
