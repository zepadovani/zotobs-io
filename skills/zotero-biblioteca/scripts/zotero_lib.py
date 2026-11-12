#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""zotero_lib — busca na biblioteca do Zotero e organização em coleções (subpastas).

Subcomandos:
  libraries    lista as bibliotecas (pessoal e de grupos)
  collections  árvore de coleções, com chaves e contagens
  search       busca itens por tema (título, resumo, tags, autores, notas,
               anotações, texto completo) e mostra por que cada um casou
  show         detalhes de itens (resumo, tags, coleções, link zotero://)
  collection   create / add: cria subcoleções e coloca itens nelas

Só stdlib. Lê o banco numa cópia (o Zotero o mantém travado) e NUNCA escreve no
zotero.sqlite: criar coleções e adicionar itens passa pelo plugin zotobs-bridge
(>= 0.1.2) ou, sem ele, por um snippet JS para colar em Ferramentas > Developer
> Run JavaScript. Só cria coleções e adiciona itens a elas; nada é removido.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

KEY_RE = re.compile(r"^[0-9A-Z]{8}$")
NOT_REGULAR = ("attachment", "note", "annotation")
BATCH = 200  # itens por requisição ao plugin (ele aceita até 500)
CONFIG = Path(os.environ.get("ZOTERO_ANOT_CONFIG", Path.home() / ".config" / "zotero-anot" / "config.json"))
TOKEN_FILE = CONFIG.parent / "bridge_token"
BRIDGE = os.environ.get("ZOTOBS_BRIDGE_URL", "http://127.0.0.1:23119")

# Mesmo código que roda dentro do plugin (extension/bootstrap.js); um teste
# garante que os dois continuam idênticos.
JS_CORE = r'''// >>> zotobs-collection-op (manter idêntico a JS_CORE em skills/zotero-biblioteca/scripts/zotero_lib.py)
async function zotobsCollectionOp(req) {
  const lib = req.library;
  const library = Zotero.Libraries.get(lib);
  if (!library) throw new Error("biblioteca " + lib + " não encontrada");
  if (!library.editable) throw new Error("a biblioteca " + lib + " é somente leitura");
  const out = { colecao: null, colecoes_criadas: [], adicionados: [], ja_estavam: [], falhas: [] };
  const live = (k) => {
    const c = Zotero.Collections.getByLibraryAndKey(lib, k);
    return c && !c.deleted ? c : null;
  };
  let col = null;
  if (req.collection) {
    col = live(req.collection);
    if (!col) throw new Error("coleção " + req.collection + " não encontrada na biblioteca " + lib);
  } else if (req.create && Array.isArray(req.create.names) && req.create.names.length) {
    let parent = null;
    if (req.create.parent) {
      parent = live(req.create.parent);
      if (!parent) throw new Error("coleção-mãe " + req.create.parent + " não encontrada na biblioteca " + lib);
    }
    for (const raw of req.create.names) {
      const name = String(raw).trim();
      if (!name) throw new Error("nome de coleção vazio");
      const pid = parent ? parent.id : null;
      let next = Zotero.Collections.getByLibrary(lib, true)
        .find((c) => (c.parentID || null) === pid && c.name === name);
      if (!next) {
        next = new Zotero.Collection();
        next.libraryID = lib;
        next.name = name;
        if (parent) next.parentID = parent.id;
        await next.saveTx();
        out.colecoes_criadas.push(next.key);
      }
      parent = next;
    }
    col = parent;
  } else {
    throw new Error("informe 'collection' ou 'create'");
  }
  out.colecao = col.key;
  for (const key of req.items) {
    try {
      if (!/^[A-Z0-9]{8}$/.test(key || "")) throw new Error("chave inválida");
      const it = Zotero.Items.getByLibraryAndKey(lib, key);
      if (!it || it.deleted) throw new Error("item não encontrado");
      if (!it.isRegularItem()) throw new Error("não é um item principal (anexo, nota ou anotação)");
      await it.loadAllData();
      if (it.inCollection(col.id)) { out.ja_estavam.push(key); continue; }
      it.addToCollection(col.id);
      await it.saveTx();
      out.adicionados.push(key);
    } catch (e) {
      out.falhas.push((key || "?") + ": " + e.message);
    }
  }
  return out;
}
// <<< zotobs-collection-op'''


def die(msg: str, code: int = 2):
    print(f"erro: {msg}", file=sys.stderr)
    sys.exit(code)


def fold(s: str | None) -> str:
    """minúsculas, sem acentos, espaços normalizados (busca insensível a ambos)."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.casefold()).strip()


def chunks(seq, n=500):
    seq = list(seq)
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


# ------------------------------------------------------------ config do Zotero
# (mesma lógica de zotero_anot.py; duplicada de propósito: a skill é autônoma)
def _prefs() -> dict[str, str]:
    out: dict[str, str] = {}
    roots = [Path(os.environ["APPDATA"]) / "Zotero" / "Zotero" / "Profiles"] if os.environ.get("APPDATA") else []
    files = (list(Path.home().glob("Library/Application Support/Zotero/Profiles/*/prefs.js"))
             + [q for r in roots for q in r.glob("*/prefs.js")] + list(Path.home().glob(".zotero/zotero/*/prefs.js")))
    for p in files:
        for m in re.finditer(r'user_pref\("([^"]+)",\s*"?([^")]*)"?\);', p.read_text(errors="ignore")):
            out[m.group(1)] = m.group(2)
    return out


def zotero_dir(args) -> Path:
    data = args.zotero_dir or os.environ.get("ZOTERO_DATA_DIR") or _prefs().get("extensions.zotero.dataDir") or str(Path.home() / "Zotero")
    return Path(data).expanduser()


def open_db(data_dir: Path, name: str = "zotero.sqlite", required: bool = True):
    """Zotero mantém o banco travado enquanto aberto: trabalha numa cópia
    (banco + WAL) em cache, refeita quando a origem muda."""
    src = data_dir / name
    if not src.exists():
        if required:
            die(f"{name} não encontrado em {data_dir} (use --zotero-dir)")
        return None
    cache = Path(tempfile.gettempdir()) / "zotero_anot_cache"
    cache.mkdir(exist_ok=True)
    dst = cache / f"{hashlib.md5(str(src).encode()).hexdigest()[:8]}.sqlite"
    wal = Path(str(src) + "-wal")
    newest = max(p.stat().st_mtime for p in (src, wal) if p.exists())
    if not dst.exists() or dst.stat().st_mtime < newest:
        for suf in ("", "-wal", "-shm"):
            Path(str(dst) + suf).unlink(missing_ok=True)
        shutil.copy2(src, dst)
        if wal.exists():
            shutil.copy2(wal, str(dst) + "-wal")
    con = sqlite3.connect(str(dst))
    con.row_factory = sqlite3.Row
    return con


def has_table(con, name: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE name=?", (name,)).fetchone() is not None


# --------------------------------------------------------------- bibliotecas
def list_libraries(con) -> list[dict]:
    out = []
    for r in con.execute("SELECT l.libraryID AS id, l.type, l.editable, g.groupID AS gid, g.name FROM libraries l "
                         "LEFT JOIN groups g USING(libraryID) WHERE l.type IN ('user','group') ORDER BY l.libraryID"):
        out.append({"id": r["id"], "type": r["type"], "editable": bool(r["editable"]), "group_id": r["gid"],
                    "name": "Minha biblioteca" if r["type"] == "user" else (r["name"] or f"grupo {r['gid']}")})
    return out


def resolve_library(con, spec: str | None) -> dict:
    libs = list_libraries(con)
    if not spec or fold(spec) in ("user", "pessoal", "personal"):
        hit = [l for l in libs if l["type"] == "user"]
    elif spec.isdigit():
        hit = [l for l in libs if l["id"] == int(spec)]
    else:
        f = fold(spec)
        hit = [l for l in libs if fold(l["name"]) == f] or [l for l in libs if f in fold(l["name"])]
    if len(hit) != 1:
        opts = "\n".join(f"  {l['id']:>3}  {l['name']}" for l in libs)
        die(f"biblioteca '{spec}' " + ("é ambígua" if hit else "não encontrada") + f". Use o número ou o nome:\n{opts}")
    return hit[0]


# ----------------------------------------------------------------- coleções
def load_collections(con, lib: int) -> dict:
    """Coleções vivas (fora da lixeira) de uma biblioteca, com caminho e filhos."""
    trash = "AND collectionID NOT IN (SELECT collectionID FROM deletedCollections)" if has_table(con, "deletedCollections") else ""
    rows = con.execute("SELECT collectionID, collectionName, parentCollectionID, key FROM collections "
                       f"WHERE libraryID=? {trash}", (lib,)).fetchall()
    cols = {r[0]: {"id": r[0], "name": r[1], "parent": r[2], "key": r[3], "children": []} for r in rows}
    roots = []
    for c in cols.values():
        if c["parent"] is None:
            roots.append(c)
        elif c["parent"] in cols:
            cols[c["parent"]]["children"].append(c)
        # pai na lixeira: a coleção fica inalcançável e é ignorada

    reach: dict[int, dict] = {}

    def walk(c, names):
        c["names"] = names + [c["name"]]
        c["path"] = "/".join(c["names"])
        reach[c["id"]] = c
        c["children"].sort(key=lambda k: fold(k["name"]))
        for k in c["children"]:
            walk(k, c["names"])

    roots.sort(key=lambda k: fold(k["name"]))
    for r in roots:
        walk(r, [])
    return {"all": reach, "roots": roots}


def subtree(c: dict) -> list[dict]:
    out = [c]
    for k in c["children"]:
        out += subtree(k)
    return out


def find_collections(tree: dict, spec: str) -> list[dict]:
    """Chave (8 caracteres), nome, caminho 'A/B' (casa o final do caminho) ou
    '/A/B' (a partir da raiz). Insensível a maiúsculas e acentos."""
    spec = spec.strip()
    if KEY_RE.match(spec):
        hit = [c for c in tree["all"].values() if c["key"] == spec]
        if hit:
            return hit
    segs = [fold(s) for s in spec.strip("/").split("/") if s.strip()]
    if not segs:
        return []
    rooted = spec.startswith("/")
    out = []
    for c in tree["all"].values():
        names = [fold(n) for n in c["names"]]
        if (names == segs) if rooted else (names[-len(segs):] == segs):
            out.append(c)
    return sorted(out, key=lambda c: c["path"])


def one_collection(tree: dict, spec: str, what: str = "coleção") -> dict:
    hit = find_collections(tree, spec)
    if not hit:
        die(f"{what} '{spec}' não encontrada (veja `zotobs collections --filter TEXTO`)")
    if len(hit) > 1:
        lst = "\n".join(f"  [{c['key']}] /{c['path']}" for c in hit)
        die(f"{what} '{spec}' é ambígua; use a chave ou o caminho completo com '/' inicial:\n{lst}")
    return hit[0]


def plan_target(tree: dict, spec: str, parent_spec: str | None, create: bool) -> dict:
    """Resolve o destino: {'col': coleção existente | None, 'parent': coleção-mãe | None, 'create': [nomes]}."""
    names = [n.strip() for n in spec.strip().strip("/").split("/") if n.strip()]
    if not names:
        die("destino vazio")
    node = None
    if parent_spec:
        node = one_collection(tree, parent_spec, "coleção-mãe")
    else:
        hit = find_collections(tree, spec)
        if hit:
            return {"col": one_collection(tree, spec), "parent": None, "create": []}
    for i, n in enumerate(names):
        kids = node["children"] if node else tree["roots"]
        same = [k for k in kids if fold(k["name"]) == fold(n)]
        if len(same) > 1:
            die(f"há {len(same)} coleções chamadas '{n}' no mesmo nível; use a chave de uma delas")
        if not same:
            if not create:
                onde = f"em /{node['path']}" if node else "na raiz"
                die(f"a coleção '{'/'.join(names[i:])}' não existe {onde}; use --create para criá-la")
            return {"col": None, "parent": node, "create": names[i:]}
        node = same[0]
    return {"col": node, "parent": None, "create": []}


# -------------------------------------------------------------------- itens
FIELDS = ("title", "shortTitle", "abstractNote", "date", "publicationTitle", "bookTitle", "proceedingsTitle",
          "blogTitle", "websiteTitle", "series", "journalAbbreviation", "publisher", "DOI", "url", "citationKey")
PUB_FIELDS = ("publicationTitle", "bookTitle", "proceedingsTitle", "blogTitle", "websiteTitle")


def strip_html(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", s or ""))


def load_items(con, lib: int, tree: dict, notes: bool = False, annots: bool = False) -> dict[int, dict]:
    """Itens principais (sem anexos, notas e anotações; sem a lixeira) da biblioteca."""
    items: dict[int, dict] = {}
    for r in con.execute(
            "SELECT i.itemID, i.key, it.typeName, i.dateAdded FROM items i JOIN itemTypes it USING(itemTypeID) "
            "WHERE i.libraryID=? AND it.typeName NOT IN ('attachment','note','annotation') "
            "AND i.itemID NOT IN (SELECT itemID FROM deletedItems)", (lib,)):
        items[r[0]] = {"id": r[0], "key": r[1], "type": r[2], "added": r[3], "f": {}, "creators": [],
                       "tags": [], "cols": set(), "notes": [], "annots": [], "_fold": {}}
    ph = ",".join("?" * len(FIELDS))
    for r in con.execute(f"SELECT d.itemID, f.fieldName, v.value FROM itemData d JOIN fields f USING(fieldID) "
                         f"JOIN itemDataValues v USING(valueID) WHERE f.fieldName IN ({ph})", FIELDS):
        if r[0] in items:
            items[r[0]]["f"][r[1]] = r[2]
    for r in con.execute("SELECT ic.itemID, c.firstName, c.lastName, c.fieldMode FROM itemCreators ic "
                         "JOIN creators c USING(creatorID) ORDER BY ic.itemID, ic.orderIndex"):
        if r[0] in items:
            items[r[0]]["creators"].append((r[1] or "", r[2] or "", r[3]))
    for r in con.execute("SELECT it.itemID, t.name FROM itemTags it JOIN tags t USING(tagID)"):
        if r[0] in items:
            items[r[0]]["tags"].append(r[1])
    for cid, iid in con.execute("SELECT collectionID, itemID FROM collectionItems"):
        if cid in tree["all"] and iid in items:
            items[iid]["cols"].add(cid)
    if notes:
        for r in con.execute("SELECT parentItemID, note FROM itemNotes WHERE parentItemID IS NOT NULL"):
            if r[0] in items:
                items[r[0]]["notes"].append(strip_html(r[1]))
    if annots:
        for r in con.execute("SELECT att.parentItemID, a.text, a.comment FROM itemAnnotations a "
                             "JOIN itemAttachments att ON att.itemID=a.parentItemID WHERE att.parentItemID IS NOT NULL"):
            if r[0] in items:
                items[r[0]]["annots"] += [x for x in (r[1], r[2]) if x]
    return items


def title_of(it: dict) -> str:
    return it["f"].get("title") or it["f"].get("shortTitle") or "(sem título)"


def year_of(it: dict) -> int | None:
    m = re.match(r"(\d{4})", it["f"].get("date", ""))
    return int(m.group(1)) or None if m else None


def pub_of(it: dict) -> str:
    return next((it["f"][k] for k in PUB_FIELDS if it["f"].get(k)), "")


def creators_of(it: dict, n: int | None = 3) -> str:
    names = [(l if m == 1 or not f else f"{l}, {f}") for f, l, m in it["creators"]]
    short = [(l or f) for f, l, m in it["creators"]]
    if n is None:
        return "; ".join(names)
    return "; ".join(short[:n]) + (" et al." if len(short) > n else "")


def paths_of(it: dict, tree: dict) -> list[str]:
    return sorted("/" + tree["all"][c]["path"] for c in it["cols"])


def record(it: dict, tree: dict, score: int = 0, matched: dict | None = None) -> dict:
    abstract = re.sub(r"\s+", " ", it["f"].get("abstractNote", "")).strip()
    return {"key": it["key"], "type": it["type"], "title": title_of(it), "creators": creators_of(it, None),
            "year": year_of(it), "publication": pub_of(it), "doi": it["f"].get("DOI", ""),
            "citekey": it["f"].get("citationKey", ""), "tags": it["tags"], "collections": paths_of(it, tree),
            "score": score, "matched": matched or {},
            "abstract_snippet": abstract[:300] + ("…" if len(abstract) > 300 else "")}


# ------------------------------------------------------------------- busca
WEIGHTS = {"title": 5, "tags": 4, "abstract": 3, "notes": 2, "annotations": 2, "creators": 2,
           "publication": 1, "fulltext": 1}
DEFAULT_IN = ("title", "abstract", "tags", "creators", "publication", "notes")


def parse_in(spec: str | None) -> list[str]:
    if not spec:
        return list(DEFAULT_IN)
    if fold(spec) == "all":
        return list(WEIGHTS)
    out = [fold(x) for x in spec.split(",") if x.strip()]
    bad = [x for x in out if x not in WEIGHTS]
    if bad:
        die(f"campo(s) desconhecido(s) em --in: {', '.join(bad)}. Válidos: {', '.join(WEIGHTS)}, all")
    return out


def field_fold(it: dict, field: str) -> str:
    cache = it["_fold"]
    if field not in cache:
        f = it["f"]
        raw = {
            "title": " | ".join(x for x in (f.get("title"), f.get("shortTitle")) if x),
            "abstract": f.get("abstractNote", ""),
            "tags": " | ".join(it["tags"]),
            "creators": " | ".join(f"{a} {b}" for a, b, _ in it["creators"]),
            "publication": " | ".join(f[k] for k in PUB_FIELDS + ("series", "journalAbbreviation", "publisher") if f.get(k)),
            "notes": " | ".join(it["notes"]),
            "annotations": " | ".join(it["annots"]),
        }[field]
        cache[field] = fold(raw)
    return cache[field]


def term_regex(term: str, whole: bool):
    pat = r"(?<!\w)" + re.escape(fold(term)) + (r"(?!\w)" if whole else "")
    return re.compile(pat)


def fulltext_hits(ft, att_parent: dict[int, int], term: str, whole: bool) -> set[int]:
    """Itens cujo texto completo (índice do próprio Zotero) contém o termo."""
    q = '"' + term.replace('"', '""') + '"' + ("" if whole else " *")
    try:
        ids = [r[0] for r in ft.execute("SELECT rowid FROM fulltextContent WHERE fulltextContent MATCH ?", (q,))]
    except sqlite3.OperationalError:
        return set()
    return {att_parent[i] for i in ids if i in att_parent}


def parse_years(spec: str | None):
    if not spec:
        return None
    m = re.fullmatch(r"\s*(\d{4})?\s*(-)?\s*(\d{4})?\s*", spec)
    if not m or not (m.group(1) or m.group(3)):
        die(f"--year inválido: '{spec}' (use 2015, 2010-2020, 2010- ou -2020)")
    lo = int(m.group(1)) if m.group(1) else None
    hi = int(m.group(3)) if m.group(3) else (None if m.group(2) else lo)
    return lo, hi


def cmd_search(args):
    data = zotero_dir(args)
    con = open_db(data)
    lib = resolve_library(con, args.library)
    tree = load_collections(con, lib["id"])
    fields = parse_in(args.in_)
    years = parse_years(args.year)
    types = {fold(t) for t in args.types.split(",")} if args.types else None
    tags = [fold(t) for t in args.tag or []]
    terms = [t for t in args.terms if t.strip()]
    if not (terms or args.collection or tags or types or years):
        die("informe termos de busca ou algum filtro (--collection, --tag, --types, --year)")

    items = load_items(con, lib["id"], tree, notes="notes" in fields, annots="annotations" in fields)
    pool = set(items)
    for spec, keep in ((args.collection, True), (args.not_in, False)):
        if spec:
            c = one_collection(tree, spec)
            ids = {c2["id"] for c2 in (subtree(c) if args.recursive else [c])}
            pool = {i for i in pool if bool(items[i]["cols"] & ids) == keep}
    if types:
        pool = {i for i in pool if fold(items[i]["type"]) in types}
    if tags:
        pool = {i for i in pool if all(t in {fold(x) for x in items[i]["tags"]} for t in tags)}
    if years:
        lo, hi = years
        pool = {i for i in pool if (y := year_of(items[i])) is not None and (lo is None or y >= lo) and (hi is None or y <= hi)}

    ft_hits: dict[str, set[int]] = {}
    if "fulltext" in fields and terms:
        ft = open_db(data, "fulltext.sqlite", required=False)
        if ft is None:
            die("índice de texto completo (fulltext.sqlite, Zotero 10+) não encontrado; tire 'fulltext' de --in")
        att_parent = dict(con.execute("SELECT itemID, parentItemID FROM itemAttachments WHERE parentItemID IS NOT NULL").fetchall())
        ft_hits = {t: fulltext_hits(ft, att_parent, t, args.whole_word) for t in terms}

    rx = [(t, term_regex(t, args.whole_word)) for t in terms]
    results = []
    for iid in pool:
        it = items[iid]
        matched: dict[str, list[str]] = {}
        score = 0
        for t, r in rx:
            hit = [f for f in fields if (iid in ft_hits[t] if f == "fulltext" else r.search(field_fold(it, f)))]
            if hit:
                matched[t] = hit
                score += sum(WEIGHTS[f] for f in hit)
        if terms and (not matched or (args.match == "all" and len(matched) < len(terms))):
            continue
        results.append((score, it, matched))
    results.sort(key=lambda x: (-x[0], -(year_of(x[1]) or 0), fold(title_of(x[1]))))
    total = len(results)
    shown = results if not args.limit else results[:args.limit]

    if args.json:
        print(json.dumps({"library": lib["id"], "terms": terms, "total": total,
                          "results": [record(it, tree, s, m) for s, it, m in shown]}, ensure_ascii=False, indent=1))
        return
    print(f"{total} itens em '{lib['name']}'" + (f" (mostrando {len(shown)}; --limit 0 mostra todos)" if len(shown) < total else ""))
    for n, (s, it, m) in enumerate(shown, 1):
        y = year_of(it) or "s.d."
        t = title_of(it)
        print(f"{n:>3}. {it['key']}  {y}  {creators_of(it)}  —  {t[:110]}{'…' if len(t) > 110 else ''}")
        extra = "; ".join(f"{t}: {', '.join(fs)}" for t, fs in m.items())
        where = ", ".join(paths_of(it, tree)[:3])
        print(f"       [{it['type']}]" + (f" score {s} · {extra}" if terms else "") + (f"  em: {where}" if where else ""))


# ---------------------------------------------------------------- listagens
def cmd_libraries(args):
    for l in list_libraries(open_db(zotero_dir(args))):
        print(f"{l['id']:>3}  {l['name']}  ({'pessoal' if l['type'] == 'user' else 'grupo'}"
              f"{'' if l['editable'] else ', somente leitura'})")


def cmd_collections(args):
    con = open_db(zotero_dir(args))
    lib = resolve_library(con, args.library)
    tree = load_collections(con, lib["id"])
    counts = dict(con.execute("SELECT collectionID, COUNT(*) FROM collectionItems "
                              "WHERE itemID NOT IN (SELECT itemID FROM deletedItems) GROUP BY 1").fetchall())
    flt = fold(args.filter) if args.filter else None
    rows = []
    for c in (x for r in tree["roots"] for x in subtree(r)):
        depth = len(c["names"]) - 1
        if args.depth is not None and depth >= args.depth:
            continue
        if flt and flt not in fold(c["name"]):
            continue
        rows.append((c, depth))
    if args.json:
        print(json.dumps([{"key": c["key"], "name": c["name"], "path": "/" + c["path"], "depth": d,
                           "items": counts.get(c["id"], 0)} for c, d in rows], ensure_ascii=False, indent=1))
        return
    print(f"{len(rows)} coleções em '{lib['name']}' (id {lib['id']})")
    for c, d in rows:
        label = "/" + c["path"] if flt else "  " * d + c["name"]
        print(f"{label}  [{c['key']}]  {counts.get(c['id'], 0)}")


def cmd_show(args):
    con = open_db(zotero_dir(args))
    lib = resolve_library(con, args.library)
    tree = load_collections(con, lib["id"])
    items = load_items(con, lib["id"], tree)
    by_key = {it["key"]: it for it in items.values()}
    link = ("zotero://select/library/items/{}" if lib["type"] == "user"
            else f"zotero://select/groups/{lib['group_id']}/items/{{}}")
    out = []
    for k in args.keys:
        it = by_key.get(k.upper())
        if not it:
            print(f"{k}: não é um item principal desta biblioteca (ou está na lixeira)", file=sys.stderr)
            continue
        extras = {
            "anexos": con.execute("SELECT COUNT(*) FROM itemAttachments WHERE parentItemID=?", (it["id"],)).fetchone()[0],
            "notas": con.execute("SELECT COUNT(*) FROM itemNotes WHERE parentItemID=?", (it["id"],)).fetchone()[0],
            "anotacoes": con.execute("SELECT COUNT(*) FROM itemAnnotations a JOIN itemAttachments t ON t.itemID=a.parentItemID "
                                     "WHERE t.parentItemID=?", (it["id"],)).fetchone()[0],
        }
        rec = {**record(it, tree), "abstract": it["f"].get("abstractNote", ""), "url": it["f"].get("url", ""),
               "link": link.format(it["key"]), **extras}
        rec.pop("abstract_snippet")
        out.append(rec)
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return
    for r in out:
        print(f"{r['key']}  {r['year'] or 's.d.'}  [{r['type']}]  {r['title']}")
        print(f"  autores: {r['creators'] or '—'}")
        if r["publication"]:
            print(f"  publicado em: {r['publication']}")
        for lab, k in (("DOI", "doi"), ("URL", "url"), ("citekey", "citekey")):
            if r[k]:
                print(f"  {lab}: {r[k]}")
        print(f"  tags: {', '.join(r['tags']) or '—'}")
        print(f"  coleções: {', '.join(r['collections']) or '—'}")
        print(f"  anexos {r['anexos']} · notas {r['notas']} · anotações {r['anotacoes']}  |  {r['link']}")
        resumo = r["abstract"].replace("\n", " ") or "—"
        print(f"  resumo: {resumo}\n")


# ---------------------------------------------------------- plugin / snippet
class BridgeError(Exception):
    """Plugin inacessível, antigo ou sem pareamento: dá para cair no snippet."""


class OpError(Exception):
    """O plugin recebeu o pedido e recusou (ex.: coleção inexistente): não adianta o snippet."""


def bridge_token() -> str | None:
    try:
        return TOKEN_FILE.read_text().strip() or None
    except OSError:
        return None


def bridge_call(method: str, path: str, token: str, body=None, timeout=60) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    h = {"X-Zotobs-Token": token, **({"Content-Type": "application/json"} if data is not None else {})}
    req = urllib.request.Request(BRIDGE + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        if e.code == 403:
            raise BridgeError("o plugin recusou o token; rode `zotobs bridge-token`")
        if e.code == 404:
            raise BridgeError("o plugin instalado é antigo (sem /zotobs/collection); atualize o zotobs-bridge para 0.1.2+")
        try:
            detail = json.loads(detail).get("error", detail)
        except ValueError:
            pass
        raise OpError(f"o plugin respondeu {e.code}: {detail}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise BridgeError(f"plugin inacessível (Zotero fechado ou sem o zotobs-bridge?): {e}")


def js_snippet(payload: dict) -> str:
    return f"""// zotobs: coleção -> {len(payload['items'])} itens (biblioteca {payload['library']})
// Zotero > Ferramentas > Developer > Run JavaScript > colar > Run
{JS_CORE}
const out = await zotobsCollectionOp({json.dumps(payload, ensure_ascii=False, indent=1)});
return "coleção " + out.colecao + ": " + out.colecoes_criadas.length + " criadas, " + out.adicionados.length +
  " itens adicionados, " + out.ja_estavam.length + " já estavam, " + out.falhas.length + " falhas" +
  (out.falhas.length ? "\\n" + out.falhas.join("\\n") : "");
"""


def write_snippet(payload: dict) -> None:
    js = js_snippet(payload)
    out = Path.home() / ".cache" / "zotero-anot" / "ultima_colecao.js"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(js, encoding="utf-8")
    clip = next(([c] + a for c, a in (("pbcopy", []), ("wl-copy", []), ("xclip", ["-selection", "clipboard"]), ("clip", []))
                 if shutil.which(c)), None)
    copied = False
    if clip and not os.environ.get("ZOTERO_ANOT_NO_CLIP"):
        import subprocess
        subprocess.run(clip, input=js.encode("utf-16-le" if clip[0] == "clip" else "utf-8"), check=False)
        copied = True
    print(f"Snippet salvo em {out}" + (" e copiado para a área de transferência." if copied else "."))
    print("No Zotero: Ferramentas > Developer > Run JavaScript > colar > Run (seguro repetir: não duplica nada).")


def apply_plan(args, lib: dict, plan: dict, add_keys: list[str]) -> bool:
    """Executa pelo plugin; sem ele, gera o snippet. True se não houve falhas."""
    def payload(keys, col_key=None):
        base = {"library": lib["id"], "items": keys}
        if col_key or plan["col"]:
            base["collection"] = col_key or plan["col"]["key"]
        else:
            base["create"] = {"parent": plan["parent"]["key"] if plan["parent"] else None, "names": plan["create"]}
        return base

    if not args.no_plugin:
        token = bridge_token()
        try:
            if not token:
                raise BridgeError("sem token de pareamento (rode `zotobs bridge-token`)")
            info = bridge_call("GET", "/zotobs/ping", token, timeout=3)
            if "collections" not in info.get("features", []):
                raise BridgeError(f"o plugin instalado (v{info.get('version')}) é antigo; atualize o zotobs-bridge para 0.1.2+")
            tot = {"colecoes_criadas": [], "adicionados": [], "ja_estavam": [], "falhas": []}
            col_key = None
            for batch in list(chunks(add_keys, BATCH)) or [[]]:
                res = bridge_call("POST", "/zotobs/collection", token, payload(batch, col_key))
                col_key = res["colecao"]
                for k in tot:
                    tot[k] += res.get(k, [])
            print(f"[zotero/plugin v{info.get('version')}] coleção {col_key}: {len(tot['colecoes_criadas'])} criada(s), "
                  f"{len(tot['adicionados'])} itens adicionados, {len(tot['ja_estavam'])} já estavam, {len(tot['falhas'])} falhas")
            for f in tot["falhas"]:
                print("  falha:", f)
            return not tot["falhas"]
        except BridgeError as e:
            print(f"[zotero/plugin] não usado: {e}")
        except OpError as e:
            die(str(e), 1)
    write_snippet(payload(add_keys))
    return True


# ------------------------------------------------------------ collection add
def parse_keys(tokens: list[str], stdin_text: str | None) -> list[str]:
    raw: list[str] = []
    if stdin_text and stdin_text.strip():
        try:
            data = json.loads(stdin_text)
        except ValueError:
            data = None
        if isinstance(data, dict):
            data = data.get("results") or data.get("items") or data.get("keys") or []
        if isinstance(data, list):
            raw += [x.get("key", "") if isinstance(x, dict) else str(x) for x in data]
        else:  # chaves soltas (inclusive só dígitos, que o JSON leria como número)
            raw += re.split(r"[\s,;]+", stdin_text.strip())
    for t in tokens:
        raw += re.split(r"[\s,;]+", t.strip())
    keys, bad = [], []
    for k in (x.strip().upper() for x in raw if x.strip()):
        if not KEY_RE.match(k):
            bad.append(k)
        elif k not in keys:
            keys.append(k)
    if bad:
        die("chave(s) de item inválida(s) (esperado 8 caracteres A-Z/0-9): " + ", ".join(bad[:5]))
    return keys


def classify(con, lib: int, keys: list[str], col: dict | None) -> dict[str, dict]:
    rows = {}
    for part in chunks(keys):
        q = ("SELECT i.itemID, i.key, it.typeName, EXISTS(SELECT 1 FROM deletedItems d WHERE d.itemID=i.itemID) AS trashed, "
             "(SELECT v.value FROM itemData d JOIN fields f USING(fieldID) JOIN itemDataValues v USING(valueID) "
             " WHERE d.itemID=i.itemID AND f.fieldName='title') AS title "
             f"FROM items i JOIN itemTypes it USING(itemTypeID) WHERE i.libraryID=? AND i.key IN ({','.join('?' * len(part))})")
        for r in con.execute(q, [lib, *part]):
            rows[r["key"]] = r
    members = set()
    if col:
        members = {r[0] for r in con.execute("SELECT itemID FROM collectionItems WHERE collectionID=?", (col["id"],))}
    out = {}
    for k in keys:
        r = rows.get(k)
        if r is None:
            out[k] = {"status": "missing", "title": "", "why": "não existe nesta biblioteca (outra biblioteca? use --library)"}
        elif r["trashed"]:
            out[k] = {"status": "problem", "title": r["title"] or "", "why": "está na lixeira"}
        elif r["typeName"] in NOT_REGULAR:
            out[k] = {"status": "problem", "title": r["title"] or "", "why": f"é {r['typeName']}, não um item principal"}
        elif r["itemID"] in members:
            out[k] = {"status": "already", "title": r["title"] or ""}
        else:
            out[k] = {"status": "add", "title": r["title"] or ""}
    return out


def run_one(args, con, lib: dict, tree: dict, target: str, create: bool, keys: list[str]) -> int:
    """Prévia (e gravação, sem --dry-run) de UM destino. Devolve 0 (ok) ou 1 (houve problema)."""
    plan = plan_target(tree, target, args.parent, create=create)
    status = classify(con, lib["id"], keys, plan["col"])
    if plan["col"]:
        print(f"Destino: /{plan['col']['path']}  [{plan['col']['key']}]  (existente) · biblioteca '{lib['name']}'")
    else:
        base = f"em /{plan['parent']['path']}" if plan["parent"] else "na raiz"
        print(f"Destino: será criada a coleção '{'/'.join(plan['create'])}' {base} · biblioteca '{lib['name']}'")
    marks = {"add": "+", "already": "=", "problem": "!", "missing": "!"}
    for k, s in status.items():
        why = {"add": "adicionar", "already": "já está na coleção"}.get(s["status"], s.get("why", ""))
        print(f"  {marks[s['status']]} {k}  {s['title'][:80]}  → {why}")
    to_add = [k for k, s in status.items() if s["status"] == "add"]
    n_prob = sum(1 for s in status.values() if s["status"] in ("problem", "missing"))
    n_already = sum(1 for s in status.values() if s["status"] == "already")
    print(f"{len(to_add)} a adicionar, {n_already} já estavam, {n_prob} com problema")
    if not to_add and plan["col"]:
        print("(nada a fazer)")
        return 1 if n_prob else 0
    if args.dry_run:
        print("(nada gravado)")
        return 0
    if n_prob and args.strict:
        die("--strict: há itens com problema; nada gravado", 1)
    ok = apply_plan(args, lib, plan, to_add)
    return 1 if (n_prob or not ok) else 0


def load_groups(path: str) -> dict[str, list[str]]:
    try:
        data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        die(f"--groups: não consegui ler o JSON ({e})")
    if not isinstance(data, dict) or not data or not all(isinstance(v, list) for v in data.values()):
        die('--groups: esperado um objeto {"nome da subcoleção": ["CHAVE", ...], ...}')
    if any(not n.strip() or "/" in n for n in data):
        die("--groups: nomes de subcoleção não podem ser vazios nem conter '/'")
    return {n.strip(): parse_keys([str(k) for k in v], None) for n, v in data.items()}


def cmd_collection(args):
    con = open_db(zotero_dir(args))
    lib = resolve_library(con, args.library)
    if not lib["editable"] and not args.dry_run:
        die(f"a biblioteca '{lib['name']}' é somente leitura")
    tree = load_collections(con, lib["id"])
    creating = args.action == "create"
    if getattr(args, "groups", None):  # opcional: uma subcoleção por grupo, dentro de DESTINO
        if args.keys:
            die("--groups não se combina com chaves avulsas")
        code = 0
        for name, keys in load_groups(args.groups).items():
            print(f"\n== {args.target}/{name}")
            code |= run_one(args, con, lib, tree, f"{args.target.rstrip('/')}/{name}", True, keys)
        sys.exit(code)
    stdin_text = sys.stdin.read() if "-" in (args.keys if not creating else []) else None
    keys = [] if creating else parse_keys([k for k in args.keys if k != "-"], stdin_text)
    sys.exit(run_one(args, con, lib, tree, args.target, creating or args.create, keys))


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(prog="zotero_lib", description=__doc__.split("\n\n")[0])
    ap.add_argument("--zotero-dir", help="pasta de dados do Zotero (padrão: prefs.js ou ~/Zotero)")
    ap.add_argument("--base-dir", help="ignorado aqui (aceito por compatibilidade com o `zotobs`)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    lib = argparse.ArgumentParser(add_help=False)
    lib.add_argument("-L", "--library", help="número ou nome da biblioteca (padrão: a pessoal; veja `libraries`)")

    sub.add_parser("libraries", help="lista as bibliotecas").set_defaults(fn=cmd_libraries)

    c = sub.add_parser("collections", parents=[lib], help="árvore de coleções, com chaves e contagens")
    c.add_argument("--filter", help="só coleções cujo nome contém o texto (lista com caminho completo)")
    c.add_argument("--depth", type=int, help="mostra só N níveis")
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_collections)

    s = sub.add_parser("search", parents=[lib], help="busca itens por tema")
    s.add_argument("terms", nargs="*", help="termos ou frases (entre aspas); por padrão, qualquer um deles (OR)")
    s.add_argument("--match", choices=["any", "all"], default="any", help="any (padrão): algum termo; all: todos")
    s.add_argument("--in", dest="in_", help=f"campos: {','.join(WEIGHTS)} ou all (padrão: {','.join(DEFAULT_IN)})")
    s.add_argument("--whole-word", action="store_true", help="palavra inteira (padrão: o termo vale como início de palavra)")
    s.add_argument("-c", "--collection", help="só itens desta coleção (chave, nome ou caminho)")
    s.add_argument("--not-in", help="exclui itens que já estão nesta coleção")
    s.add_argument("--recursive", action="store_true", help="--collection/--not-in incluem as subcoleções")
    s.add_argument("--tag", action="append", help="exige esta tag (repetível: todas)")
    s.add_argument("--types", help="tipos de item, ex.: journalArticle,book,thesis")
    s.add_argument("--year", help="2015, 2010-2020, 2010- ou -2020")
    s.add_argument("--limit", type=int, default=30, help="máximo de resultados (0 = todos; padrão 30)")
    s.add_argument("--json", action="store_true", help="saída JSON (bom para agentes)")
    s.set_defaults(fn=cmd_search)

    w = sub.add_parser("show", parents=[lib], help="detalhes de itens")
    w.add_argument("keys", nargs="+", help="chaves dos itens (8 caracteres)")
    w.add_argument("--json", action="store_true")
    w.set_defaults(fn=cmd_show)

    col = sub.add_parser("collection", help="cria subcoleções e coloca itens nelas")
    cs = col.add_subparsers(dest="action", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("target", help="coleção de destino: chave, nome ou caminho 'A/B' ('/A/B' a partir da raiz)")
    common.add_argument("--parent", help="coleção-mãe, quando o destino é novo (chave, nome ou caminho)")
    common.add_argument("--dry-run", action="store_true", help="só mostra o que faria")
    common.add_argument("--no-plugin", "--offline", dest="no_plugin", action="store_true",
                        help="não usa o plugin: gera o snippet JS para colar no Zotero")
    common.add_argument("--strict", action="store_true", help="não grava nada se algum item tiver problema")
    cr = cs.add_parser("create", parents=[lib, common], help="cria a coleção (e as que faltarem no caminho)")
    cr.set_defaults(fn=cmd_collection, keys=[], create=True)
    ad = cs.add_parser("add", parents=[lib, common], help="adiciona itens à coleção")
    ad.add_argument("keys", nargs="*", help="chaves de itens; '-' lê da entrada padrão (JSON de `search --json`, ou chaves soltas)")
    ad.add_argument("--create", action="store_true", help="cria a coleção de destino se ela não existir")
    ad.add_argument("--groups", metavar="ARQ.json",
                    help='opcional: {"subcoleção": ["CHAVE", ...]} cria cada subcoleção dentro de DESTINO (cria o que faltar)')
    ad.set_defaults(fn=cmd_collection)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
