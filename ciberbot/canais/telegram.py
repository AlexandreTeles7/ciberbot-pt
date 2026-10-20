"""Canal Telegram: mensagens HTML enviadas por um bot."""
from __future__ import annotations

import re
import time

from ..edicao import Edicao, mensagens_telegram
from ..rede import ErroRede, enviar_json
from .base import ErroCanal

NOME = "telegram"
_TOKEN = re.compile(r"^\d+:[A-Za-z0-9_-]+$")


def ativo(cfg: dict, env: dict) -> bool:
    return bool(env.get("TELEGRAM_BOT_TOKEN") and env.get("TELEGRAM_CHAT_ID"))


def _enviar_uma(url: str, carga: dict) -> None:
    for _ in range(3):
        estado, corpo = enviar_json(url, carga)
        if estado == 429:  # limite de pedidos: respeitar o tempo indicado
            espera = 3.0
            if isinstance(corpo, dict):
                espera = float((corpo.get("parameters") or {}).get("retry_after", 3))
            time.sleep(min(espera, 30))
            continue
        if estado == 200 and isinstance(corpo, dict) and corpo.get("ok"):
            return
        detalhe = corpo.get("description", "") if isinstance(corpo, dict) else ""
        raise ErroCanal(f"Telegram respondeu {estado}. {detalhe}".strip())
    raise ErroCanal("Telegram: demasiados pedidos (429)")


def enviar(ed: Edicao, cfg: dict, env: dict) -> str:
    token = env["TELEGRAM_BOT_TOKEN"].strip()
    if not _TOKEN.match(token):
        raise ErroCanal("TELEGRAM_BOT_TOKEN com formato inválido")
    chats = [c.strip() for c in env["TELEGRAM_CHAT_ID"].split(",") if c.strip()]
    mensagens = mensagens_telegram(ed)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        for chat in chats:
            for m in mensagens:
                _enviar_uma(url, {
                    "chat_id": chat,
                    "text": m,
                    "parse_mode": "HTML",
                    "link_preview_options": {"is_disabled": True},
                })
                time.sleep(0.4)
    except ErroRede as e:
        raise ErroCanal(f"Telegram inacessível ({e})") from None
    return f"{len(mensagens)} mensagem(ns) para {len(chats)} conversa(s)"
