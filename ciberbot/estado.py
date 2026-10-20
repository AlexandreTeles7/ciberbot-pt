"""Memória dos itens já enviados, para nunca repetir notícias."""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path

DIAS_TITULOS = 7  # durante quantos dias se compara a semelhança com títulos já enviados


class Estado:
    def __init__(self, caminho: str | Path):
        self.caminho = Path(caminho)
        self.vistos: dict[str, str] = {}              # id -> data (AAAA-MM-DD)
        self.titulos: dict[str, list[str]] = {}       # id -> [data, título original]
        self.aviso = ""

    def carregar(self) -> "Estado":
        if self.caminho.exists():
            try:
                dados = json.loads(self.caminho.read_text(encoding="utf-8"))
                vistos = dados.get("vistos", {})
                titulos = dados.get("titulos", {})
                if isinstance(vistos, dict):
                    self.vistos = {str(k): str(v) for k, v in vistos.items()}
                if isinstance(titulos, dict):
                    self.titulos = {str(k): [str(v[0]), str(v[1])] for k, v in titulos.items()
                                    if isinstance(v, list) and len(v) == 2}
            except (OSError, ValueError, TypeError, IndexError):
                self.aviso = "Ficheiro de estado ilegível; a começar do zero."
                self.vistos, self.titulos = {}, {}
        return self

    def ja_visto(self, id_: str) -> bool:
        return id_ in self.vistos

    def marcar(self, ids, hoje: date) -> None:
        for i in ids:
            self.vistos[i] = hoje.isoformat()

    def registar_titulos(self, itens, hoje: date) -> None:
        for it in itens:
            self.titulos[it.id] = [hoje.isoformat(), it.titulo]

    def titulos_recentes(self) -> list[str]:
        return [t for _, t in self.titulos.values()]

    def podar(self, hoje: date, dias: int = 90) -> None:
        corte = (hoje - timedelta(days=dias)).isoformat()
        self.vistos = {k: v for k, v in self.vistos.items() if v >= corte}
        corte_t = (hoje - timedelta(days=DIAS_TITULOS)).isoformat()
        self.titulos = {k: v for k, v in self.titulos.items() if v[0] >= corte_t}

    def guardar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.caminho.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"versao": 1,
                        "vistos": dict(sorted(self.vistos.items())),
                        "titulos": dict(sorted(self.titulos.items()))},
                       ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        os.replace(tmp, self.caminho)
