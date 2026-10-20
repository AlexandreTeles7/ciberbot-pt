"""Canal e-mail: envio por SMTP (por exemplo Gmail com palavra-passe de aplicação)."""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from ..edicao import Edicao, email_html, texto_simples
from .base import ErroCanal

NOME = "email"


def ativo(cfg: dict, env: dict) -> bool:
    return bool(env.get("SMTP_HOST") and env.get("EMAIL_PARA")
                and (env.get("EMAIL_DE") or env.get("SMTP_USER")))


def construir_mensagem(ed: Edicao, de: str, para: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"🛡️ {ed.titulo} — {ed.data.strftime('%d/%m/%Y')}"
    msg["From"] = de
    msg["To"] = para
    msg.set_content(texto_simples(ed))
    msg.add_alternative(email_html(ed), subtype="html")
    return msg


def enviar(ed: Edicao, cfg: dict, env: dict) -> str:
    host = env["SMTP_HOST"].strip()
    porta = int(env.get("SMTP_PORT") or 587)
    utilizador = env.get("SMTP_USER", "")
    senha = env.get("SMTP_PASSWORD", "")
    de = env.get("EMAIL_DE") or utilizador
    destinatarios = [d.strip() for d in env["EMAIL_PARA"].split(",") if d.strip()]
    contexto = ssl.create_default_context()
    try:
        if porta == 465:
            servidor = smtplib.SMTP_SSL(host, porta, timeout=30, context=contexto)
        else:
            servidor = smtplib.SMTP(host, porta, timeout=30)
        with servidor as s:
            if porta != 465:
                s.starttls(context=contexto)
            if utilizador:
                s.login(utilizador, senha)
            for dest in destinatarios:  # uma mensagem por pessoa: ninguém vê os restantes
                s.send_message(construir_mensagem(ed, de, dest))
    except (smtplib.SMTPException, OSError) as e:
        raise ErroCanal(f"falha no SMTP ({type(e).__name__})") from None
    return f"enviado para {len(destinatarios)} destinatário(s)"
