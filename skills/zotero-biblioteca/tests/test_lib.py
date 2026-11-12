"""zotero_lib contra um banco do Zotero sintético, um plugin falso e o JS do plugin em node.

Rodar:  uv run --with pymupdf --with pytest python -m pytest -q
"""
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import zotero_lib as zl  # noqa: E402

BOOTSTRAP = HERE.parents[2] / "extension" / "bootstrap.js"
TOKEN = "segredo"

SCHEMA = """
CREATE TABLE libraries (libraryID INTEGER PRIMARY KEY, type TEXT, editable INT);
CREATE TABLE groups (groupID INTEGER PRIMARY KEY, libraryID INT, name TEXT);
CREATE TABLE itemTypes (itemTypeID INTEGER PRIMARY KEY, typeName TEXT);
CREATE TABLE fields (fieldID INTEGER PRIMARY KEY, fieldName TEXT);
CREATE TABLE items (itemID INTEGER PRIMARY KEY, itemTypeID INT, dateAdded TEXT, libraryID INT, key TEXT);
CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value TEXT);
CREATE TABLE itemData (itemID INT, fieldID INT, valueID INT);
CREATE TABLE creators (creatorID INTEGER PRIMARY KEY, firstName TEXT, lastName TEXT, fieldMode INT);
CREATE TABLE itemCreators (itemID INT, creatorID INT, creatorTypeID INT, orderIndex INT);
CREATE TABLE tags (tagID INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE itemTags (itemID INT, tagID INT, type INT);
CREATE TABLE collections (collectionID INTEGER PRIMARY KEY, collectionName TEXT, parentCollectionID INT, libraryID INT, key TEXT);
CREATE TABLE collectionItems (collectionID INT, itemID INT, orderIndex INT);
CREATE TABLE deletedItems (itemID INTEGER PRIMARY KEY);
CREATE TABLE deletedCollections (collectionID INTEGER PRIMARY KEY);
CREATE TABLE itemNotes (itemID INTEGER PRIMARY KEY, parentItemID INT, note TEXT);
CREATE TABLE itemAttachments (itemID INTEGER PRIMARY KEY, parentItemID INT);
CREATE TABLE itemAnnotations (itemID INTEGER PRIMARY KEY, parentItemID INT, text TEXT, comment TEXT);
"""


