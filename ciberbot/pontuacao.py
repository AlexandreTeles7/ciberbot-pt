"""Pontuação, deduplicação e limites do resumo."""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime

from .modelos import ETQ_NA_KEV, ETQ_RANSOMWARE, Item


def _regex_termo(termo: str) -> re.Pattern:
    # Limites de palavra: evita que "rce" dê pontos a "source".
    return re.compile(rf"(?<!\w){re.escape(termo.lower())}(?!\w)")


def pontuar(itens: list[Item], cfg: dict, cves_kev: set[str], agora: datetime) -> None:
    """Atribui 'pontuacao' a cada item (quanto maior, mais relevante)."""
    janela = float(cfg.get("geral", {}).get("janela_horas", 36))
    regras = [(_regex_termo(t), int(v)) for t, v in (cfg.get("palavras_chave") or {}).items()]
    pesos = {f["nome"]: int(f.get("peso", 10)) for f in cfg.get("fontes", [])}
    for it in itens:
        texto = f"{it.titulo} {it.resumo}".lower()
        p = float(pesos.get(it.fonte, 10))
        p += sum(v for rx, v in regras if rx.search(texto))
        for e in it.etiquetas:
            if e.startswith("CVSS "):
                try:
                    p += max(0.0, float(e[5:]) - 7.0) * 6
                except ValueError:
                    pass
        if ETQ_RANSOMWARE in it.etiquetas:
            p += 15
        if it.categoria == "noticias" and any(c.upper() in cves_kev for c in it.cves):
            p += 15
            if ETQ_NA_KEV not in it.etiquetas:
                it.etiquetas.append(ETQ_NA_KEV)
        idade_h = max(0.0, (agora - it.publicado).total_seconds() / 3600)
        p += 10 * max(0.0, 1 - idade_h / janela)
        it.pontuacao = round(p, 1)


def _tokens(titulo: str) -> set[str]:
    return {w for w in re.findall(r"\w+", titulo.lower()) if len(w) > 3}


def _parecidos(a: set[str], b: set[str]) -> bool:
    return len(a) >= 3 and len(b) >= 3 and len(a & b) / len(a | b) >= 0.6


def deduplicar(itens: list[Item], cves_kev: set[str] | None = None,
               titulos_anteriores: list[str] | None = None) -> list[Item]:
    """Remove CVE críticos já cobertos pela KEV e títulos muito parecidos.

    'cves_kev' deve incluir também CVE da KEV já enviados noutros dias, e
    'titulos_anteriores' os títulos de edições recentes: assim a mesma história,
    vinda de outra fonte noutro dia, não volta a aparecer.
    """
    ordenados = sorted(itens, key=lambda i: -i.pontuacao)
    kev = {c.upper() for c in (cves_kev or set())}
    kev |= {c.upper() for i in ordenados if i.categoria == "exploradas" for c in i.cves}
    previos = [_tokens(t) for t in (titulos_anteriores or [])]
    mantidos: list[Item] = []
    tokens_mantidos: list[set[str]] = []
    for it in ordenados:
        if it.categoria == "criticas" and any(c.upper() in kev for c in it.cves):
            continue
        tk = _tokens(it.titulo)
        if any(_parecidos(tk, tm) for tm in tokens_mantidos + previos):
            continue
        mantidos.append(it)
        tokens_mantidos.append(tk)
    return mantidos


def limitar(itens: list[Item], cfg: dict) -> list[Item]:
    """Aplica os limites por fonte, por secção e total (por ordem de pontuação)."""
    geral = cfg.get("geral", {})
    limites = cfg.get("limites", {})
    por_fonte_padrao = int(geral.get("max_por_fonte", 8))
    por_fonte_cfg = {f["nome"]: int(f.get("max_itens", por_fonte_padrao)) for f in cfg.get("fontes", [])}
    n_fonte: Counter = Counter()
    n_cat: Counter = Counter()
    saida: list[Item] = []
    for it in sorted(itens, key=lambda i: -i.pontuacao):
        if n_fonte[it.fonte] >= por_fonte_cfg.get(it.fonte, por_fonte_padrao):
            continue
        if it.categoria in limites and n_cat[it.categoria] >= int(limites[it.categoria]):
            continue
        n_fonte[it.fonte] += 1
        n_cat[it.categoria] += 1
        saida.append(it)
    return saida[: int(geral.get("max_itens", 25))]
