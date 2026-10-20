"""Acesso HTTP com a biblioteca padrão (sem dependências externas)."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "CiberBotPT/1.0 (agregador de cibersegurança; leitura de feeds públicos)"


class ErroRede(Exception):
    """Falha de rede. A mensagem nunca inclui o URL completo (pode conter tokens)."""


def _validar(url: str) -> urllib.parse.ParseResult:
    p = urllib.parse.urlparse(url)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise ErroRede("URL inválido (só http/https)")
    return p


def obter(url: str, cabecalhos: dict | None = None, timeout: int = 25,
          tentativas: int = 3, max_bytes: int = 20_000_000) -> bytes:
    """GET com repetição simples em erros temporários."""
    p = _validar(url)
    ultimo = "erro desconhecido"
    for n in range(tentativas):
        pedido = urllib.request.Request(
            url, headers={"User-Agent": UA, "Accept": "*/*", **(cabecalhos or {})}
        )
        try:
            with urllib.request.urlopen(pedido, timeout=timeout) as r:
                dados = r.read(max_bytes + 1)
            if len(dados) > max_bytes:
                raise ErroRede(f"{p.netloc}: resposta demasiado grande")
            return dados
        except urllib.error.HTTPError as e:
            ultimo = f"HTTP {e.code}"
            if e.code < 500 and e.code != 429:
                break  # erro definitivo (404, 403...): não vale a pena repetir
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            ultimo = type(e).__name__
        if n < tentativas - 1:
            time.sleep(1.5 * (n + 1))
    raise ErroRede(f"{p.netloc}: {ultimo}")


def enviar_json(url: str, carga: dict, cabecalhos: dict | None = None,
                timeout: int = 30) -> tuple[int, object]:
    """POST JSON. Devolve (código HTTP, corpo interpretado). Não levanta erro em 4xx/5xx."""
    p = _validar(url)
    corpo = json.dumps(carga).encode("utf-8")
    cab = {"User-Agent": UA, "Content-Type": "application/json", **(cabecalhos or {})}
    pedido = urllib.request.Request(url, data=corpo, headers=cab, method="POST")
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as r:
            estado, bruto = r.status, r.read(5_000_000)
    except urllib.error.HTTPError as e:
        estado, bruto = e.code, e.read(5_000_000)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ErroRede(f"{p.netloc}: {type(e).__name__}") from None
    texto = bruto.decode("utf-8", "replace")
    try:
        return estado, json.loads(texto) if texto.strip() else None
    except ValueError:
        return estado, texto[:500]