@pytest.fixture
def zdir(tmp_path):
    """Pasta de dados do Zotero sintética (biblioteca pessoal + um grupo somente leitura)."""
    d = tmp_path / "zotero"
    d.mkdir()
    con = sqlite3.connect(d / "zotero.sqlite")
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO libraries VALUES (?,?,?)", [(1, "user", 1), (2, "group", 0)])
    con.execute("INSERT INTO groups VALUES (5, 2, 'Grupo X')")
    con.executemany("INSERT INTO itemTypes VALUES (?,?)", [(1, "journalArticle"), (2, "book"), (3, "attachment"),
                                                          (4, "note"), (5, "annotation"), (6, "thesis")])
    con.executemany("INSERT INTO fields VALUES (?,?)", [(1, "title"), (2, "abstractNote"), (3, "date"),
                                                       (4, "publicationTitle"), (5, "DOI"), (6, "citationKey")])
    items = [  # id, tipo, chave, biblioteca
        (1, 1, "AAAAAAA2", 1), (2, 2, "BBBBBBB3", 1), (3, 1, "CCCCCCC4", 1), (4, 6, "DDDDDDD5", 1),
        (5, 3, "EEEEEEE6", 1), (6, 4, "FFFFFFF7", 1), (7, 5, "GGGGGGG8", 1), (8, 1, "HHHHHHH9", 2),
    ]
    con.executemany("INSERT INTO items VALUES (?,?,'2024-01-01',?,?)", [(i, t, lib, k) for i, t, k, lib in items])
    data = {
        1: {1: "Ritmo e pulso na música", 2: "estudo sobre o pulso", 3: "2019-00-00 2019", 4: "Revista X"},
        2: {1: "Timbre e espectro", 2: "análise do rítmico no timbre", 3: "2005-00-00 2005"},
        3: {1: "Harmonia tonal", 3: "2010-00-00 2010"},
        4: {1: "Ritmos africanos", 3: "2001-00-00 2001"},
        8: {1: "Ritmo no grupo", 3: "2020-00-00 2020"},
    }
    vid = 0
    for iid, fs in data.items():
        for fid, val in fs.items():
            vid += 1
            con.execute("INSERT INTO itemDataValues VALUES (?,?)", (vid, val))
            con.execute("INSERT INTO itemData VALUES (?,?,?)", (iid, fid, vid))
    con.executemany("INSERT INTO creators VALUES (?,?,?,?)", [(1, "Ana", "Silva", 0), (2, "Bia", "Souza", 0)])
    con.executemany("INSERT INTO itemCreators VALUES (?,?,1,0)", [(1, 1), (2, 2)])
    con.executemany("INSERT INTO tags VALUES (?,?)", [(1, "ritmo"), (2, "Pulsação")])
    con.executemany("INSERT INTO itemTags VALUES (?,?,0)", [(1, 1), (2, 2)])
    con.execute("INSERT INTO deletedItems VALUES (4)")
    con.execute("INSERT INTO itemAttachments VALUES (5, 2)")          # anexo do item 2
    con.execute("INSERT INTO itemNotes VALUES (6, 3, '<p>sobre o ritmo na harmonia</p>')")
    con.execute("INSERT INTO itemAnnotations VALUES (7, 5, 'a síncopa é central', 'ver ritmo')")
    con.executemany("INSERT INTO collections VALUES (?,?,?,1,?)", [
        (1, "Bibliografia", None, "COLAAAA1"), (2, "Ritmo", 1, "COLBBBB2"),
        (3, "Ritmo", None, "COLCCCC3"), (4, "Lixo", None, "COLDDDD4")])
    con.execute("INSERT INTO deletedCollections VALUES (4)")
    con.execute("INSERT INTO collectionItems VALUES (2, 1, 0)")      # item 1 já está em Bibliografia/Ritmo
    con.commit()
    con.close()
    return d


@pytest.fixture
def fulltext(zdir):
    ft = sqlite3.connect(zdir / "fulltext.sqlite")
    try:
        ft.execute("CREATE VIRTUAL TABLE fulltextContent USING fts5(text, tokenize='unicode61', content='')")
    except sqlite3.OperationalError:
        pytest.skip("SQLite sem FTS5")
    ft.execute("INSERT INTO fulltextContent(rowid, text) VALUES (5, 'a sincopa define o RITMO desta peça')")
    ft.commit()
    ft.close()


def run(zdir, *argv, capsys, stdin=None, monkeypatch=None):
    if stdin is not None:
        import io
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    monkeypatch.setattr(sys, "argv", ["zotero_lib", "--zotero-dir", str(zdir), *argv])
    code = 0
    try:
        zl.main()
    except SystemExit as e:
        code = e.code or 0
    cap = capsys.readouterr()
    return code, cap.out, cap.err


# ------------------------------------------------------------------ busca
def test_search_pesos_acentos_e_lixeira(zdir, capsys, monkeypatch):
    code, out, _ = run(zdir, "search", "ritmo", "rítmico", "--json", capsys=capsys, monkeypatch=monkeypatch)
    res = json.loads(out)["results"]
    keys = [r["key"] for r in res]
    assert keys == ["AAAAAAA2", "BBBBBBB3", "CCCCCCC4"]        # pesos: título+tag > resumo > nota
    assert "DDDDDDD5" not in keys          # na lixeira
    assert "HHHHHHH9" not in keys          # outra biblioteca
    top = res[0]
    assert top["key"] == "AAAAAAA2" and top["matched"]["ritmo"] == ["title", "tags"]
    assert top["collections"] == ["/Bibliografia/Ritmo"] and top["year"] == 2019
    # "rítmico" casa "ritmico" (sem acento) no resumo do item 2; e a nota do item 3 casa "ritmo"
    assert res[1]["matched"] == {"rítmico": ["abstract"]} and res[2]["matched"] == {"ritmo": ["notes"]}


