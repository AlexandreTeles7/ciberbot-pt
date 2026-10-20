"""Construção da edição diária e geração do texto para cada canal."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone, tzinfo

from .modelos import Item, url_segura
from .texto import cortar

SECCOES = {
    "portugal": ("🇵🇹", "Em Portugal"),
    "exploradas": ("🔴", "Vulnerabilidades exploradas ativamente"),
    "criticas": ("🟠", "Vulnerabilidades críticas recentes"),
    "noticias": ("📰", "Ataques e notícias"),
}
ORDEM_PADRAO = ["portugal", "exploradas", "criticas", "noticias"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]

AVISO_TRADUCAO = ("Traduzido automaticamente para português de Portugal. "
                  "Confirme sempre os detalhes na fonte original.")


@dataclass
class Edicao:
    titulo: str
    data: date
    seccoes: list[tuple[str, list[Item]]]
    avisos: list[str] = field(default_factory=list)
    gerado_em: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    fuso: tzinfo = timezone.utc
    url_publica: str = ""

    def itens(self) -> list[Item]:
        return [i for _, lista in self.seccoes for i in lista]

    @property
    def total(self) -> int:
        return len(self.itens())


def nome_seccao(chave: str) -> tuple[str, str]:
    return SECCOES.get(chave, ("📌", chave.replace("_", " ").capitalize()))


def agrupar(itens: list[Item], ordem: list[str] | None = None) -> list[tuple[str, list[Item]]]:
    ordem = ordem or ORDEM_PADRAO
    grupos: dict[str, list[Item]] = {}
    for it in sorted(itens, key=lambda i: -i.pontuacao):
        grupos.setdefault(it.categoria, []).append(it)
    chaves = [k for k in ordem if k in grupos] + [k for k in grupos if k not in ordem]
    return [(k, grupos[k]) for k in chaves]


def data_extensa(d: date) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def data_curta(dt: datetime, fuso: tzinfo) -> str:
    return dt.astimezone(fuso).strftime("%d/%m")


def etiquetas(it: Item) -> list[str]:
    return list(it.etiquetas) + (["Em inglês"] if it.em_ingles else [])


# --------------------------------------------------------------------------- texto simples

def texto_simples(ed: Edicao) -> str:
    linhas = [ed.titulo, f"{data_extensa(ed.data)} · {ed.total} destaques", ""]
    n = 0
    for chave, lista in ed.seccoes:
        emoji, nome = nome_seccao(chave)
        linhas += [f"== {emoji} {nome} ==", ""]
        for it in lista:
            n += 1
            linhas.append(f"{n}. {it.titulo_final}")
            if it.resumo_final:
                linhas.append(f"   {cortar(it.resumo_final, 400)}")
            meta = [it.fonte, data_curta(it.publicado, ed.fuso)] + etiquetas(it)
            linhas.append("   " + " · ".join(meta))
            if url_segura(it.url):
                linhas.append(f"   {it.url}")
            linhas.append("")
    if ed.url_publica:
        linhas.append(f"Ver no site: {ed.url_publica}")
    linhas.append(AVISO_TRADUCAO)
    for a in ed.avisos:
        linhas.append(f"Nota: {a}")
    return "\n".join(linhas)


# --------------------------------------------------------------------------- Telegram (HTML)

def _esc(s: str) -> str:
    return html.escape(s or "", quote=False)


def _esc_attr(s: str) -> str:
    return html.escape(s or "", quote=True)


def _agrupar_mensagens(blocos: list[str], limite: int) -> list[str]:
    mensagens: list[str] = []
    atual = ""
    for b in blocos:
        if atual and len(atual) + 2 + len(b) > limite:
            mensagens.append(atual)
            atual = b
        else:
            atual = f"{atual}\n\n{b}" if atual else b
    if atual:
        mensagens.append(atual)
    return mensagens


def mensagens_telegram(ed: Edicao, limite: int = 3900) -> list[str]:
    blocos = [f"<b>🛡️ {_esc(ed.titulo)}</b>\n{data_extensa(ed.data)} · {ed.total} destaques"]
    for chave, lista in ed.seccoes:
        emoji, nome = nome_seccao(chave)
        cabecalho = f"<b>{emoji} {_esc(nome)}</b>"
        for k, it in enumerate(lista):
            partes = [f"<b>{_esc(cortar(it.titulo_final, 300))}</b>"]
            if it.resumo_final:
                partes.append(_esc(cortar(it.resumo_final, 400)))
            meta = " · ".join([_esc(it.fonte), data_curta(it.publicado, ed.fuso)]
                              + [_esc(e) for e in etiquetas(it)])
            rodape = f"<i>{meta}</i>"
            if url_segura(it.url):
                rodape += f' · <a href="{_esc_attr(it.url)}">Ler mais</a>'
            partes.append(rodape)
            bloco = "\n".join(partes)
            blocos.append(f"{cabecalho}\n\n{bloco}" if k == 0 else bloco)
    final = [f"<i>{_esc(AVISO_TRADUCAO)}</i>"]
    if ed.url_publica and url_segura(ed.url_publica):
        final.insert(0, f'<a href="{_esc_attr(ed.url_publica)}">Ver no site</a>')
    blocos.append("\n".join(final))
    return _agrupar_mensagens(blocos, limite)


# --------------------------------------------------------------------------- Discord (Markdown)

def _md(s: str) -> str:
    """Escapa caracteres de formatação do Markdown do Discord."""
    return re.sub(r"([\\*_`~|>#\[\]])", r"\\\1", s or "")


def mensagens_discord(ed: Edicao, limite: int = 1900) -> list[str]:
    blocos = [f"# 🛡️ {_md(ed.titulo)}\n{data_extensa(ed.data)} · {ed.total} destaques"]
    for chave, lista in ed.seccoes:
        emoji, nome = nome_seccao(chave)
        cabecalho = f"## {emoji} {_md(nome)}"
        for k, it in enumerate(lista):
            partes = [f"**{_md(cortar(it.titulo_final, 250))}**"]
            if it.resumo_final:
                partes.append(_md(cortar(it.resumo_final, 350)))
            meta = " · ".join([_md(it.fonte), data_curta(it.publicado, ed.fuso)]
                              + [_md(e) for e in etiquetas(it)])
            rodape = f"*{meta}*"
            if url_segura(it.url):
                rodape += f" · <{it.url}>"  # <> evita pré-visualizações enormes
            partes.append(rodape)
            bloco = "\n".join(partes)
            blocos.append(f"{cabecalho}\n{bloco}" if k == 0 else bloco)
    final = f"-# {_md(AVISO_TRADUCAO)}"
    if ed.url_publica and url_segura(ed.url_publica):
        final = f"<{ed.url_publica}>\n{final}"
    blocos.append(final)
    return _agrupar_mensagens(blocos, limite)


# --------------------------------------------------------------------------- e-mail (HTML)

def email_html(ed: Edicao) -> str:
    corpo = [
        '<div style="max-width:680px;margin:0 auto;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;'
        'color:#16191d;line-height:1.5">',
        f'<h1 style="font-size:22px;margin:0 0 4px">🛡️ {_esc(ed.titulo)}</h1>',
        f'<p style="margin:0 0 18px;color:#5b6472">{data_extensa(ed.data)} · {ed.total} destaques</p>',
    ]
    cores = {"portugal": "#1f8a4c", "exploradas": "#d6322f", "criticas": "#e07a12", "noticias": "#3a6fd8"}
    for chave, lista in ed.seccoes:
        emoji, nome = nome_seccao(chave)
        cor = cores.get(chave, "#6b7280")
        corpo.append(f'<h2 style="font-size:17px;margin:24px 0 8px">{emoji} {_esc(nome)}</h2>')
        for it in lista:
            titulo = _esc(it.titulo_final)
            if url_segura(it.url):
                titulo = f'<a href="{_esc_attr(it.url)}" style="color:#0b5fd6;text-decoration:none">{titulo}</a>'
            meta = " · ".join([_esc(it.fonte), data_curta(it.publicado, ed.fuso)]
                              + [_esc(e) for e in etiquetas(it)])
            corpo.append(
                f'<div style="border-left:4px solid {cor};padding:2px 0 2px 12px;margin:0 0 14px">'
                f'<div style="font-weight:600">{titulo}</div>'
                f'<div style="margin:3px 0">{_esc(cortar(it.resumo_final, 400))}</div>'
                f'<div style="font-size:13px;color:#5b6472">{meta}</div></div>'
            )
    rodape = _esc(AVISO_TRADUCAO)
    if ed.url_publica and url_segura(ed.url_publica):
        rodape = f'<a href="{_esc_attr(ed.url_publica)}">Ver no site</a> · {rodape}'
    corpo.append(f'<p style="font-size:12px;color:#5b6472;margin-top:28px">{rodape}</p></div>')
    return "\n".join(corpo)


# --------------------------------------------------------------------------- página web

CSS = """
:root{--fundo:#f6f7f9;--cartao:#fff;--texto:#16191d;--suave:#5b6472;--linha:#e3e6ea;--link:#0b5fd6;--chip:#eef1f5;
--s-portugal:#1f8a4c;--s-exploradas:#d6322f;--s-criticas:#e07a12;--s-noticias:#3a6fd8;--s-outra:#6b7280}
@media (prefers-color-scheme:dark){:root{--fundo:#0f1216;--cartao:#171b21;--texto:#e8eaed;--suave:#9aa3af;
--linha:#262c34;--link:#7db4ff;--chip:#222831;--s-portugal:#4cc17f;--s-exploradas:#ff6b66;--s-criticas:#ffa04a;
--s-noticias:#7aa2ff;--s-outra:#9aa3af}}
*{box-sizing:border-box}
body{margin:0;background:var(--fundo);color:var(--texto);font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--link)}
.caixa{max-width:760px;margin:0 auto;padding:0 16px}
.topo{padding:28px 0 4px}
.marca{margin:0;color:var(--suave);font-size:.8rem;letter-spacing:.06em;text-transform:uppercase}
h1{margin:.25em 0 .15em;font-size:1.7rem;line-height:1.2}
.data{margin:0;color:var(--suave)}
h2{font-size:1.1rem;margin:2em 0 .7em}
.cartao{background:var(--cartao);border:1px solid var(--linha);border-left:4px solid var(--cor);
border-radius:10px;padding:13px 16px;margin:0 0 12px}
.s-portugal{--cor:var(--s-portugal)}.s-exploradas{--cor:var(--s-exploradas)}
.s-criticas{--cor:var(--s-criticas)}.s-noticias{--cor:var(--s-noticias)}.s-outra{--cor:var(--s-outra)}
.cartao h3{margin:0 0 .3em;font-size:1.02rem;line-height:1.35}
.cartao h3 a{color:inherit;text-decoration:none}.cartao h3 a:hover{text-decoration:underline}
.cartao p{margin:.3em 0}
.meta{color:var(--suave);font-size:.85rem}
.chip{display:inline-block;background:var(--chip);border-radius:999px;padding:1px 9px;margin:3px 4px 0 0;font-size:.78rem}
.nota{background:var(--chip);border-radius:10px;padding:10px 14px;font-size:.9rem;color:var(--suave)}
.arquivo ul{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:6px 14px}
.rodape{color:var(--suave);font-size:.82rem;padding:28px 16px 44px}
"""


def _cartao(it: Item, chave: str, fuso: tzinfo) -> str:
    classe = chave if chave in SECCOES else "outra"
    titulo = _esc(it.titulo_final)
    if url_segura(it.url):
        titulo = f'<a href="{_esc_attr(it.url)}" rel="noopener noreferrer">{titulo}</a>'
    chips = "".join(f'<span class="chip">{_esc(e)}</span>' for e in etiquetas(it))
    resumo = f"<p>{_esc(cortar(it.resumo_final, 450))}</p>" if it.resumo_final else ""
    return (f'<article class="cartao s-{classe}"><h3>{titulo}</h3>{resumo}'
            f'<p class="meta">{_esc(it.fonte)} · {data_curta(it.publicado, fuso)}</p>{chips}</article>')


def pagina_html(ed: Edicao, arquivo: list[str] | None = None, prefixo: str = "") -> str:
    """Página completa. 'prefixo' é o caminho relativo até à raiz do site ("" ou "../")."""
    seccoes = []
    for chave, lista in ed.seccoes:
        emoji, nome = nome_seccao(chave)
        cartoes = "\n".join(_cartao(i, chave, ed.fuso) for i in lista)
        seccoes.append(f"<section><h2>{emoji} {_esc(nome)}</h2>\n{cartoes}</section>")
    avisos = ""
    if ed.avisos:
        itens = "".join(f"<li>{_esc(a)}</li>" for a in ed.avisos)
        avisos = f'<p class="nota">Notas desta edição:</p><ul class="nota">{itens}</ul>'
    nav = ""
    if arquivo:
        links = "".join(
            f'<li><a href="{prefixo}arquivo/{_esc_attr(d)}.html">'
            f'{data_extensa(date.fromisoformat(d))}</a></li>' for d in arquivo)
        nav = f'<nav class="arquivo"><h2>🗂️ Arquivo</h2><ul>{links}</ul></nav>'
    elif prefixo:
        nav = f'<p><a href="{prefixo}index.html">← Edição mais recente</a></p>'
    hora = ed.gerado_em.astimezone(ed.fuso).strftime("%d/%m/%Y às %H:%M")
    return f"""<!doctype html>
<html lang="pt-PT">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(ed.titulo)} — {data_extensa(ed.data)}</title>
<meta name="description" content="Resumo diário de cibersegurança em português de Portugal: ataques, vulnerabilidades e alertas.">
<style>{CSS}</style>
</head>
<body>
<header class="topo caixa">
<p class="marca">CiberBot PT</p>
<h1>{_esc(ed.titulo)}</h1>
<p class="data">{data_extensa(ed.data)} · {ed.total} destaques</p>
</header>
<main class="caixa">
{chr(10).join(seccoes)}
{avisos}
{nav}
</main>
<footer class="rodape caixa">
Gerado automaticamente em {hora}. {_esc(AVISO_TRADUCAO)}
</footer>
</body>
</html>
"""
