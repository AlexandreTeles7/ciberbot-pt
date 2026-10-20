"""Recolha e interpretação das fontes: RSS/Atom, CISA KEV e NVD."""
from __future__ import annotations

import hashlib
import json
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Callable

from .modelos import CVE_RE, ETQ_EXPLORADA, ETQ_RANSOMWARE, Item
from .rede import ErroRede, obter
from .texto import cortar, detetar_idioma, limpar_html


class ErroFonte(Exception):
    """Conteúdo de uma fonte que não foi possível interpretar."""


def _id(*partes: str) -> str:
    return hashlib.sha1("|".join(partes).encode("utf-8")).hexdigest()[:16]


def _cves(*textos: str) -> list[str]:
    achados: list[str] = []
    for t in textos:
        for c in CVE_RE.findall(t or ""):
            c = c.upper()
            if c not in achados:
                achados.append(c)
    return achados


# --------------------------------------------------------------------------- RSS / Atom

def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _texto(el, *nomes: str) -> str:
    """Texto do primeiro filho cujo nome local esteja em 'nomes' (por ordem de prioridade)."""
    for nome in nomes:
        for filho in el:
            if _local(filho.tag) == nome and (filho.text or "").strip():
                return filho.text.strip()
    return ""


def _ligacao(el) -> str:
    for filho in el:
        if _local(filho.tag) != "link":
            continue
        href = filho.get("href")
        if href and filho.get("rel", "alternate") == "alternate":
            return href.strip()
        if filho.text and filho.text.strip():
            return filho.text.strip()
    return ""