def test_search_prefixo_e_palavra_inteira(zdir, capsys, monkeypatch):
    _, out, _ = run(zdir, "search", "ritm", "--json", capsys=capsys, monkeypatch=monkeypatch)
    assert {r["key"] for r in json.loads(out)["results"]} >= {"AAAAAAA2", "BBBBBBB3"}
    _, out, _ = run(zdir, "search", "ritm", "--whole-word", "--json", capsys=capsys, monkeypatch=monkeypatch)
    assert json.loads(out)["results"] == []


def test_search_filtros(zdir, capsys, monkeypatch):
    def keys(*a):
        _, out, _ = run(zdir, "search", *a, "--json", capsys=capsys, monkeypatch=monkeypatch)
        return [r["key"] for r in json.loads(out)["results"]]
    assert keys("ritmo", "pulso", "--match", "all") == ["AAAAAAA2"]
    assert keys("ritmo", "--not-in", "Bibliografia/Ritmo") == ["CCCCCCC4"]   # AAAAAAA2 já está lá
    assert keys("ritm", "--not-in", "/Bibliografia/Ritmo") == ["BBBBBBB3", "CCCCCCC4"]
    assert keys("--collection", "/Bibliografia", "--recursive") == ["AAAAAAA2"]
    assert keys("--collection", "/Bibliografia") == []                    # sem --recursive: só itens diretos
    assert keys("--year", "2000-2012", "--types", "book") == ["BBBBBBB3"]
    assert keys("--tag", "pulsacao") == ["BBBBBBB3"]                      # tag sem acento/caixa
    assert keys("ritm", "--library", "Grupo X") == ["HHHHHHH9"]


def test_search_notas_anotacoes_e_texto_completo(zdir, fulltext, capsys, monkeypatch):
    _, out, _ = run(zdir, "search", "ritmo", "--in", "notes", "--json", capsys=capsys, monkeypatch=monkeypatch)
    assert [r["key"] for r in json.loads(out)["results"]] == ["CCCCCCC4"]
    _, out, _ = run(zdir, "search", "sincopa", "--in", "annotations,fulltext", "--json", capsys=capsys, monkeypatch=monkeypatch)
    res = json.loads(out)["results"]
    assert [r["key"] for r in res] == ["BBBBBBB3"]                         # via anexo (anotação + texto completo)
    assert res[0]["matched"]["sincopa"] == ["annotations", "fulltext"]


def test_search_sem_criterio_e_campo_invalido(zdir, capsys, monkeypatch):
    code, _, err = run(zdir, "search", capsys=capsys, monkeypatch=monkeypatch)
    assert code == 2 and "informe termos" in err
    code, _, err = run(zdir, "search", "x", "--in", "titulo", capsys=capsys, monkeypatch=monkeypatch)
    assert code == 2 and "desconhecido" in err


def test_collections_e_show(zdir, capsys, monkeypatch):
    _, out, _ = run(zdir, "collections", capsys=capsys, monkeypatch=monkeypatch)
    assert "Bibliografia  [COLAAAA1]" in out and "  Ritmo  [COLBBBB2]  1" in out
    assert "Lixo" not in out                                              # coleção na lixeira
    _, out, _ = run(zdir, "collections", "--filter", "RITMO", "--json", capsys=capsys, monkeypatch=monkeypatch)
    assert [c["path"] for c in json.loads(out)] == ["/Bibliografia/Ritmo", "/Ritmo"]
    _, out, _ = run(zdir, "show", "AAAAAAA2", capsys=capsys, monkeypatch=monkeypatch)
    assert "autores: Silva, Ana" in out and "/Bibliografia/Ritmo" in out and "zotero://select/library/items/AAAAAAA2" in out
    _, out, _ = run(zdir, "libraries", capsys=capsys, monkeypatch=monkeypatch)
    assert "Grupo X  (grupo, somente leitura)" in out


