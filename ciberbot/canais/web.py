"""Canal web: gera um site estático (publicável no GitHub Pages) com arquivo diário."""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path

from ..edicao import Edicao, agrupar, pagina_html
from ..modelos import Item
from .base import ErroCanal

NOME = "web"


def ativo(cfg: dict, env: dict) -> bool:
    return bool(cfg.get("web", {}).get("ativo", True))


def _carregar_dia(caminho: Path) -> list[Item]:
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        return [Item.de_dict(d) for d in dados.get("itens", [])]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def enviar(ed: Edicao, cfg: dict, env: dict, pasta: str | Path | None = None) -> str:
    raiz = Path(pasta or cfg.get("web", {}).get("pasta", "docs"))
    dia = ed.data.isoformat()
    try:
        (raiz / "arquivo").mkdir(parents=True, exist_ok=True)
        (raiz / "dados").mkdir(parents=True, exist_ok=True)

        # Se já houve uma execução hoje, junta os itens (a página do dia é cumulativa).
        json_dia = raiz / "dados" / f"{dia}.json"
        anteriores = _carregar_dia(json_dia)
        if anteriores:
            por_id = {i.id: i for i in anteriores}
            por_id.update({i.id: i for i in ed.itens()})
            ordem = cfg.get("geral", {}).get("ordem_seccoes")
            ed = replace(ed, seccoes=agrupar(list(por_id.values()), ordem))

        json_dia.write_text(
            json.dumps({"data": dia, "gerado_em": ed.gerado_em.isoformat(),
                        "itens": [i.para_dict() for i in ed.itens()]},
                       ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        datas = sorted({p.stem for p in (raiz / "arquivo").glob("*.html")} | {dia}, reverse=True)
        (raiz / "arquivo" / f"{dia}.html").write_text(
            pagina_html(ed, arquivo=None, prefixo="../"), encoding="utf-8")
        # A página inicial mostra sempre a edição mais recente (e a lista do arquivo).
        ultimo = datas[0]
        ed_indice = ed
        if ultimo != dia:
            itens_ultimo = _carregar_dia(raiz / "dados" / f"{ultimo}.json")
            ordem = cfg.get("geral", {}).get("ordem_seccoes")
            ed_indice = (replace(ed, data=date.fromisoformat(ultimo), avisos=[],
                                 seccoes=agrupar(itens_ultimo, ordem)) if itens_ultimo else None)
        if ed_indice:
            (raiz / "index.html").write_text(pagina_html(ed_indice, arquivo=datas), encoding="utf-8")
        (raiz / ".nojekyll").touch()  # o GitHub Pages não precisa de processar com Jekyll
    except OSError as e:
        raise ErroCanal(f"não foi possível escrever o site ({type(e).__name__})") from None
    return f"site atualizado em {raiz}/ ({ed.total} itens)"
