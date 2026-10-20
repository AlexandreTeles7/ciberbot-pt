"""Pré-visualização com dados de exemplo (ficheiros em tests/fixtures), sem rede nem API."""
from __future__ import annotations

import json
import tempfile
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from .cli import carregar_config, executar

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
# Os dados de exemplo são datados de 19–20 de outubro de 2026; a "hora atual" da demo é fixa.
AGORA_DEMO = datetime(2026, 10, 20, 7, 0, tzinfo=timezone.utc)


def obter_de_ficheiros(url: str, **_ignorado) -> bytes:
    """Substitui o acesso à rede: o último segmento do URL é o nome do ficheiro de exemplo."""
    nome = urllib.parse.urlparse(url).path.rsplit("/", 1)[-1]
    return (FIXTURES / nome).read_bytes()


def traducao_simulada(sistema: str, mensagem: str) -> str:
    """Faz de 'API de tradução': devolve traduções escritas à mão (demo_pt.json)."""
    tabela = json.loads((FIXTURES / "demo_pt.json").read_text(encoding="utf-8"))
    carga = mensagem.split("<itens>\n", 1)[1].rsplit("\n</itens>", 1)[0]
    saida = []
    for item in json.loads(carga):
        t = tabela.get(item["titulo"], {})
        saida.append({
            "i": item["i"],
            "titulo": t.get("titulo", "[PT] " + item["titulo"]),
            "resumo": t.get("resumo", item["resumo"]),
        })
    return json.dumps(saida, ensure_ascii=False)


def executar_demo(pasta_previsao: str = "previsao") -> int:
    cfg = carregar_config(FIXTURES / "config_demo.toml")
    with tempfile.TemporaryDirectory() as tmp:
        return executar(
            cfg, {}, AGORA_DEMO, dry_run=True,
            obter_fn=obter_de_ficheiros, chamar_traducao=traducao_simulada,
            pasta_estado=Path(tmp) / "vistos.json", pasta_previsao=pasta_previsao,
        )
