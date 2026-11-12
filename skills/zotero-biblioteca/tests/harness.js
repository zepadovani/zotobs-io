// Roda o código JS do plugin com um objeto Zotero simulado (só o que ele usa).
//   node harness.js op     <arquivo-com-zotobsCollectionOp>
//   node harness.js bridge <bootstrap.js>
const fs = require("fs");
const vm = require("vm");

function makeZotero() {
  let nextId = 100;
  const cols = [
    { id: 1, key: "COLAAAA1", name: "Bibliografia", parentID: false, deleted: false, libraryID: 1 },
    { id: 2, key: "COLBBBB2", name: "Ritmo", parentID: 1, deleted: false, libraryID: 1 },
    { id: 3, key: "COLLIXO3", name: "Lixo", parentID: false, deleted: true, libraryID: 1 },
  ];
  const mk = (key, extra = {}) => {
    const it = {
      key, deleted: false, regular: true, cols: new Set(), saved: 0,
      isRegularItem() { return this.regular; },
      async loadAllData() {},
      inCollection(id) { return this.cols.has(id); },
      addToCollection(id) { this.cols.add(id); },
      async saveTx() { this.saved++; return true; },
      ...extra,
    };
    return it;
  };
  const items = {
    AAAAAAA2: mk("AAAAAAA2"),
    BBBBBBB3: mk("BBBBBBB3"),
    CCCCCCC4: mk("CCCCCCC4", { regular: false }),   // anexo
    DDDDDDD5: mk("DDDDDDD5", { deleted: true }),    // lixeira
  };
  items.BBBBBBB3.cols.add(2);                       // já está em Bibliografia/Ritmo
  class Collection {
    async saveTx() {
      this.id = nextId++;
      this.key = "NEWKEY" + String(this.id).padStart(2, "0");
      this.deleted = false;
      cols.push(this);
    }
  }
  const Zotero = {
    Libraries: { get: (id) => ({ 1: { editable: true }, 2: { editable: false } })[id] },
    Collections: {
      getByLibraryAndKey: (lib, k) => cols.find((c) => c.libraryID === lib && c.key === k),
      getByLibrary: (lib) => cols.filter((c) => c.libraryID === lib && !c.deleted),
    },
    Collection,
    Items: { getByLibraryAndKey: (lib, k) => (lib === 1 ? items[k] : undefined) },
    Server: { Endpoints: {} },
    debug() {},
  };
  return { Zotero, cols, items };
}

async function main() {
  const [mode, file] = process.argv.slice(2);
  const src = fs.readFileSync(file, "utf8");
  const { Zotero, cols, items } = makeZotero();
  vm.runInThisContext("var Zotero;");
  global.Zotero = Zotero;
  global.Services = {};
  vm.runInThisContext(src);
  const out = {};
  if (mode === "op") {
    const op = (req) => zotobsCollectionOp(req).catch((e) => ({ erro: e.message }));
    // 1. cria cadeia nova sob coleção existente e adiciona itens (inclui casos ruins)
    out.criar = await op({ library: 1, create: { parent: "COLAAAA1", names: ["Tema", "Sub"] },
                           items: ["AAAAAAA2", "BBBBBBB3", "CCCCCCC4", "DDDDDDD5", "ZZZZZZZ9", "curta"] });
    const sub = cols.find((c) => c.key === out.criar.colecao);
    out.sub = { name: sub.name, parent: cols.find((c) => c.id === sub.parentID).name };
    // 2. repetir é idempotente: não cria de novo a cadeia nem duplica itens
    out.repetir = await op({ library: 1, create: { parent: "COLAAAA1", names: ["Tema", "Sub"] },
                             items: ["AAAAAAA2"] });
    out.n_cols = cols.length;
    out.salvos = items.AAAAAAA2.saved;
    // 3. destino existente; lixeira, biblioteca somente leitura, nomes vazios
    out.existente = await op({ library: 1, collection: "COLBBBB2", items: ["AAAAAAA2", "BBBBBBB3"] });
    out.lixeira = await op({ library: 1, collection: "COLLIXO3", items: [] });
    out.somente_leitura = await op({ library: 2, collection: "COLAAAA1", items: [] });
    out.vazio = await op({ library: 1, create: { parent: null, names: ["  "] }, items: [] });
    out.raiz = await op({ library: 1, create: { parent: null, names: ["Nova raiz"] }, items: [] });
    out.raiz_parent = cols.find((c) => c.key === out.raiz.colecao).parentID === undefined;
  } else if (mode === "bridge") {
    const B = ZotobsBridge;
    out.features = B.features;
    out.version = B.version;
    out.invalido = (await B.doCollection({ library: "x", items: [] }))[0];
    out.grande = (await B.doCollection({ library: 1, collection: "COLAAAA1", items: new Array(501).fill("AAAAAAA2") }))[0];
    out.inexistente = (await B.doCollection({ library: 1, collection: "NAOEXIS9", items: [] }))[0];
    const ok = await B.doCollection({ library: 1, collection: "COLBBBB2", items: ["AAAAAAA2"] });
    out.ok = [ok[0], JSON.parse(ok[2]).adicionados];
    B.register();
    out.registrado = "/zotobs/collection" in Zotero.Server.Endpoints;
    B.unregister();
    out.removido = !("/zotobs/collection" in Zotero.Server.Endpoints);
  }
  console.log(JSON.stringify(out));
}
main().catch((e) => { console.error(e); process.exit(1); });