def _data(el) -> datetime | None:
    bruto = _texto(el, "pubDate", "published", "updated", "date")
    if not bruto:
        return None
    try:
        d = parsedate_to_datetime(bruto)
    except (TypeError, ValueError, IndexError):
        try:
            d = datetime.fromisoformat(bruto.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def interpretar_feed(dados: bytes, fonte: dict, agora: datetime) -> list[Item]:
    if b"<!ENTITY" in dados:  # defesa simples contra expansão de entidades XML
        raise ErroFonte("XML com declarações de entidades não é suportado")
    try:
        raiz = ET.fromstring(dados)
    except ET.ParseError as e:
        raise ErroFonte(f"XML inválido ({e})") from None

    exigidas = [p.lower() for p in fonte.get("palavras_obrigatorias", [])]
    itens: list[Item] = []
    for el in raiz.iter():
        if _local(el.tag) not in ("item", "entry"):
            continue
        titulo = limpar_html(_texto(el, "title"))
        url = _ligacao(el)
        if not titulo or not url:
            continue
        resumo = limpar_html(_texto(el, "description", "summary", "content", "encoded"))
        if exigidas and not any(p in f"{titulo} {resumo}".lower() for p in exigidas):
            continue
        guid = _texto(el, "guid", "id") or url
        idioma = fonte.get("idioma")
        if idioma not in ("pt", "en"):
            idioma = detetar_idioma(f"{titulo} {resumo}")
        itens.append(Item(
            id=_id(fonte["nome"], guid),
            titulo=cortar(titulo, 300),
            resumo=cortar(resumo, 600),
            url=url,
            fonte=fonte["nome"],
            idioma=idioma,
            categoria=fonte.get("categoria", "noticias"),
            publicado=_data(el) or agora,
            cves=_cves(titulo, resumo),
        ))
    return itens


# --------------------------------------------------------------------------- CISA KEV

def interpretar_kev(dados: bytes, fonte: dict, agora: datetime, janela_horas: int) -> list[Item]:
    j = json.loads(dados)
    limite = agora - timedelta(hours=janela_horas + 24)
    itens: list[Item] = []
    for v in j.get("vulnerabilities", []):
        cve = (v.get("cveID") or "").upper()
        try:
            # A KEV só indica o dia: assume-se o meio-dia (UTC), que cai no mesmo dia em Portugal.
            d = datetime.strptime(v["dateAdded"], "%Y-%m-%d").replace(
                hour=12, minute=0, second=0, tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        if not cve or d < limite:
            continue
        nome = v.get("vulnerabilityName") or f"{v.get('vendorProject', '')} {v.get('product', '')}".strip()
        etiquetas = [ETQ_EXPLORADA]
        if str(v.get("knownRansomwareCampaignUse", "")).lower() == "known":
            etiquetas.append(ETQ_RANSOMWARE)
        prazo = v.get("dueDate")
        if prazo:
            try:
                prazo = datetime.strptime(prazo, "%Y-%m-%d").strftime("%d/%m/%Y")
            except ValueError:
                pass
            etiquetas.append(f"Prazo CISA: {prazo}")
        itens.append(Item(
            id=f"kev:{cve}",
            titulo=cortar(f"{cve}: {nome}", 300),
            resumo=cortar(limpar_html(v.get("shortDescription", "")), 600),
            url=f"https://nvd.nist.gov/vuln/detail/{cve}",
            fonte=fonte["nome"],
            idioma=fonte.get("idioma", "en"),
            categoria=fonte.get("categoria", "exploradas"),
            publicado=d,
            cves=[cve],
            etiquetas=etiquetas,
        ))
    return itens


# --------------------------------------------------------------------------- NVD

def construir_url_nvd(fonte: dict, agora: datetime, janela_horas: int) -> str:
    inicio = (agora - timedelta(hours=janela_horas)).astimezone(timezone.utc)
    fim = agora.astimezone(timezone.utc)
    fmt = "%Y-%m-%dT%H:%M:%S.000+00:00"
    params = {
        "pubStartDate": inicio.strftime(fmt),
        "pubEndDate": fim.strftime(fmt),
        "cvssV3Severity": "CRITICAL",
        "resultsPerPage": "100",
    }
    return f"{fonte['url']}?{urllib.parse.urlencode(params)}"


def _cvss(cve: dict) -> float:
    melhor = 0.0
    for chave, lista in (cve.get("metrics") or {}).items():
        if not chave.startswith("cvssMetricV"):
            continue
        for m in lista or []:
            s = (m.get("cvssData") or {}).get("baseScore")
            if isinstance(s, (int, float)):
                melhor = max(melhor, float(s))
    return melhor


def interpretar_nvd(dados: bytes, fonte: dict, agora: datetime) -> list[Item]:
    j = json.loads(dados)
    itens: list[Item] = []
    for entrada in j.get("vulnerabilities", []):
        cve = entrada.get("cve") or {}
        cve_id = (cve.get("id") or "").upper()
        if not cve_id or cve.get("vulnStatus") == "Rejected":
            continue
        desc = next((d.get("value", "") for d in cve.get("descriptions", [])
                     if d.get("lang") == "en"), "")
        desc = limpar_html(desc)
        if not desc or desc.startswith("** REJECT"):
            continue
        try:
            pub = datetime.fromisoformat(cve["published"]).replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            pub = agora
        pontos = _cvss(cve)
        primeira = desc.split(". ")[0]
        itens.append(Item(
            id=f"nvd:{cve_id}",
            titulo=cortar(f"{cve_id}: {primeira}", 160),
            resumo=cortar(desc, 600),
            url=f"https://nvd.nist.gov/vuln/detail/{cve_id}",
            fonte=fonte["nome"],
            idioma=fonte.get("idioma", "en"),
            categoria=fonte.get("categoria", "criticas"),
            publicado=pub,
            cves=[cve_id],
            etiquetas=[f"CVSS {pontos:.1f}"] if pontos else [],
        ))
    return itens


# --------------------------------------------------------------------------- recolha

def recolher(cfg: dict, agora: datetime, env: dict | None = None,
             obter_fn: Callable[..., bytes] = obter) -> tuple[list[Item], list[str]]:
    """Recolhe todas as fontes. Uma fonte com falha não impede as restantes."""
    env = env or {}
    janela = int(cfg.get("geral", {}).get("janela_horas", 36))
    itens: list[Item] = []
    avisos: list[str] = []
    for fonte in cfg.get("fontes", []):
        nome = fonte.get("nome", "?")
        try:
            tipo = fonte.get("tipo", "rss")
            if tipo == "rss":
                itens += interpretar_feed(obter_fn(fonte["url"]), fonte, agora)
            elif tipo == "kev":
                itens += interpretar_kev(obter_fn(fonte["url"]), fonte, agora, janela)
            elif tipo == "nvd":
                cab = {"apiKey": env["NVD_API_KEY"]} if env.get("NVD_API_KEY") else {}
                url = construir_url_nvd(fonte, agora, janela)
                itens += interpretar_nvd(obter_fn(url, cabecalhos=cab), fonte, agora)
            else:
                raise ErroFonte(f"tipo de fonte desconhecido: {tipo}")
        except (ErroRede, ErroFonte, ValueError, KeyError) as e:
            avisos.append(f"Fonte «{nome}» indisponível: {e}")
    return itens, avisos
