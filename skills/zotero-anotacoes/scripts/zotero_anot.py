#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pymupdf"]
# ///
"""zotero_anot — extrai e inclui anotações de PDFs do Zotero.

Subcomandos:
  extract  PDF -> Markdown/JSON. Lê (a) o banco do Zotero (anotações feitas no
           leitor do Zotero, que NÃO ficam no arquivo PDF) e (b) anotações
           embutidas no próprio PDF (feitas em Preview, Skim, Acrobat, ou
           incluídas por este script).
  add      Inclui anotações (JSON ou Markdown do Obsidian). Padrão: nativas no
           Zotero via Web API (fallback: snippet JS); --destino pdf embute no PDF.
  embed    Converte as anotações do banco do Zotero em anotações embutidas no PDF.
  strip    Remove anotações embutidas criadas por este script.
  info     Mostra o item/attachment do Zotero que corresponde a um PDF e
           contagens por tipo.
  pages    Tabela página-PDF <-> rótulo de página (ex.: ix, 57), útil para
           traduzir "página 57" do texto impresso para o índice do PDF.

Sem dependências além de `pymupdf` (stdlib para o resto). Nunca escreve no
banco do Zotero. `add` faz backup do PDF antes de gravar.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import pymupdf

pymupdf.TOOLS.mupdf_display_errors(False)

# ----------------------------------------------------------------- constantes
ZTYPE = {1: "highlight", 2: "note", 3: "image", 4: "ink", 5: "underline", 6: "text"}
ZCOLORS = {  # paleta padrão do leitor do Zotero 7
    "#ffd400": "amarelo", "#ff6666": "vermelho", "#5fb236": "verde",
    "#2ea8e5": "azul", "#a28ae5": "roxo", "#e56eee": "magenta",
    "#f19837": "laranja", "#aaaaaa": "cinza",
}
NAME2HEX = {"yellow": "#ffd400", "red": "#ff6666", "green": "#5fb236",
            "blue": "#2ea8e5", "purple": "#a28ae5", "magenta": "#e56eee",
            "orange": "#f19837", "gray": "#aaaaaa", "grey": "#aaaaaa"}
NAME2HEX.update({v: k for k, v in ZCOLORS.items()})  # nomes em português
AUTHOR_DEFAULT = "agente"


def die(msg: str, code: int = 2):
    print(f"erro: {msg}", file=sys.stderr)
    sys.exit(code)


def hex2rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore


def rgb2hex(c) -> str | None:
    if not c:
        return None
    return "#%02x%02x%02x" % tuple(round(v * 255) for v in c[:3])


def color_name(hexv: str | None) -> str:
    if not hexv:
        return ""
    return ZCOLORS.get(hexv.lower(), hexv.lower())


def norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


# ------------------------------------------------------------ config do Zotero
def _prefs() -> dict[str, str]:
    out: dict[str, str] = {}
    for p in Path.home().glob("Library/Application Support/Zotero/Profiles/*/prefs.js"):
        for m in re.finditer(r'user_pref\("([^"]+)",\s*"?([^")]*)"?\);', p.read_text(errors="ignore")):
            out[m.group(1)] = m.group(2)
    roots = [Path(os.environ["APPDATA"]) / "Zotero" / "Zotero" / "Profiles"] if os.environ.get("APPDATA") else []  # Windows
    for p in [q for r in roots for q in r.glob("*/prefs.js")] + list(Path.home().glob(".zotero/zotero/*/prefs.js")):  # + Linux
        for m in re.finditer(r'user_pref\("([^"]+)",\s*"?([^")]*)"?\);', p.read_text(errors="ignore")):
            out[m.group(1)] = m.group(2)
    return out


def zotero_dirs(args) -> tuple[Path, Path | None]:
    prefs = _prefs()
    data = args.zotero_dir or os.environ.get("ZOTERO_DATA_DIR") or prefs.get("extensions.zotero.dataDir") or str(Path.home() / "Zotero")
    base = args.base_dir or os.environ.get("ZOTERO_BASE_DIR") or prefs.get("extensions.zotero.baseAttachmentPath")
    return Path(data).expanduser(), (Path(base).expanduser() if base else None)


def open_db(data_dir: Path) -> sqlite3.Connection:
    """Zotero mantém o banco travado enquanto aberto: trabalha numa cópia
    (banco + WAL) em cache, refeita quando a origem muda."""
    src = data_dir / "zotero.sqlite"
    if not src.exists():
        die(f"zotero.sqlite não encontrado em {data_dir} (use --zotero-dir)")
    cache = Path(tempfile.gettempdir()) / "zotero_anot_cache"
    cache.mkdir(exist_ok=True)
    tag = hashlib.md5(str(src).encode()).hexdigest()[:8]
    dst = cache / f"{tag}.sqlite"
    parts = [src, Path(str(src) + "-wal")]
    newest = max(p.stat().st_mtime for p in parts if p.exists())
    if not dst.exists() or dst.stat().st_mtime < newest:
        for suf in ("", "-wal", "-shm"):
            Path(str(dst) + suf).unlink(missing_ok=True)
        shutil.copy2(src, dst)
        wal = Path(str(src) + "-wal")
        if wal.exists():
            shutil.copy2(wal, str(dst) + "-wal")
    con = sqlite3.connect(str(dst))
    con.row_factory = sqlite3.Row
    return con


def resolve_attachment(con, data_dir: Path, base: Path | None, pdf: Path):
    """PDF em disco -> linha do itemAttachments (ou None)."""
    pdf = pdf.resolve()
    rows = con.execute(
        "SELECT att.itemID, att.parentItemID, att.path, i.key, i.libraryID "
        "FROM itemAttachments att JOIN items i USING(itemID) WHERE att.path LIKE ?",
        ("%" + pdf.name,)).fetchall()
    for r in rows:
        p = r["path"] or ""
        if p.startswith("attachments:") and base:
            cand = base / p[len("attachments:"):]
        elif p.startswith("storage:"):
            cand = data_dir / "storage" / r["key"] / p[len("storage:"):]
        else:
            cand = Path(p)
        try:
            if cand.resolve() == pdf:
                return r
        except OSError:
            pass
    return None


def item_meta(con, item_id: int | None) -> dict:
    if not item_id:
        return {}
    q = ("SELECT f.fieldName, v.value FROM itemData d JOIN fields f USING(fieldID) "
         "JOIN itemDataValues v USING(valueID) WHERE d.itemID=?")
    meta = {r[0]: r[1] for r in con.execute(q, (item_id,))}
    meta["key"] = con.execute("SELECT key FROM items WHERE itemID=?", (item_id,)).fetchone()[0]
    return meta


# --------------------------------------------------------------- extração
def _rects_to_page(page, rects) -> list[pymupdf.Rect]:
    m = page.transformation_matrix
    return [pymupdf.Rect(*r) * m for r in rects]  # ~ normaliza abaixo


def _norm_rect(r: pymupdf.Rect) -> pymupdf.Rect:
    return pymupdf.Rect(min(r.x0, r.x1), min(r.y0, r.y1), max(r.x0, r.x1), max(r.y0, r.y1))


def zotero_annotations(con, att) -> list[dict]:
    rows = con.execute(
        "SELECT ia.*, i.key, i.dateAdded, i.dateModified FROM itemAnnotations ia "
        "JOIN items i USING(itemID) WHERE ia.parentItemID=? ORDER BY ia.sortIndex",
        (att["itemID"],)).fetchall()
    out = []
    for r in rows:
        pos = json.loads(r["position"])
        tags = [t[0] for t in con.execute(
            "SELECT t.name FROM itemTags it JOIN tags t USING(tagID) WHERE it.itemID=?", (r["itemID"],))]
        out.append({
            "origem": "zotero", "key": r["key"], "tipo": ZTYPE.get(r["type"], str(r["type"])),
            "pagina": pos["pageIndex"] + 1, "rotulo": r["pageLabel"],
            "cor": (r["color"] or "").lower(), "texto": r["text"] or "", "comentario": r["comment"] or "",
            "autor": r["authorName"] or "", "tags": tags, "criado": r["dateAdded"],
            "_pos": pos,
        })
    return out


def pdf_annotations(doc) -> list[dict]:
    out = []
    for page in doc:
        for a in page.annots() or []:
            t = a.type[1]
            tipo = {"Highlight": "highlight", "Underline": "underline", "Text": "note",
                    "FreeText": "text", "Ink": "ink", "Square": "image", "StrikeOut": "strikeout",
                    "Squiggly": "squiggly"}.get(t)
            if not tipo:
                continue
            info = a.info
            texto = ""
            if tipo in ("highlight", "underline", "strikeout", "squiggly"):
                verts = a.vertices or []
                quads = [pymupdf.Quad(verts[i:i + 4]) for i in range(0, len(verts), 4)]
                texto = " ".join(page.get_textbox(q.rect).strip() for q in quads)
                texto = re.sub(r"\s+", " ", texto).strip()
            nm = ""
            try:
                nm = doc.xref_get_key(a.xref, "NM")[1].strip("()")
            except Exception:
                pass
            comentario = info.get("content", "") or ""
            if tipo == "text" and not comentario:
                comentario = a.get_text() if hasattr(a, "get_text") else ""
            strokes = [[tuple(p) for p in st] for st in (a.vertices or [])] if tipo == "ink" else []
            out.append({
                "_strokes": strokes,
                "origem": "pdf", "key": nm or f"xref{a.xref}", "tipo": tipo,
                "pagina": page.number + 1, "rotulo": page.get_label() or "",
                "cor": rgb2hex(a.colors.get("stroke") or a.colors.get("fill")) or "",
                "texto": texto, "comentario": comentario,
                "autor": info.get("title", ""), "tags": [], "criado": info.get("creationDate", ""),
                "_rect": tuple(a.rect),
            })
    return out


def merge(zot: list[dict], emb: list[dict]) -> list[dict]:
    """Junta as duas fontes; descarta duplicata do PDF já presente no Zotero."""
    seen = {(a["pagina"], a["tipo"], norm(a["texto"] or a["comentario"])) for a in zot}
    extra = [a for a in emb if (a["pagina"], a["tipo"], norm(a["texto"] or a["comentario"])) not in seen]
    allann = zot + extra
    allann.sort(key=lambda a: (a["pagina"], a["_pos"]["rects"][0][1] * -1 if a.get("_pos") and a["_pos"].get("rects") else -(a.get("_rect", (0, 0, 0, 0))[1])))
    return allann


def ink_strokes(page, a) -> list[list[tuple[float, float]]]:
    """Traços do desenho em coordenadas de página (origem no topo-esquerdo)."""
    if a.get("_pos"):
        m = page.transformation_matrix
        return [[tuple(pymupdf.Point(p[i], p[i + 1]) * m) for i in range(0, len(p) - 1, 2)]
                for p in a["_pos"].get("paths", [])]
    return a.get("_strokes", [])


def ink_text(page, a) -> str:
    """Texto coberto pela extensão vertical de um desenho feito na margem.

    Linhas cujo centro vertical cai entre o topo e a base do traço; do lado
    do traço em diante (traço à esquerda -> palavras à direita, e vice-versa).
    Desenhos sobre figuras ou muito largos (círculos, setas) não geram texto.
    """
    pts = [p for s in ink_strokes(page, a) for p in s]
    if not pts:
        return ""
    r = pymupdf.Rect(min(p[0] for p in pts), min(p[1] for p in pts),
                     max(p[0] for p in pts), max(p[1] for p in pts))
    if r.width > 0.25 * page.rect.width:
        return ""
    for img in page.get_image_info():
        inter = r & pymupdf.Rect(img["bbox"])
        if not inter.is_empty and inter.get_area() > 0.3 * max(r.get_area(), 1):
            return ""
    left = (r.x0 + r.x1) / 2 < page.rect.width / 2
    lines: dict[tuple, list] = {}
    for x0, y0, x1, y1, w, b, l, _n in page.get_text("words"):
        if r.y0 <= (y0 + y1) / 2 <= r.y1 and (x1 > r.x0 if left else x0 < r.x1):
            lines.setdefault((b, l), []).append((x0, y0, w))
    ordered = sorted(lines.values(), key=lambda ws: ws[0][1])
    return re.sub(r"\s+", " ", " ".join(" ".join(w for *_, w in sorted(ws)) for ws in ordered)).strip()


def render_region(doc, a, outdir: Path) -> str | None:
    """Recorta a região de anotações image/ink do PDF para PNG (com o traço)."""
    page = doc[a["pagina"] - 1]
    strokes = []
    if a["tipo"] == "ink":
        strokes = ink_strokes(page, a)
        pts = [p for s in strokes for p in s]
        if not pts:
            return None
        r = pymupdf.Rect(min(p[0] for p in pts), min(p[1] for p in pts),
                         max(p[0] for p in pts), max(p[1] for p in pts))
        r = pymupdf.Rect(r.x0 - 12, r.y0 - 12, r.x1 + 12, r.y1 + 12)
    elif a.get("_pos"):
        rects = a["_pos"].get("rects")
        if not rects:
            return None
        r = _norm_rect(_rects_to_page(page, rects)[0])
    else:
        r = pymupdf.Rect(a["_rect"])
    r &= page.rect
    outdir.mkdir(parents=True, exist_ok=True)
    fn = outdir / f"{a['key']}.png"
    pix = page.get_pixmap(clip=r, dpi=150, annots=False)
    if strokes:  # sobrepõe o traço: página temporária com o recorte + polilinhas
        tmp = pymupdf.open()
        tp = tmp.new_page(width=r.width, height=r.height)
        tp.insert_image(tp.rect, pixmap=pix)
        col = hex2rgb(a["cor"] or "#2ea8e5")
        width = (a.get("_pos") or {}).get("width", 2)
        sh = tp.new_shape()
        for st in strokes:
            sh.draw_polyline([pymupdf.Point(x - r.x0, y - r.y0) for x, y in st])
        sh.finish(color=col, width=width, closePath=False, lineCap=1, lineJoin=1)
        sh.commit()
        pix = tp.get_pixmap(dpi=150)
    pix.save(str(fn))
    return fn.name


def cmd_extract(args):
    pdf = Path(args.pdf).expanduser()
    if not pdf.exists():
        die(f"PDF não encontrado: {pdf}")
    doc = pymupdf.open(pdf)
    att = meta = None
    zot: list[dict] = []
    if args.fonte in ("auto", "zotero", "ambas"):
        data_dir, base = zotero_dirs(args)
        try:
            con = open_db(data_dir)
            att = resolve_attachment(con, data_dir, base, pdf)
            if att:
                meta = item_meta(con, att["parentItemID"] or att["itemID"])
                zot = zotero_annotations(con, att)
            elif args.fonte == "zotero":
                die("este PDF não está registrado como attachment no Zotero (--base-dir correto?)")
        except SystemExit:
            raise
        except Exception as e:
            if args.fonte == "zotero":
                die(f"falha lendo o banco do Zotero: {e}")
            print(f"aviso: banco do Zotero indisponível ({e}); seguindo só com o PDF", file=sys.stderr)
    emb = pdf_annotations(doc) if args.fonte in ("auto", "pdf", "ambas") else []
    anns = merge(zot, emb) if args.fonte != "zotero" else zot

    if args.tipos:
        want = {t.strip() for t in args.tipos.split(",")}
        anns = [a for a in anns if a["tipo"] in want]
    if args.paginas:
        lo, _, hi = args.paginas.partition("-")
        lo, hi = int(lo), int(hi or lo)
        anns = [a for a in anns if lo <= a["pagina"] <= hi]

    for a in anns:
        if a["tipo"] == "ink" and not a["texto"]:
            a["texto"] = ink_text(doc[a["pagina"] - 1], a)
            if a["texto"]:
                a["texto_coberto"] = True

    imgdir = None
    if args.imagens:
        imgdir = Path(args.imagens).expanduser()
        for a in anns:
            if a["tipo"] in ("image", "ink"):
                a["imagem"] = render_region(doc, a, imgdir)

    for a in anns:
        a.pop("_pos", None)
        a.pop("_rect", None)
        a.pop("_strokes", None)

    if args.json:
        text = json.dumps({"pdf": str(pdf), "item": meta, "anotacoes": anns}, ensure_ascii=False, indent=2)
    else:
        text = to_markdown(pdf, meta, att, anns, imgdir, args.saida)
    if args.saida:
        dst = Path(args.saida).expanduser()
        extra = ""
        if dst.exists() and not args.json:
            old_text = dst.read_text(encoding="utf-8")
            bk = backup_md(dst)
            if args.se_existe == "mesclar":
                edited = [k for k, w in parse_export_md(old_text).items()
                          if k in (nw := parse_export_md(text)) and w["comment"] != nw[k]["comment"]]
                text, info = merge_export(old_text, text)
                extra = f"; mesclado: {info['mantidos']} trechos seus mantidos"
                if info["orfaos"]:
                    extra += f", {info['orfaos']} sem âncora (no fim do arquivo)"
                if edited:
                    extra += (f"\naviso: {len(edited)} comentário(s) diferem do Zotero ({', '.join(edited)}); "
                              "o do Zotero prevaleceu — para enviar edições do .md use `sync-md` antes")
            extra += f"\n(backup da nota anterior: {bk})"
        dst.write_text(text, encoding="utf-8")
        if imgdir:
            gone = clean_orphan_images(imgdir, {a["imagem"] for a in anns if a.get("imagem")})
            if gone:
                extra += f"\n{gone} imagem(ns) órfã(s) removida(s) de {imgdir}"
        print(f"{len(anns)} anotações -> {args.saida}{extra}", file=sys.stderr)
    else:
        print(text)


# ------------------------------------------------ mesclar com nota já existente
_PAGE = re.compile(r"^#{2,4} p\. (\d+)")
_PAGELINK = re.compile(r"^\[↗ abrir página\]\(zotero://open-pdf/")
_COUNTS = re.compile(r"^_\d+ .*_$")


def _tokenize(text: str):
    """-> (cabeçalho, [tokens]); token = ('page', n, linhas) | ('block', chave, linhas) | ('text', None, linhas)."""
    lines = text.split("\n")
    i = next((k for k, ln in enumerate(lines) if _PAGE.match(ln) or _HEAD.match(ln)), len(lines))
    head, toks = lines[:i], []
    while i < len(lines):
        ln = lines[i]
        m = _PAGE.match(ln)
        if m:
            grp = [ln]
            i += 1
            if i < len(lines) and _PAGELINK.match(lines[i]):
                grp.append(lines[i])
                i += 1
            toks.append(("page", int(m.group(1)), grp))
            continue
        m = _HEAD.match(ln)
        if m:
            grp = [ln]
            i += 1
            while i < len(lines) and lines[i].startswith(">"):
                grp.append(lines[i])
                i += 1
            toks.append(("block", m.group(1), grp))
            continue
        grp = []
        while i < len(lines) and not _PAGE.match(lines[i]) and not _HEAD.match(lines[i]):
            grp.append(lines[i])
            i += 1
        while grp and not grp[0].strip():
            grp.pop(0)
        while grp and not grp[-1].strip():
            grp.pop()
        if grp:
            toks.append(("text", None, grp))
    return head, toks


def merge_export(old: str, new: str) -> tuple[str, dict]:
    """Blocos vêm do export novo (Zotero manda); trechos escritos pelo usuário no .md
    antigo (texto fora dos blocos) são reinseridos depois do bloco que os precedia."""
    ohead, otoks = _tokenize(old)
    nhead, ntoks = _tokenize(new)
    # âncoras dos trechos do usuário: bloco/página anterior e bloco seguinte
    chunks = []
    prev = None
    for n, (kind, ref, lines) in enumerate(otoks):
        if kind in ("page", "block"):
            prev = (kind, ref)
        else:
            nxt = next((t[1] for t in otoks[n + 1:] if t[0] == "block"), None)
            chunks.append({"prev": prev, "next": nxt, "lines": lines})
    new_keys = {t[1] for t in ntoks if t[0] == "block"}
    new_pages = {t[1] for t in ntoks if t[0] == "page"}
    after: dict[tuple, list] = {}
    before: dict[str, list] = {}
    orphan = []
    for c in chunks:
        if c["prev"] and ((c["prev"][0] == "block" and c["prev"][1] in new_keys) or
                          (c["prev"][0] == "page" and c["prev"][1] in new_pages)):
            after.setdefault(c["prev"], []).append(c)
        elif c["next"] in new_keys:
            before.setdefault(c["next"], []).append(c)
        else:
            orphan.append(c)
    out = []
    # cabeçalho: mantém o antigo (edições do usuário), atualiza contagem/data com os do novo
    newvals = {}
    for ln in nhead:
        for key in ("anotacoes:", "extraido_em:"):
            if ln.startswith(key):
                newvals[key] = ln
        if _COUNTS.match(ln):
            newvals["_"] = ln
    for ln in (ohead or nhead):
        for key in ("anotacoes:", "extraido_em:"):
            if ln.startswith(key) and key in newvals:
                ln = newvals[key]
        if _COUNTS.match(ln) and "_" in newvals:
            ln = newvals["_"]
        out.append(ln)
    if not ohead:
        out = list(nhead)
    while out and not out[-1].strip():
        out.pop()
    out.append("")
    for kind, ref, lines in ntoks:
        if kind == "block":
            for c in before.get(ref, []):
                out += c["lines"] + [""]
        out += lines + [""]
        for c in after.get((kind, ref), []) if kind in ("page", "block") else []:
            out += c["lines"] + [""]
    if orphan:
        out += ["#### (trechos sem anotação de origem)", ""]
        for c in orphan:
            out += c["lines"] + [""]
    info = {"mantidos": len(chunks) - len(orphan), "orfaos": len(orphan)}
    return "\n".join(out).rstrip() + "\n", info


def backup_md(path: Path):
    bk = Path(os.environ.get("ZOTERO_ANOT_BACKUPS", Path.home() / ".cache" / "zotero-anot" / "backups"))
    bk.mkdir(parents=True, exist_ok=True)
    dst = bk / f"{dt.datetime.now():%Y%m%d-%H%M%S}-{path.name}"
    shutil.copy2(path, dst)
    return dst


def clean_orphan_images(imgdir: Path, keep: set[str]):
    n = 0
    if imgdir.is_dir():
        for f in imgdir.iterdir():
            if re.fullmatch(r"[A-Z0-9]{8}\.png", f.name) and f.name not in keep:
                f.unlink()
                n += 1
    return n


def _esc(t: str) -> str:
    return html.escape(" ".join((t or "").split()), quote=False)


def md_block(a: dict, att, imgdir, saida) -> list[str]:
    """Um bloco `> ...` por anotação: link + trecho/rótulo colorido (HTML) na 1ª linha,
    comentário logo abaixo. Formato lido de volta por `parse_export_md` (sync-md)."""
    hexv = (a["cor"] or "").lower()
    tipo = a["tipo"]
    if att and a["origem"] == "zotero":
        link = f"[↗](zotero://open-pdf/library/items/{att['key']}?page={a['pagina']}&annotation={a['key']})"
    elif att:
        link = f"[↗](zotero://open-pdf/library/items/{att['key']}?page={a['pagina']})"
    else:
        link = "↗"
    col = f"color:{hexv};" if hexv else ""
    if tipo == "highlight":
        head = f'<span style="background:{hexv}66;"><i>“{_esc(a["texto"])}”</i></span>' if hexv else f"<i>“{_esc(a['texto'])}”</i>"
    elif tipo == "underline":
        st = f"text-decoration:underline;text-decoration-color:{hexv};text-decoration-thickness:2px;" if hexv else "text-decoration:underline;"
        head = f'<span style="{st}"><i>“{_esc(a["texto"])}”</i></span>'
    else:
        rot = {"note": "nota", "text": "texto", "image": "imagem", "ink": "desenho"}.get(tipo, tipo)
        head = f'<span style="{col}font-weight:bold;">{rot}</span>'
        if tipo == "ink" and a.get("texto_coberto") and a["texto"]:
            head += f' <i>“{_esc(a["texto"])}”</i>'  # trecho do texto sob o desenho
    if a["tags"]:
        head += " <small>" + " ".join("#" + t.replace(" ", "_") for t in a["tags"]) + "</small>"
    out = [f"> {link} {head}  "]
    if a.get("imagem") and imgdir:
        try:
            rel = os.path.relpath(imgdir / a["imagem"], Path(saida).expanduser().parent) if saida else str(imgdir / a["imagem"])
        except ValueError:
            rel = str(imgdir / a["imagem"])
        out.append(f"> ![]({rel.replace(' ', '%20')})")
    if tipo in ("note", "text") and not a["comentario"] and a["texto"]:
        out += ["> " + ln if ln else ">" for ln in a["texto"].splitlines()]
    for ln in (a["comentario"] or "").splitlines():
        out.append("> " + ln if ln else ">")
    out.append("")
    return out


def to_markdown(pdf: Path, meta, att, anns, imgdir, saida) -> str:
    meta = meta or {}
    title = meta.get("title") or pdf.stem
    L = ["---", f'title: "{title.replace(chr(34), chr(39))}"']
    if meta.get("citationKey"):
        L.append(f"citekey: {meta['citationKey']}")
    if meta.get("key"):
        L.append(f"zotero_item: {meta['key']}")
    L += [f'pdf: "{pdf.name}"', f"anotacoes: {len(anns)}",
          f"extraido_em: {dt.datetime.now():%Y-%m-%d %H:%M}", "---", "",
          f"# Anotações — {title}", ""]
    cont: dict[str, int] = {}
    for a in anns:
        cont[a["tipo"]] = cont.get(a["tipo"], 0) + 1
    L += ["_" + ", ".join(f"{n} {t}" for t, n in cont.items()) + "_", ""]
    page = None
    for a in anns:
        if a["pagina"] != page:
            page = a["pagina"]
            lab = f" (impresso: {a['rotulo']})" if a["rotulo"] and str(a["rotulo"]) != str(page) else ""
            L.append(f"#### p. {page}{lab}")
            if att:
                L.append(f"[↗ abrir página](zotero://open-pdf/library/items/{att['key']}?page={page})")
            L.append("")
        L += md_block(a, att, imgdir, saida)
    return "\n".join(L).rstrip() + "\n"


# ------------------------------------------------------------- páginas
def cmd_pages(args):
    doc = pymupdf.open(Path(args.pdf).expanduser())
    print("indice_pdf\trotulo")
    for p in doc:
        print(f"{p.number + 1}\t{p.get_label()}")


def label_to_index(doc, label: str) -> int | None:
    for p in doc:
        if p.get_label() == str(label):
            return p.number + 1
    return None


# ------------------------------------------------------------------ info
def cmd_info(args):
    pdf = Path(args.pdf).expanduser()
    doc = pymupdf.open(pdf)
    data_dir, base = zotero_dirs(args)
    con = open_db(data_dir)
    att = resolve_attachment(con, data_dir, base, pdf)
    print(f"PDF: {pdf}  ({len(doc)} páginas)")
    print(f"Zotero data dir: {data_dir}\nBase de anexos: {base}")
    if not att:
        print("Zotero: NÃO encontrado como attachment")
    else:
        m = item_meta(con, att["parentItemID"] or att["itemID"])
        print(f"Zotero: attachment {att['key']} | item {m.get('key')} | {m.get('title')} | citekey={m.get('citationKey')}")
        z = zotero_annotations(con, att)
        c: dict[str, int] = {}
        for a in z:
            c[a["tipo"]] = c.get(a["tipo"], 0) + 1
        print(f"Anotações no banco do Zotero: {len(z)} {c}")
    e = pdf_annotations(doc)
    c = {}
    for a in e:
        c[a["tipo"]] = c.get(a["tipo"], 0) + 1
    print(f"Anotações embutidas no PDF: {len(e)} {c}")


# ------------------------------------------------------------------- add
def ann_id(spec: dict) -> str:
    """ID determinístico -> idempotência (mesma spec = mesma anotação)."""
    raw = "|".join(str(spec.get(k, "")) for k in ("page", "page_label", "type", "text", "comment", "occurrence"))
    return "zotanot-" + hashlib.sha1(raw.encode()).hexdigest()[:12]


def _page_tokens(page):
    """Tokens normalizados da página com suas caixas. Junta palavra quebrada
    por hífen no fim de linha ("charac-" + "teristics") num token só."""
    words = page.get_text("words")  # x0,y0,x1,y1,palavra,bloco,linha,n
    toks, i = [], 0
    while i < len(words):
        w = words[i]
        t = w[4]
        if t.endswith("-") and i + 1 < len(words) and len(t) > 2:
            n = words[i + 1]
            toks.append((norm(t[:-1] + n[4]), [w, n]))
            i += 2
            continue
        toks.append((norm(t), [w]))
        i += 1
    return toks


def _quads_from_words(ws):
    """Uma caixa por linha visual, cobrindo as palavras dessa linha."""
    lines: dict[tuple, pymupdf.Rect] = {}
    for w in ws:
        k = (w[5], w[6])
        r = pymupdf.Rect(w[:4])
        lines[k] = (lines[k] | r) if k in lines else r
    return [r.quad for r in lines.values()]


def find_quads(page, text: str, occurrence: int | None, context: str | None):
    """Localiza `text` na página por sequência de palavras (multi-linha ok)."""
    want = [norm(t) for t in text.split()]
    if not want:
        return None, "texto vazio"
    toks = _page_tokens(page)
    matches = []
    for i in range(len(toks) - len(want) + 1):
        if all(toks[i + j][0] == want[j] for j in range(len(want))):
            matches.append([w for j in range(len(want)) for w in toks[i + j][1]])
    if not matches:  # tolera pontuação colada: compara sem pontuação nas pontas
        strip = lambda x: re.sub(r"^\W+|\W+$", "", x)
        wl = [strip(x) for x in want]
        for i in range(len(toks) - len(want) + 1):
            if all(strip(toks[i + j][0]) == wl[j] for j in range(len(want))):
                matches.append([w for j in range(len(want)) for w in toks[i + j][1]])
    if not matches:
        return None, "texto não encontrado na página (confira hifenização/quebra; use trecho literal menor)"
    if context and len(matches) > 1:
        keep = []
        for m in matches:
            r = pymupdf.Rect(m[0][:4])
            box = pymupdf.Rect(r.x0 - 400, r.y0 - 40, r.x1 + 400, r.y1 + 40)
            if norm(context) in norm(page.get_textbox(box)):
                keep.append(m)
        matches = keep or matches
    if len(matches) > 1 and occurrence is None:
        return None, f"{len(matches)} ocorrências na página; informe 'occurrence' (1..{len(matches)}) ou 'context'"
    idx = (occurrence or 1) - 1
    if idx >= len(matches):
        return None, f"occurrence {occurrence} > {len(matches)} ocorrências"
    return _quads_from_words(matches[idx]), None


def existing_ids(doc) -> set[str]:
    ids = set()
    for p in doc:
        for a in p.annots() or []:
            try:
                v = doc.xref_get_key(a.xref, "NM")[1]
                ids.add(v.strip("()"))
            except Exception:
                pass
    return ids


def resolve_spec(doc, spec: dict):
    """Valida e localiza a anotação SEM alterar o PDF.
    Retorna ("ok", ann) ou ("erro", mensagem). ann é neutra: serve tanto ao
    backend nativo (Zotero) quanto ao embutido (PDF)."""
    typ = (spec.get("type") or "highlight").lower()
    if typ not in ("highlight", "underline", "note", "text"):
        return "erro", f"tipo '{typ}' não suportado (use highlight, underline, note, text)"
    if "page" in spec:
        pidx = int(spec["page"])
    elif "page_label" in spec:
        pidx = label_to_index(doc, spec["page_label"]) or 0
        if not pidx:
            return "erro", f"rótulo de página '{spec['page_label']}' inexistente (veja `pages`)"
    else:
        return "erro", "faltou 'page' (índice PDF, base 1) ou 'page_label'"
    if not 1 <= pidx <= len(doc):
        return "erro", f"página {pidx} fora do intervalo 1..{len(doc)}"
    spec = {**spec, "page": pidx}
    page = doc[pidx - 1]
    color = spec.get("color", "yellow" if typ != "text" else "red")
    hexv = NAME2HEX.get(str(color).lower(), color)
    if not str(hexv).startswith("#"):
        return "erro", f"cor desconhecida '{color}'"
    ann = {"id": ann_id(spec), "type": typ, "page": pidx, "color": hexv.lower(),
           "comment": spec.get("comment", "") or "", "text": re.sub(r"\s+", " ", spec.get("text", "") or "").strip()}
    if typ in ("highlight", "underline"):
        if not ann["text"]:
            return "erro", f"{typ} exige 'text' (trecho literal presente na página)"
        quads, err = find_quads(page, ann["text"], spec.get("occurrence"), spec.get("context"))
        if err:
            return "erro", err
        ann["quads"] = quads
    elif typ == "note":
        pt = spec.get("point")
        if not pt:  # sem ponto: ao lado do trecho, ou canto sup. esquerdo da margem
            pt = [page.rect.x0 + 20, page.rect.y0 + 20]
            if ann["text"]:
                q, _ = find_quads(page, ann["text"], spec.get("occurrence"), spec.get("context"))
                if q:
                    pt = [q[0].rect.x0 - 18, q[0].rect.y0]
        ann["point"] = list(pt)
    else:
        if not ann["comment"]:
            return "erro", "text exige 'comment' (conteúdo da caixa)"
        ann["rect"] = spec.get("rect") or [page.rect.x1 - 200, page.rect.y0 + 30, page.rect.x1 - 20, page.rect.y0 + 90]
        ann["fontsize"] = spec.get("fontsize", 11)
    return "ok", ann


def write_embedded(doc, ann: dict, author: str):
    """Grava a anotação resolvida como anotação PDF padrão."""
    page = doc[ann["page"] - 1]
    typ, rgb, comment = ann["type"], hex2rgb(ann["color"]), ann["comment"]
    now = pymupdf.get_pdf_now()
    if typ in ("highlight", "underline"):
        a = page.add_highlight_annot(quads=ann["quads"]) if typ == "highlight" else page.add_underline_annot(quads=ann["quads"])
        a.set_colors(stroke=rgb)
    elif typ == "note":
        a = page.add_text_annot(pymupdf.Point(*ann["point"]), comment or " ", icon="Note")
        a.set_colors(stroke=rgb)
    else:
        a = page.add_freetext_annot(pymupdf.Rect(*ann["rect"]), comment, fontsize=ann["fontsize"], text_color=rgb)
    a.set_info(content=comment, title=author, subject=typ, creationDate=now, modDate=now)
    a.update()
    doc.xref_set_key(a.xref, "NM", pymupdf.get_pdf_str(ann.get("nm") or ann["id"]))


def embed_zotero(doc, za: dict):
    """Anotação do banco do Zotero -> anotação embutida no PDF (todos os tipos)."""
    pos = za["_pos"]
    page = doc[pos["pageIndex"]]
    typ, rgb = za["tipo"], hex2rgb(za["cor"] or "#ffd400")
    comment = za["comentario"]
    if typ == "ink":
        strokes = ink_strokes(page, za)
        if not strokes:
            return False
        a = page.add_ink_annot([[(float(x), float(y)) for x, y in st] for st in strokes if len(st) > 1])
        a.set_border(width=pos.get("width", 2))
        a.set_colors(stroke=rgb)
    else:
        rects = [_norm_rect(r) for r in _rects_to_page(page, pos["rects"])]
        if typ in ("highlight", "underline"):
            qs = [r.quad for r in rects]
            a = page.add_highlight_annot(quads=qs) if typ == "highlight" else page.add_underline_annot(quads=qs)
            a.set_colors(stroke=rgb)
        elif typ == "note":
            a = page.add_text_annot(pymupdf.Point(rects[0].x0, rects[0].y0), comment or " ", icon="Note")
            a.set_colors(stroke=rgb)
        elif typ == "text":
            a = page.add_freetext_annot(rects[0], comment, fontsize=pos.get("fontSize", 14), text_color=rgb)
        else:  # image -> retângulo
            a = page.add_rect_annot(rects[0])
            a.set_border(width=1.5)
            a.set_colors(stroke=rgb)
    a.set_info(content=comment, title=za["autor"] or "Zotero", subject=typ)
    a.update()
    doc.xref_set_key(a.xref, "NM", pymupdf.get_pdf_str(za["key"]))
    return True


def save_pdf(doc, pdf: Path, saida: str | None):
    """Salva com backup (in-place) ou numa cópia."""
    if saida:
        out = Path(saida).expanduser()
        doc.save(str(out), garbage=0, deflate=True)
        print(f"-> {out}")
        return
    bdir = Path(os.environ.get("ZOTERO_ANOT_BACKUPS", Path.home() / ".cache" / "zotero-anot" / "backups"))
    bdir.mkdir(parents=True, exist_ok=True)
    bk = bdir / f"{pdf.stem}.{dt.datetime.now():%Y%m%d-%H%M%S}.pdf"
    shutil.copy2(pdf, bk)
    try:
        doc.saveIncr()  # só acrescenta ao final: rápido e não reescreve o PDF
    except Exception:
        tmp = pdf.with_suffix(".tmp.pdf")
        doc.save(str(tmp), garbage=0, deflate=True)
        tmp.replace(pdf)
    print(f"PDF gravado: {pdf}\nbackup: {bk}\nSe o PDF estiver aberto no Zotero, feche e reabra a aba do leitor.")


# --------------------------------------------------- entrada em Markdown
_COLOR = r"(?:\{(\w+|#[0-9a-fA-F]{6})\})?"


def parse_md(text: str) -> list[dict]:
    """Nota do Obsidian -> specs. Sintaxe (sob um título de página):
        ## p. 57            página do PDF (índice, base 1)   [aceita o título gerado por `extract`]
        ## pl. ix           página pelo rótulo impresso
        > trecho literal :: comentário {verde}     -> highlight
        _> trecho literal :: comentário            -> underline
        - :: comentário {azul}                     -> nota de página (ícone)
    Linhas sem '::' (ex.: as geradas por `extract`) são ignoradas."""
    specs, base = [], None
    for line in text.splitlines():
        m = re.match(r"^#{1,6}\s+(?:p\.|pág\.?|página)\s*(\d+)", line, re.I)
        if m:
            base = {"page": int(m.group(1))}
            continue
        m = re.match(r"^#{1,6}\s+pl\.\s*([^\s(]+)", line, re.I)
        if m:
            base = {"page_label": m.group(1)}
            continue
        if not base:
            continue
        m = re.match(r"^(_?)>\s*(.+?)\s*::\s*(.*?)\s*" + _COLOR + r"\s*$", line)
        if m:
            t = re.sub(r"^(==|\"|“)|(==|\"|”)$", "", m.group(2).strip()).strip()
            s = {**base, "type": "underline" if m.group(1) else "highlight", "text": t, "comment": m.group(3)}
            if m.group(4):
                s["color"] = m.group(4)
            specs.append(s)
            continue
        m = re.match(r"^[-*]\s*::\s*(.*?)\s*" + _COLOR + r"\s*$", line)
        if m and m.group(1):
            s = {**base, "type": "note", "comment": m.group(1)}
            if m.group(2):
                s["color"] = m.group(2)
            specs.append(s)
    return specs


def load_specs(src: str, name: str) -> list[dict]:
    if name.lower().endswith((".md", ".markdown")):
        return parse_md(src)
    try:
        specs = json.loads(src)
    except json.JSONDecodeError:
        return parse_md(src)  # stdin em markdown
    if isinstance(specs, dict):
        specs = specs.get("anotacoes", specs.get("annotations", [specs]))
    return specs


# ---------------------------------------------------------------- add
def add_native(args, doc, anns):
    import zotero_native as zn
    data_dir, base = zotero_dirs(args)
    con = open_db(data_dir)
    att = resolve_attachment(con, data_dir, base, Path(args.pdf).expanduser())
    if not att:
        die("este PDF não está registrado como attachment no Zotero (--base-dir correto?)")
    items = [zn.to_native(doc[a["page"] - 1], a, att["key"], args.autor, args.tag) for a in anns]
    reason = None
    key, uid = zn.creds()
    if not args.sem_extensao:
        token = zn.bridge_token()
        if token:
            try:
                info = zn.bridge_ping(token)
                res = zn.post_bridge(token, att["libraryID"], att["key"], items)
                print(f"[zotero/extensão v{info.get('version')}] {len(res['criadas'])} criadas, "
                      f"{len(res['puladas'])} já existiam, {len(res['falhas'])} falhas")
                for f in res["falhas"]:
                    print("  falha:", f)
                return len(res["falhas"]) == 0
            except zn.ApiError as e:
                print(f"[zotero/extensão] não usada: {e}")
    if args.offline:
        reason = "--offline"
    elif not key:
        reason = ("sem chave de API (crie em zotero.org/settings/keys com escrita e salve em "
                  f"{zn.CONFIG} como {{\"api_key\": \"...\"}} ou export ZOTERO_API_KEY)")
    else:
        try:
            prefix = zn.prefix_for(con, att["libraryID"], key, uid)
            res = zn.post_annotations(prefix, att["key"], items, key)
            print(f"[zotero/API] {len(res['criadas'])} criadas, {len(res['puladas'])} já existiam, {len(res['falhas'])} falhas")
            for f in res["falhas"]:
                print("  falha:", f)
            if res["criadas"]:
                print("Sincronize o Zotero (botão de sync) para vê-las no leitor.")
            return len(res["falhas"]) == 0
        except zn.ApiError as e:
            reason = str(e)
    print(f"[zotero/JS] API não usada: {reason}")
    js = zn.js_snippet(att["libraryID"], att["key"], items)
    out = Path.home() / ".cache" / "zotero-anot" / "ultimo_import.js"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(js, encoding="utf-8")
    copied = False
    clip = next(([c] + a for c, a in (("pbcopy", []), ("wl-copy", []), ("xclip", ["-selection", "clipboard"]), ("clip", []))
                 if shutil.which(c)), None)
    if clip and not os.environ.get("ZOTERO_ANOT_NO_CLIP"):
        import subprocess
        subprocess.run(clip, input=js.encode("utf-16-le" if clip[0] == "clip" else "utf-8"), check=False)
        copied = True
    print(f"Snippet salvo em {out}" + (" e copiado para a área de transferência." if copied else "."))
    print("No Zotero: Ferramentas > Developer > Run JavaScript > colar > Run.")
    return True


def add_pdf(args, pdf, doc, anns):
    have = existing_ids(doc)
    n = 0
    for a in anns:
        if a["id"] in have:
            print(f"[pdf/pulado] já existe ({a['id']})")
            continue
        write_embedded(doc, a, args.autor)
        n += 1
    print(f"[pdf] {n} embutidas")
    if n:
        save_pdf(doc, pdf, args.saida)
    return True


def cmd_add(args):
    pdf = Path(args.pdf).expanduser()
    if not pdf.exists():
        die(f"PDF não encontrado: {pdf}")
    src = sys.stdin.read() if args.spec == "-" else Path(args.spec).expanduser().read_text(encoding="utf-8")
    specs = load_specs(src, args.spec)
    if not specs:
        die("nenhuma anotação na entrada (JSON vazio, ou markdown sem linhas '> trecho :: comentário')")
    doc = pymupdf.open(pdf)
    plan = []
    for s in specs:
        try:
            plan.append((s, *resolve_spec(doc, s)))
        except Exception as ex:  # uma spec ruim não derruba o lote
            plan.append((s, "erro", f"{type(ex).__name__}: {ex}"))
    anns = [r for _, st, r in plan if st == "ok"]
    n_err = len(plan) - len(anns)
    for s, st, r in plan:
        if st == "ok":
            print(f"[ok] p.{r['page']} {r['type']} {r['id']} -> chave Zotero {__import__('zotero_native').zkey(r['id'])}")
        else:
            print(f"[erro] {r}  <- {json.dumps(s, ensure_ascii=False)[:100]}")
    print(f"\n{len(anns)} válidas, {n_err} erros | destino: {args.destino}")
    if args.dry_run or not anns:
        print("(nada gravado)")
        sys.exit(1 if n_err and not anns else 0)
    if n_err and args.estrito:
        die("--estrito: há erros; nada gravado", 1)
    ok = True
    if args.destino in ("zotero", "ambos"):
        ok = add_native(args, doc, anns) and ok
    if args.destino in ("pdf", "ambos"):
        ok = add_pdf(args, pdf, doc, anns) and ok
    if n_err or not ok:
        sys.exit(1)


_HEAD = re.compile(r"^> \[↗\]\(zotero://open-pdf/[^)]*annotation=([A-Z0-9]{8})\)(.*)$")
_SMALL = re.compile(r"<small>(.*?)</small>")


def parse_export_md(text: str) -> dict[str, dict]:
    """Nota exportada por `extract` -> {chave: {'comment': str, 'tags': set[str]}}.
    Comentário = linhas `> ...` após a 1ª linha do bloco (exceto imagens `> ![`)."""
    out: dict[str, dict] = {}
    cur = None
    for ln in text.splitlines() + [""]:
        m = _HEAD.match(ln)
        if m:
            if cur is not None:
                cur["comment"] = "\n".join(cur.pop("_c")).strip("\n")
            tags = set()
            for g in _SMALL.findall(m.group(2)):
                tags |= {t[1:] for t in g.split() if t.startswith("#")}
            cur = out.setdefault(m.group(1), {"comment": "", "tags": tags, "_c": []})
            continue
        if cur is None:
            continue
        if ln.startswith(">"):
            if not ln.startswith("> !["):
                cur["_c"].append(ln[2:] if ln.startswith("> ") else "")
        else:
            cur["comment"] = "\n".join(cur.pop("_c")).strip("\n")
            cur = None
    return out


def cmd_sync_md(args):
    import zotero_native as zn
    data_dir, base = zotero_dirs(args)
    con = open_db(data_dir)
    att = resolve_attachment(con, data_dir, base, Path(args.pdf).expanduser())
    if not att:
        die("este PDF não está registrado como attachment no Zotero")
    want = parse_export_md(Path(args.md).expanduser().read_text(encoding="utf-8"))
    changes = []
    for a in zotero_annotations(con, att):
        w = want.get(a["key"])
        if not w:
            continue
        ch = {"key": a["key"]}
        if w["comment"] != a["comentario"].strip("\n"):
            ch["comment"] = w["comment"]
        norm_tag = lambda t: t.replace(" ", "_")
        if {norm_tag(t) for t in a["tags"]} != w["tags"]:
            keep = {norm_tag(t): t for t in a["tags"]}
            ch["tags"] = [keep.get(t, t) for t in sorted(w["tags"])]
        if len(ch) > 1:
            changes.append(ch)
            print(f"[mudou] {a['key']} p.{a['pagina']}: " + ", ".join(k for k in ch if k != "key"))
    if not changes:
        print("nada a sincronizar.")
        return
    if args.dry_run:
        print(f"{len(changes)} alterações (nada gravado)")
        return
    token = zn.bridge_token()
    if not token:
        die("sync-md precisa da extensão zotobs-bridge: rode `zotobs bridge-token` e instale o .xpi")
    try:
        res = zn.update_bridge(token, att["libraryID"], att["key"], changes)
    except zn.ApiError as e:
        die(f"{e} (a extensão v0.1.0+ está instalada e o Zotero aberto?)")
    print(f"[zotero/extensão] {len(res['atualizadas'])} atualizadas, {len(res['inalteradas'])} inalteradas, {len(res['falhas'])} falhas")
    for f in res["falhas"]:
        print("  falha:", f)
    if res["falhas"]:
        sys.exit(1)


def cmd_bridge_token(args):
    import zotero_native as zn
    new = zn.bridge_token() is None
    zn.bridge_token(create=True)
    print(f"token {'criado' if new else 'já existia'} em {zn.TOKEN_FILE} (modo 600)")
    try:
        info = zn.bridge_ping(zn.bridge_token())
        print(f"extensão ativa: v{info.get('version')}, Zotero {info.get('zotero')}")
    except zn.ApiError as e:
        print(f"extensão não respondeu ({e}); instale o .xpi e abra o Zotero.")


def cmd_embed(args):
    """Anotações do banco do Zotero -> anotações embutidas no PDF."""
    pdf = Path(args.pdf).expanduser()
    data_dir, base = zotero_dirs(args)
    con = open_db(data_dir)
    att = resolve_attachment(con, data_dir, base, pdf)
    if not att:
        die("este PDF não está registrado como attachment no Zotero")
    zs = zotero_annotations(con, att)
    if args.tipos:
        want = {t.strip() for t in args.tipos.split(",")}
        zs = [z for z in zs if z["tipo"] in want]
    doc = pymupdf.open(pdf)
    have = existing_ids(doc)
    sigs = {(a["pagina"], a["tipo"], norm(a["texto"] or a["comentario"])) for a in pdf_annotations(doc)}
    n = 0
    for z in zs:
        if z["key"] in have or (z["pagina"], z["tipo"], norm(z["texto"] or z["comentario"])) in sigs:
            continue  # já embutida (mesma chave, ou mesmo conteúdo com outra chave)
        if embed_zotero(doc, z):
            n += 1
    print(f"{n} anotações do Zotero embutidas no PDF ({len(zs) - n} já existiam/puladas)")
    if n:
        save_pdf(doc, pdf, args.saida)


def cmd_strip(args):
    """Remove anotações embutidas (padrão: só as criadas por este script)."""
    pdf = Path(args.pdf).expanduser()
    doc = pymupdf.open(pdf)
    n = 0
    for page in doc:
        for a in list(page.annots() or []):
            try:
                nm = doc.xref_get_key(a.xref, "NM")[1].strip("()")
            except Exception:
                nm = ""
            if nm.startswith("zotanot-") or args.todas:
                page.delete_annot(a)
                n += 1
    print(f"{n} anotações embutidas removidas")
    if n and not args.dry_run:
        save_pdf(doc, pdf, args.saida)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(prog="zotero_anot", description=__doc__.split("\n\n")[0])
    ap.add_argument("--zotero-dir", help="pasta de dados do Zotero (padrão: prefs.js ou ~/Zotero)")
    ap.add_argument("--base-dir", help="pasta base de anexos vinculados (padrão: prefs.js)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("extract", help="anotações -> Markdown/JSON")
    e.add_argument("pdf")
    e.add_argument("-o", "--saida", help="arquivo .md (ou .json com --json); padrão: stdout")
    e.add_argument("--fonte", choices=["auto", "zotero", "pdf", "ambas"], default="auto",
                   help="auto/ambas = banco do Zotero + anotações embutidas (sem duplicar)")
    e.add_argument("--json", action="store_true", help="saída JSON (bom para agentes)")
    e.add_argument("--tipos", help="filtro: highlight,underline,note,text,image,ink")
    e.add_argument("--paginas", help="faixa de páginas PDF, ex.: 80-90")
    e.add_argument("--se-existe", choices=["mesclar", "sobrescrever"], default="mesclar",
                   help="se o .md já existe: mesclar (padrão; mantém o que você escreveu entre os blocos) ou sobrescrever")
    e.add_argument("--imagens", help="pasta onde salvar recortes PNG de anotações image/ink")
    e.set_defaults(fn=cmd_extract)

    a = sub.add_parser("add", help="inclui anotações (JSON ou Markdown do Obsidian)")
    a.add_argument("pdf")
    a.add_argument("spec", help="arquivo .json ou .md com as anotações, ou - para stdin")
    a.add_argument("--destino", choices=["zotero", "pdf", "ambos"], default="zotero",
                   help="zotero (padrão): anotação nativa via Web API, com fallback JS; pdf: embutida no arquivo")
    a.add_argument("--offline", action="store_true", help="não usa a API: gera o snippet JS para colar no Zotero")
    a.add_argument("--sem-extensao", action="store_true",
                   help="não tenta a extensão zotobs-bridge (vai direto para Web API/snippet)")
    a.add_argument("--tag", default="agente", help="tag aplicada às anotações nativas ('' = nenhuma)")
    a.add_argument("--autor", default=AUTHOR_DEFAULT, help="nome do autor gravado nas anotações")
    a.add_argument("--dry-run", action="store_true", help="só valida/mostra o que faria")
    a.add_argument("--estrito", action="store_true", help="não grava nada se alguma spec falhar")
    a.add_argument("--saida", help="(destino pdf) grava numa cópia em vez de alterar o PDF original")
    a.set_defaults(fn=cmd_add)

    m = sub.add_parser("embed", help="converte anotações do Zotero em anotações embutidas no PDF")
    m.add_argument("pdf")
    m.add_argument("--tipos", help="filtro: highlight,underline,note,text,image,ink")
    m.add_argument("--saida", help="grava numa cópia em vez de alterar o PDF original")
    m.set_defaults(fn=cmd_embed)

    r = sub.add_parser("strip", help="remove anotações embutidas (padrão: só as criadas por este script)")
    r.add_argument("pdf")
    r.add_argument("--todas", action="store_true", help="remove TODAS as anotações embutidas")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--saida")
    r.set_defaults(fn=cmd_strip)

    sy = sub.add_parser("sync-md", help="envia ao Zotero edições de comentário/tags feitas na nota exportada (.md)")
    sy.add_argument("pdf")
    sy.add_argument("md", help="nota gerada por `extract` (com os links zotero://…annotation=KEY)")
    sy.add_argument("--dry-run", action="store_true")
    sy.set_defaults(fn=cmd_sync_md)

    t = sub.add_parser("bridge-token", help="cria/mostra o token de pareamento com a extensão zotobs-bridge")
    t.set_defaults(fn=cmd_bridge_token)

    i = sub.add_parser("info", help="item do Zotero + contagens")
    i.add_argument("pdf")
    i.set_defaults(fn=cmd_info)

    p = sub.add_parser("pages", help="índice PDF <-> rótulo da página")
    p.add_argument("pdf")
    p.set_defaults(fn=cmd_pages)

    args = ap.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent))  # zotero_native.py
    args.fn(args)


if __name__ == "__main__":
    main()