# ----------------------------------------------------------- collection add
def test_plano_dry_run(zdir, capsys, monkeypatch):
    code, out, _ = run(zdir, "collection", "add", "/Ritmo", "AAAAAAA2", "BBBBBBB3", "EEEEEEE6", "DDDDDDD5", "ZZZZZZZ9",
                       "--dry-run", capsys=capsys, monkeypatch=monkeypatch)
    assert code == 0 and "(existente)" in out and "(nada gravado)" in out
    assert "+ AAAAAAA2" in out and "+ BBBBBBB3" in out            # /Ritmo (raiz) está vazia
    assert "! EEEEEEE6" in out and "é attachment" in out
    assert "! DDDDDDD5" in out and "lixeira" in out
    assert "! ZZZZZZZ9" in out and "não existe" in out
    assert "2 a adicionar, 0 já estavam, 3 com problema" in out
    _, out, _ = run(zdir, "collection", "add", "Bibliografia/Ritmo", "AAAAAAA2", "--dry-run", capsys=capsys, monkeypatch=monkeypatch)
    assert "= AAAAAAA2" in out and "já está na coleção" in out


def test_destino_ambiguo_inexistente_e_criacao(zdir, capsys, monkeypatch):
    code, _, err = run(zdir, "collection", "add", "Ritmo", "AAAAAAA2", "--dry-run", capsys=capsys, monkeypatch=monkeypatch)
    assert code == 2 and "ambígua" in err and "COLBBBB2" in err and "COLCCCC3" in err
    code, _, err = run(zdir, "collection", "add", "Novo", "AAAAAAA2", "--dry-run", capsys=capsys, monkeypatch=monkeypatch)
    assert code == 2 and "--create" in err
    _, out, _ = run(zdir, "collection", "add", "Tema/Sub", "AAAAAAA2", "--parent", "COLAAAA1", "--create", "--dry-run",
                    capsys=capsys, monkeypatch=monkeypatch)
    assert "será criada a coleção 'Tema/Sub' em /Bibliografia" in out
    _, out, _ = run(zdir, "collection", "create", "Bibliografia/Ritmo/Fino", "--dry-run", capsys=capsys, monkeypatch=monkeypatch)
    assert "será criada a coleção 'Fino' em /Bibliografia/Ritmo" in out
    _, out, _ = run(zdir, "collection", "create", "Bibliografia/Ritmo", capsys=capsys, monkeypatch=monkeypatch)
    assert "(nada a fazer)" in out


def test_chaves_por_stdin_json_e_texto(zdir, capsys, monkeypatch):
    saida_busca = json.dumps({"results": [{"key": "AAAAAAA2"}, {"key": "BBBBBBB3"}]})
    _, out, _ = run(zdir, "collection", "add", "/Ritmo", "-", "--dry-run", stdin=saida_busca, capsys=capsys, monkeypatch=monkeypatch)
    assert "2 a adicionar" in out
    _, out, _ = run(zdir, "collection", "add", "/Ritmo", "-", "--dry-run", stdin="AAAAAAA2, BBBBBBB3\nAAAAAAA2", capsys=capsys, monkeypatch=monkeypatch)
    assert "2 a adicionar" in out                                         # sem repetir
    code, _, err = run(zdir, "collection", "add", "/Ritmo", "curta", "--dry-run", capsys=capsys, monkeypatch=monkeypatch)
    assert code == 2 and "inválida" in err
    _, out, _ = run(zdir, "collection", "add", "/Ritmo", "-", "--dry-run", stdin="22222222", capsys=capsys, monkeypatch=monkeypatch)
    assert "! 22222222" in out                                            # só dígitos: chave solta, não número JSON


def test_biblioteca_somente_leitura(zdir, capsys, monkeypatch):
    code, _, err = run(zdir, "collection", "create", "X", "--library", "2", capsys=capsys, monkeypatch=monkeypatch)
    assert code == 2 and "somente leitura" in err


# ------------------------------------------------------------ plugin falso
def make_bridge(seen, features=("annotations", "collections"), fail=None):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.headers.get("X-Zotobs-Token") != TOKEN:
                return self._send(403, {"error": "token"})
            self._send(200, {"ok": True, "version": "0.1.2", "zotero": "10", **({"features": list(features)} if features else {})})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append(body)
            if fail:
                return self._send(422, {"error": fail})
            self._send(200, {"colecao": body.get("collection") or "NEWKEY01",
                             "colecoes_criadas": [] if body.get("collection") else ["NEWKEY01"],
                             "adicionados": body["items"], "ja_estavam": [], "falhas": []})
    return H


