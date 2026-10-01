"""Teste de ida e volta com PDF sintético: add -> extract --source pdf --json.

Rodar:  uv run --with pymupdf --with pytest pytest tests/ -q
"""
import json
import subprocess
import sys
from pathlib import Path

import pymupdf

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "zotero_anot.py"


def run(*a):
    return subprocess.run([sys.executable, str(SCRIPT), *a], capture_output=True, text=True)


def make_pdf(path):
    d = pymupdf.open()
    for i in range(3):
        p = d.new_page()
        p.insert_text((72, 100), f"Pagina {i + 1}: o timbre do tom-tom depende do tensionamento.")
    d.set_page_labels([{"startpage": 0, "prefix": "ix", "style": "", "firstpagenum": 1}])
    d.save(path)


def test_roundtrip(tmp_path):
    pdf = tmp_path / "a.pdf"
    make_pdf(str(pdf))
    spec = tmp_path / "s.json"
    spec.write_text(json.dumps([
        {"page": 2, "type": "highlight", "text": "timbre do tom-tom", "comment": "c1", "color": "green"},
        {"page": 3, "type": "underline", "text": "tensionamento"},
        {"page": 1, "type": "note", "comment": "nota"},
        {"page": 1, "type": "highlight", "text": "inexistente"},
    ]))
    r = run("add", str(pdf), str(spec), "--dest", "pdf", "--output", str(tmp_path / "b.pdf"))
    assert "[pdf] 3 embutidas" in r.stdout and "1 erros" in r.stdout
    out = run("extract", str(tmp_path / "b.pdf"), "--source", "pdf", "--json")
    anns = json.loads(out.stdout)["anotacoes"]
    assert {a["tipo"] for a in anns} == {"highlight", "underline", "note"}
    h = next(a for a in anns if a["tipo"] == "highlight")
    assert h["texto"] == "timbre do tom-tom" and h["comentario"] == "c1" and h["pagina"] == 2


def test_idempotente(tmp_path):
    pdf = tmp_path / "a.pdf"
    make_pdf(str(pdf))
    spec = tmp_path / "s.json"
    spec.write_text(json.dumps([{"page": 1, "type": "note", "comment": "x"}]))
    env_bk = {"ZOTERO_ANOT_BACKUPS": str(tmp_path / "bk")}
    import os
    os.environ.update(env_bk)
    assert "[pdf] 1 embutidas" in run("add", str(pdf), str(spec), "--dest", "pdf").stdout
    assert "pulado" in run("add", str(pdf), str(spec), "--dest", "pdf").stdout


def test_markdown_e_native_offline(tmp_path):
    """md do Obsidian -> specs; item nativo com chave determinística; sem PDF alterado."""
    sys.path.insert(0, str(SCRIPT.parent))
    import zotero_anot as za
    import zotero_native as zn
    pdf = tmp_path / "a.pdf"
    make_pdf(str(pdf))
    md = ("## p. 2\n> timbre do tom-tom :: bom ponto {verde}\n- :: nota geral\n"
          "## pl. ix\n_> tensionamento ::\n> sem dois-pontos duplos\n")
    specs = za.parse_md(md)
    assert [s["type"] for s in specs] == ["highlight", "note", "underline"]
    assert specs[2]["page_label"] == "ix" and specs[0]["color"] == "verde"
    doc = pymupdf.open(str(pdf))
    st, ann = za.resolve_spec(doc, specs[0])
    assert st == "ok"
    item = zn.to_native(doc[1], ann, "ATTKEY12", "t", "agente")
    assert item["key"] == zn.zkey(ann["id"]) and len(item["key"]) == 8
    pos = json.loads(item["annotationPosition"])
    assert pos["pageIndex"] == 1 and pos["rects"][0][1] < pos["rects"][0][3]  # y de baixo p/ cima
    js = zn.js_snippet(1, "ATTKEY12", [item])
    assert "Zotero.Annotations.saveFromJSON" in js and item["key"] in js


def test_strip(tmp_path):
    pdf = tmp_path / "a.pdf"
    make_pdf(str(pdf))
    spec = tmp_path / "s.json"
    spec.write_text(json.dumps([{"page": 1, "type": "note", "comment": "x"}]))
    run("add", str(pdf), str(spec), "--dest", "pdf", "--output", str(tmp_path / "b.pdf"))
    r = run("strip", str(tmp_path / "b.pdf"), "--output", str(tmp_path / "c.pdf"))
    assert "1 anotações embutidas removidas" in r.stdout
    assert all(not list(p.annots() or []) for p in pymupdf.open(str(tmp_path / "c.pdf")))


def test_flags_em_portugues_continuam_funcionando(tmp_path):
    """Compatibilidade: apelidos antigos (--destino pdf, --saida, --fonte) e valores (ambos/ambas)."""
    pdf, spec = tmp_path / "a.pdf", tmp_path / "m.json"
    make_pdf(pdf)
    spec.write_text(json.dumps([{"page": 2, "type": "highlight", "text": "timbre do tom-tom", "comment": "c"}]))
    r = run("add", str(pdf), str(spec), "--destino", "pdf", "--saida", str(tmp_path / "b.pdf"))
    assert "[pdf] 1 embutidas" in r.stdout
    out = run("extract", str(tmp_path / "b.pdf"), "--fonte", "pdf", "--json")
    assert json.loads(out.stdout)["anotacoes"]
    assert run("extract", str(tmp_path / "b.pdf"), "--fonte", "ambas", "--json").returncode == 0
    assert run("add", str(pdf), str(spec), "--destino", "ambos", "--dry-run").returncode == 0
