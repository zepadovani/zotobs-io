"""Backends de escrita NATIVA (anotações no banco do Zotero, não no PDF).

  1. Web API (api.zotero.org): cria itens `annotation` filhos do attachment;
     o Zotero desktop os baixa no próximo sync. Precisa de chave com escrita.
  2. Extensão local (zotobs-bridge): POST em 127.0.0.1:23119/zotobs/import;
     sem rede nem chave de API, exige token pareado (bridge_token).
  3. Snippet JS: gera código para colar em Ferramentas > Developer > Run
     JavaScript (usa a API interna do Zotero; sem rede nem chave).

As duas usam a MESMA chave determinística por anotação (zkey), então rodar
um backend e depois o outro não duplica nada.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import urllib.error
import urllib.request
from pathlib import Path

import pymupdf

API = "https://api.zotero.org"
ALPHABET = "23456789ABCDEFGHIJKLMNPQRSTUVWXYZ"  # alfabeto de chaves do Zotero
CONFIG = Path(os.environ.get("ZOTERO_ANOT_CONFIG", Path.home() / ".config" / "zotero-anot" / "config.json"))


def zkey(aid: str) -> str:
    """Chave Zotero (8 chars) determinística a partir do id da anotação."""
    d = hashlib.sha1(aid.encode()).digest()
    return "".join(ALPHABET[b % len(ALPHABET)] for b in d[:8])


# ------------------------------------------------------- posição / sortIndex
def _pdf_rect(page, r: pymupdf.Rect) -> list[float]:
    """Rect em coords de página (topo-esq.) -> coords PDF do Zotero (base-esq.)."""
    q = pymupdf.Rect(r) * ~page.transformation_matrix
    x0, x1 = sorted((q.x0, q.x1))
    y0, y1 = sorted((q.y0, q.y1))
    return [round(v, 3) for v in (x0, y0, x1, y1)]


def _char_offset(page, r: pymupdf.Rect) -> int:
    n = 0
    for w in page.get_text("words"):
        if pymupdf.Rect(w[:4]).intersects(r) or w[1] > r.y1:
            return n
        n += len(w[4]) + 1
    return n


def sort_index(page, r: pymupdf.Rect, with_offset: bool) -> str:
    off = _char_offset(page, r) if with_offset else 0
    return f"{page.number:05d}|{off:06d}|{max(int(r.y0), 0):05d}"


def to_native(page, ann: dict, att_key: str, author: str, tag: str | None) -> dict:
    """ann (resolvido por zotero_anot.resolve_spec) -> item JSON da Web API."""
    typ = ann["type"]
    idx = page.number
    if typ in ("highlight", "underline"):
        rects_m = [q.rect for q in ann["quads"]]
        pos = {"pageIndex": idx, "rects": [_pdf_rect(page, r) for r in rects_m]}
        first, off = rects_m[0], True
    elif typ == "note":
        pt = pymupdf.Point(*ann["point"])
        first = pymupdf.Rect(pt.x, pt.y, pt.x + 22, pt.y + 22)
        pos, off = {"pageIndex": idx, "rects": [_pdf_rect(page, first)]}, False
    else:  # text
        first = pymupdf.Rect(*ann["rect"])
        pos = {"pageIndex": idx, "fontSize": ann.get("fontsize", 14), "rotation": 0,
               "rects": [_pdf_rect(page, first)]}
        off = False
    item = {
        "key": zkey(ann["id"]),
        "itemType": "annotation",
        "parentItem": att_key,
        "annotationType": typ,
        "annotationAuthorName": author,
        "annotationComment": ann.get("comment", ""),
        "annotationColor": ann["color"],
        "annotationPageLabel": page.get_label() or str(idx + 1),
        "annotationSortIndex": sort_index(page, first, off),
        "annotationPosition": json.dumps(pos, separators=(",", ":")),
        "tags": [{"tag": tag}] if tag else [],
    }
    if typ in ("highlight", "underline"):
        item["annotationText"] = ann.get("text", "")
    return item


# --------------------------------------------------------------- Web API
class ApiError(Exception):
    pass


def creds() -> tuple[str | None, str | None]:
    key, uid = os.environ.get("ZOTERO_API_KEY"), os.environ.get("ZOTERO_USER_ID")
    if CONFIG.exists():
        try:
            c = json.loads(CONFIG.read_text())
            key, uid = key or c.get("api_key"), uid or c.get("user_id")
        except Exception:
            pass
    return key, uid


def _req(method: str, url: str, key: str, body=None, headers=None, timeout=20):
    h = {"Zotero-API-Key": key, "Zotero-API-Version": "3", **(headers or {})}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    rq = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(rq, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        raise ApiError(f"HTTP {e.code} em {method} {url.replace(API, '')}: {e.read().decode()[:300]}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ApiError(f"sem rede/API inacessível: {e}")


def user_id(key: str) -> str:
    _, txt = _req("GET", f"{API}/keys/{key}", key)
    return str(json.loads(txt)["userID"])


def prefix_for(con, library_id: int, key: str, uid: str | None) -> str:
    row = con.execute("SELECT type FROM libraries WHERE libraryID=?", (library_id,)).fetchone()
    if row and row[0] == "group":
        gid = con.execute("SELECT groupID FROM groups WHERE libraryID=?", (library_id,)).fetchone()[0]
        return f"/groups/{gid}"
    return f"/users/{uid or user_id(key)}"


def post_annotations(prefix: str, att_key: str, items: list[dict], key: str) -> dict:
    """Cria só as que ainda não existem. Retorna {'criadas','puladas','falhas'}."""
    _, txt = _req("GET", f"{API}{prefix}/items/{att_key}/children?itemType=annotation&format=keys&limit=1000", key)
    have = set(txt.split())
    new = [i for i in items if i["key"] not in have]
    out = {"criadas": [], "puladas": [i["key"] for i in items if i["key"] in have], "falhas": []}
    for n in range(0, len(new), 50):
        batch = new[n:n + 50]
        _, txt = _req("POST", f"{API}{prefix}/items", key, body=[{**i, "version": 0} for i in batch],
                      headers={"Zotero-Write-Token": secrets.token_hex(16)})
        res = json.loads(txt)
        for i in res.get("successful", {}).values():
            out["criadas"].append(i.get("key") or i.get("data", {}).get("key"))
        for k, f in res.get("failed", {}).items():
            out["falhas"].append(f"{batch[int(k)]['key']}: {f.get('message')}")
    return out


# ------------------------------------------------- extensão local (bridge)
BRIDGE = os.environ.get("ZOTOBS_BRIDGE_URL", "http://127.0.0.1:23119")
TOKEN_FILE = CONFIG.parent / "bridge_token"


def bridge_token(create: bool = False) -> str | None:
    """Token de pareamento com a extensão (a extensão lê o mesmo arquivo)."""
    if TOKEN_FILE.exists():
        t = TOKEN_FILE.read_text().strip()
        if t:
            return t
    if not create:
        return None
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    t = secrets.token_urlsafe(32)
    fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(t + "\n")
    return t


def _bridge(method: str, path: str, token: str, body=None, timeout=15) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    h = {"X-Zotobs-Token": token}
    if data is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(BRIDGE + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        raise ApiError(f"extensão respondeu {e.code}: {detail}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ApiError(f"extensão inacessível: {e}")


def bridge_ping(token: str) -> dict:
    return _bridge("GET", "/zotobs/ping", token, timeout=2)


def post_bridge(token: str, library_id: int, att_key: str, items: list[dict]) -> dict:
    """Mesmo retorno de post_annotations: {'criadas','puladas','falhas'}."""
    return _bridge("POST", "/zotobs/import", token,
                   {"library": library_id, "attachment": att_key, "items": items}, timeout=60)


def update_bridge(token: str, library_id: int, att_key: str, items: list[dict]) -> dict:
    """items: [{'key', 'comment'?, 'tags'?}] -> {'atualizadas','inalteradas','falhas'}."""
    return _bridge("POST", "/zotobs/update", token,
                   {"library": library_id, "attachment": att_key, "items": items}, timeout=60)


# ------------------------------------------------------------- snippet JS
def js_snippet(library_id: int, att_key: str, items: list[dict]) -> str:
    data = json.dumps(items, ensure_ascii=False, indent=1)
    return f"""// zotero-anot: {len(items)} anotações -> attachment {att_key}
// Zotero > Ferramentas > Developer > Run JavaScript > colar > Run
const LIB = {library_id}, ATT = "{att_key}";
const items = {data};
const att = Zotero.Items.getByLibraryAndKey(LIB, ATT);
if (!att) return "attachment " + ATT + " não encontrado na biblioteca " + LIB;
let ok = 0, skip = 0;
for (const d of items) {{
  if (Zotero.Items.getByLibraryAndKey(LIB, d.key)) {{ skip++; continue; }}
  // mesma rotina que o leitor do Zotero usa para criar anotações
  await Zotero.Annotations.saveFromJSON(att, {{
    key: d.key,
    type: d.annotationType,
    authorName: d.annotationAuthorName || "",
    text: d.annotationText,
    comment: d.annotationComment || "",
    color: d.annotationColor,
    pageLabel: d.annotationPageLabel,
    sortIndex: d.annotationSortIndex,
    position: JSON.parse(d.annotationPosition),
    tags: (d.tags || []).map(t => ({{ name: t.tag }})),
  }});
  ok++;
}}
return "criadas: " + ok + ", puladas (já existiam): " + skip;
"""