@pytest.fixture
def bridge(monkeypatch, tmp_path):
    def start(**kw):
        seen = []
        srv = HTTPServer(("127.0.0.1", 0), make_bridge(seen, **kw))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        monkeypatch.setattr(zl, "BRIDGE", f"http://127.0.0.1:{srv.server_port}")
        monkeypatch.setattr(zl, "TOKEN_FILE", tmp_path / "bridge_token")
        (tmp_path / "bridge_token").write_text(TOKEN + "\n")
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.setenv("ZOTERO_ANOT_NO_CLIP", "1")
        starts.append(srv)
        return seen
    starts = []
    yield start
    for s in starts:
        s.shutdown()


def test_aplica_pelo_plugin_em_lotes(zdir, bridge, capsys, monkeypatch):
    seen = bridge()
    monkeypatch.setattr(zl, "BATCH", 1)
    code, out, _ = run(zdir, "collection", "add", "Tema/Sub", "AAAAAAA2", "BBBBBBB3", "--parent", "COLAAAA1", "--create",
                       capsys=capsys, monkeypatch=monkeypatch)
    assert code == 0 and "2 itens adicionados" in out and "1 criada(s)" in out
    assert seen[0]["create"] == {"parent": "COLAAAA1", "names": ["Tema", "Sub"]} and seen[0]["items"] == ["AAAAAAA2"]
    assert seen[1]["collection"] == "NEWKEY01" and "create" not in seen[1]     # 2º lote usa a coleção já criada
    assert seen[0]["library"] == 1


def test_create_sem_itens_e_destino_existente(zdir, bridge, capsys, monkeypatch):
    seen = bridge()
    code, out, _ = run(zdir, "collection", "create", "Novinha", capsys=capsys, monkeypatch=monkeypatch)
    assert code == 0 and seen == [{"library": 1, "items": [], "create": {"parent": None, "names": ["Novinha"]}}]
    seen.clear()
    run(zdir, "collection", "add", "/Ritmo", "BBBBBBB3", capsys=capsys, monkeypatch=monkeypatch)
    assert seen == [{"library": 1, "items": ["BBBBBBB3"], "collection": "COLCCCC3"}]


def test_plugin_antigo_cai_no_snippet(zdir, bridge, capsys, monkeypatch, tmp_path):
    bridge(features=None)                                                 # ping sem 'features' = plugin < 0.1.2
    code, out, _ = run(zdir, "collection", "add", "/Ritmo", "BBBBBBB3", capsys=capsys, monkeypatch=monkeypatch)
    assert code == 0 and "é antigo" in out and "Snippet salvo" in out
    js = (tmp_path / "home" / ".cache" / "zotero-anot" / "ultima_colecao.js").read_text()
    assert "async function zotobsCollectionOp" in js and '"collection": "COLCCCC3"' in js and "BBBBBBB3" in js


def test_sem_token_usa_snippet_e_flag_no_plugin(zdir, bridge, capsys, monkeypatch, tmp_path):
    seen = bridge()
    code, out, _ = run(zdir, "collection", "add", "/Ritmo", "BBBBBBB3", "--no-plugin", capsys=capsys, monkeypatch=monkeypatch)
    assert code == 0 and seen == [] and "Snippet salvo" in out
    (tmp_path / "bridge_token").unlink()
    code, out, _ = run(zdir, "collection", "add", "/Ritmo", "BBBBBBB3", capsys=capsys, monkeypatch=monkeypatch)
    assert "sem token" in out and "Snippet salvo" in out


def test_recusa_do_plugin_nao_vira_snippet(zdir, bridge, capsys, monkeypatch):
    bridge(fail="coleção COLCCCC3 não encontrada na biblioteca 1")
    code, _, err = run(zdir, "collection", "add", "/Ritmo", "BBBBBBB3", capsys=capsys, monkeypatch=monkeypatch)
    assert code == 1 and "não encontrada" in err


def test_strict_aborta_com_problema(zdir, bridge, capsys, monkeypatch):
    seen = bridge()
    code, _, err = run(zdir, "collection", "add", "/Ritmo", "BBBBBBB3", "ZZZZZZZ9", "--strict",
                       capsys=capsys, monkeypatch=monkeypatch)
    assert code == 1 and "--strict" in err and seen == []
    code, out, _ = run(zdir, "collection", "add", "/Ritmo", "BBBBBBB3", "ZZZZZZZ9", capsys=capsys, monkeypatch=monkeypatch)
    assert code == 1 and seen and seen[0]["items"] == ["BBBBBBB3"]        # grava o que dá e sinaliza o problema


# --------------------------------------------------------- JS (node)
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node não instalado")


def _core_do_plugin():
    m = re.search(r"(// >>> zotobs-collection-op.*?// <<< zotobs-collection-op)", BOOTSTRAP.read_text(encoding="utf-8"), re.S)
    return m.group(1)


def test_js_do_snippet_igual_ao_do_plugin():
    assert zl.JS_CORE.strip() == _core_do_plugin().strip()


def _node(mode, file):
    r = subprocess.run(["node", str(HERE / "harness.js"), mode, str(file)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@needs_node
def test_js_operacao_de_colecao(tmp_path):
    f = tmp_path / "core.js"
    f.write_text(zl.JS_CORE, encoding="utf-8")
    o = _node("op", f)
    c = o["criar"]
    assert o["sub"] == {"name": "Sub", "parent": "Tema"} and len(c["colecoes_criadas"]) == 2
    assert c["adicionados"] == ["AAAAAAA2", "BBBBBBB3"] and c["ja_estavam"] == []
    assert sorted(x.split(":")[0] for x in c["falhas"]) == ["CCCCCCC4", "DDDDDDD5", "ZZZZZZZ9", "curta"]
    assert any("anexo" in x for x in c["falhas"]) and any("chave inválida" in x for x in c["falhas"])
    r = o["repetir"]                                                      # idempotência
    assert r["colecoes_criadas"] == [] and r["adicionados"] == [] and r["ja_estavam"] == ["AAAAAAA2"]
    assert r["colecao"] == c["colecao"] and o["n_cols"] == 5 and o["salvos"] == 1
    assert o["existente"]["adicionados"] == ["AAAAAAA2"] and o["existente"]["ja_estavam"] == ["BBBBBBB3"]
    assert "não encontrada" in o["lixeira"]["erro"]
    assert "somente leitura" in o["somente_leitura"]["erro"]
    assert "vazio" in o["vazio"]["erro"]
    assert o["raiz_parent"] is True


@needs_node
def test_js_endpoint_do_plugin():
    o = _node("bridge", BOOTSTRAP)
    assert "collections" in o["features"] and o["version"] == json.loads((BOOTSTRAP.parent / "manifest.json").read_text())["version"]
    assert (o["invalido"], o["grande"], o["inexistente"]) == (400, 413, 422)
    assert o["ok"] == [200, ["AAAAAAA2"]] and o["registrado"] and o["removido"]


# ------------------------------------------------------ --groups (opcional)
def test_groups_subcolecoes_por_nicho(zdir, bridge, capsys, monkeypatch, tmp_path):
    seen = bridge()
    g = tmp_path / "g.json"
    g.write_text(json.dumps({"Ritmo": ["AAAAAAA2"], "Timbre": ["BBBBBBB3"]}))
    code, out, _ = run(zdir, "collection", "add", "Tese", "--groups", str(g), "--create", "--dry-run",
                       capsys=capsys, monkeypatch=monkeypatch)
    assert code == 0 and "será criada a coleção 'Tese/Ritmo'" in out and "será criada a coleção 'Tese/Timbre'" in out
    assert seen == []
    code, out, _ = run(zdir, "collection", "add", "Tese", "--groups", str(g), "--create", capsys=capsys, monkeypatch=monkeypatch)
    assert code == 0 and [s["create"]["names"] for s in seen] == [["Tese", "Ritmo"], ["Tese", "Timbre"]]
    assert [s["items"] for s in seen] == [["AAAAAAA2"], ["BBBBBBB3"]]
    g.write_text("[1]")
    code, _, err = run(zdir, "collection", "add", "Tese", "--groups", str(g), capsys=capsys, monkeypatch=monkeypatch)
    assert code == 2 and "esperado um objeto" in err
