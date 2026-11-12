/* zotobs-bridge — plugin bootstrapped do Zotero 7+.
 *
 * Registra endpoints em http://127.0.0.1:23119/zotobs/* :
 *   GET  /zotobs/ping    -> {ok, version, zotero}
 *   POST /zotobs/import  -> cria anotações (mesmo JSON do snippet do CLI)
 *   POST /zotobs/update  -> altera comentário/tags/cor/trecho de anotações já existentes
 *   POST /zotobs/collection -> cria coleções (subpastas) e põe itens nelas
 *
 * Segurança: exige o cabeçalho X-Zotobs-Token igual ao conteúdo de
 * ~/.config/zotero-anot/bridge_token (criado por `zotobs bridge-token`) e
 * recusa requisições com Origin (navegadores). Só cria anotações e coleções
 * e adiciona itens a coleções (nunca remove nem apaga nada).
 */
var ZotobsBridge = {
  id: "zotobs-bridge@zotobs-io",
  version: "0.1.3",
  MAX_ITEMS: 500,
  features: ["annotations", "collections", "update-position"],   // o CLI confere antes de usar um recurso
  endpoints: ["/zotobs/ping", "/zotobs/import", "/zotobs/update", "/zotobs/collection"],

  log(msg) { Zotero.debug("[zotobs-bridge] " + msg); },

  tokenPath() {
    const home = Services.dirsvc.get("Home", Ci.nsIFile).path;
    return PathUtils.join(home, ".config", "zotero-anot", "bridge_token");
  },

  async authorized(req) {
    const h = req.headers || {};
    const get = (n) => h[n] ?? h[n.toLowerCase()];
    if (get("Origin")) return false;                     // navegador
    const sent = get("X-Zotobs-Token");
    if (!sent) return false;
    let want;
    try { want = (await IOUtils.readUTF8(this.tokenPath())).trim(); }
    catch (e) { return false; }                          // sem token configurado -> nega
    if (!want || want.length !== sent.length) return false;
    let diff = 0;                                        // comparação em tempo constante
    for (let i = 0; i < want.length; i++) diff |= want.charCodeAt(i) ^ sent.charCodeAt(i);
    return diff === 0;
  },

  reply(status, obj) { return [status, "application/json", JSON.stringify(obj)]; },

  async doImport(body) {
    const lib = body && body.library, attKey = body && body.attachment, items = body && body.items;
    if (!Number.isInteger(lib) || typeof attKey !== "string" || !Array.isArray(items))
      return this.reply(400, { error: "corpo inválido: library, attachment, items" });
    if (items.length > this.MAX_ITEMS)
      return this.reply(413, { error: "itens demais (máx. " + this.MAX_ITEMS + ")" });
    const att = Zotero.Items.getByLibraryAndKey(lib, attKey);
    if (!att || !att.isFileAttachment())
      return this.reply(404, { error: "attachment " + attKey + " não encontrado na biblioteca " + lib });

    const out = { criadas: [], puladas: [], falhas: [] };
    for (const d of items) {
      try {
        if (!/^[A-Z0-9]{8}$/.test(d.key || "")) throw new Error("chave inválida");
        if (Zotero.Items.getByLibraryAndKey(lib, d.key)) { out.puladas.push(d.key); continue; }
        await Zotero.Annotations.saveFromJSON(att, {
          key: d.key,
          type: d.annotationType,
          authorName: d.annotationAuthorName || "",
          text: d.annotationText,
          comment: d.annotationComment || "",
          color: d.annotationColor,
          pageLabel: d.annotationPageLabel,
          sortIndex: d.annotationSortIndex,
          position: typeof d.annotationPosition === "string"
            ? JSON.parse(d.annotationPosition) : d.annotationPosition,
          tags: (d.tags || []).map((t) => ({ name: t.tag })),
        });
        out.criadas.push(d.key);
      } catch (e) {
        this.log("falha em " + d.key + ": " + e);
        out.falhas.push((d.key || "?") + ": " + e.message);
      }
    }
    this.log("import: " + out.criadas.length + " criadas, " + out.puladas.length +
             " puladas, " + out.falhas.length + " falhas");
    return this.reply(200, out);
  },

  async doUpdate(body) {
    const lib = body && body.library, attKey = body && body.attachment, items = body && body.items;
    if (!Number.isInteger(lib) || typeof attKey !== "string" || !Array.isArray(items))
      return this.reply(400, { error: "corpo inválido: library, attachment, items" });
    if (items.length > this.MAX_ITEMS)
      return this.reply(413, { error: "itens demais (máx. " + this.MAX_ITEMS + ")" });
    const att = Zotero.Items.getByLibraryAndKey(lib, attKey);
    if (!att) return this.reply(404, { error: "attachment " + attKey + " não encontrado" });

    const out = { atualizadas: [], inalteradas: [], falhas: [] };
    for (const d of items) {
      try {
        const it = Zotero.Items.getByLibraryAndKey(lib, d.key || "");
        // só anotações deste anexo: nada além disso é tocado
        if (!it || !it.isAnnotation() || it.parentID !== att.id) throw new Error("anotação não encontrada neste anexo");
        if (typeof d.comment === "string") it.annotationComment = d.comment;
        if (Array.isArray(d.tags)) it.setTags(d.tags.map((t) => ({ tag: String(t) })));
        if (typeof d.color === "string") it.annotationColor = d.color;
        if (d.position) {                                  // trecho novo: texto + posição + ordem, juntos
          if (typeof d.text !== "string" || typeof d.sortIndex !== "string") throw new Error("position exige text e sortIndex");
          it.annotationText = d.text;
          it.annotationPosition = typeof d.position === "string" ? d.position : JSON.stringify(d.position);
          it.annotationSortIndex = d.sortIndex;
          if (typeof d.pageLabel === "string") it.annotationPageLabel = d.pageLabel;
        }
        if (await it.saveTx()) out.atualizadas.push(d.key); else out.inalteradas.push(d.key);
      } catch (e) {
        this.log("falha em " + d.key + ": " + e);
        out.falhas.push((d.key || "?") + ": " + e.message);
      }
    }
    this.log("update: " + out.atualizadas.length + " atualizadas, " + out.falhas.length + " falhas");
    return this.reply(200, out);
  },

  async doCollection(body) {
    const lib = body && body.library;
    if (!Number.isInteger(lib) || !Array.isArray(body.items) || !(body.collection || body.create))
      return this.reply(400, { error: "corpo inválido: library, items e collection ou create" });
    if (body.items.length > this.MAX_ITEMS)
      return this.reply(413, { error: "itens demais (máx. " + this.MAX_ITEMS + ")" });
    try {
      const out = await zotobsCollectionOp(body);
      this.log("coleção " + out.colecao + ": " + out.colecoes_criadas.length + " criadas, " +
               out.adicionados.length + " itens adicionados, " + out.ja_estavam.length +
               " já estavam, " + out.falhas.length + " falhas");
      return this.reply(200, out);
    } catch (e) {
      this.log("coleção: " + e);
      return this.reply(422, { error: String(e.message || e) });
    }
  },

  register() {
    const self = this;
    const E = Zotero.Server.Endpoints;
    E["/zotobs/ping"] = function () {};
    E["/zotobs/ping"].prototype = {
      supportedMethods: ["GET"],
      init: async function (req) {
        if (!(await self.authorized(req))) return self.reply(403, { error: "token" });
        return self.reply(200, { ok: true, version: self.version, zotero: Zotero.version, features: self.features });
      },
    };
    E["/zotobs/import"] = function () {};
    E["/zotobs/import"].prototype = {
      supportedMethods: ["POST"],
      supportedDataTypes: ["application/json"],
      permitBookmarklet: false,
      init: async function (req) {
        if (!(await self.authorized(req))) return self.reply(403, { error: "token" });
        try { return await self.doImport(req.data); }
        catch (e) { self.log("erro: " + e); return self.reply(500, { error: String(e.message || e) }); }
      },
    };
    E["/zotobs/update"] = function () {};
    E["/zotobs/update"].prototype = {
      supportedMethods: ["POST"],
      supportedDataTypes: ["application/json"],
      permitBookmarklet: false,
      init: async function (req) {
        if (!(await self.authorized(req))) return self.reply(403, { error: "token" });
        try { return await self.doUpdate(req.data); }
        catch (e) { self.log("erro: " + e); return self.reply(500, { error: String(e.message || e) }); }
      },
    };
    E["/zotobs/collection"] = function () {};
    E["/zotobs/collection"].prototype = {
      supportedMethods: ["POST"],
      supportedDataTypes: ["application/json"],
      permitBookmarklet: false,
      init: async function (req) {
        if (!(await self.authorized(req))) return self.reply(403, { error: "token" });
        try { return await self.doCollection(req.data); }
        catch (e) { self.log("erro: " + e); return self.reply(500, { error: String(e.message || e) }); }
      },
    };
  },

  unregister() {
    for (const p of this.endpoints) delete Zotero.Server.Endpoints[p];
  },
};

// >>> zotobs-collection-op (manter idêntico a JS_CORE em skills/zotero-biblioteca/scripts/zotero_lib.py)
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
// <<< zotobs-collection-op

function install() {}
function uninstall() {}
var zotobsRootURI = null, zotobsPaneID = null, zotobsReaderHandlers = [];

// Leitor de PDF: botão direito no documento + ícone na barra de ferramentas.
function zotobsRegisterReader(pluginID) {
  const run = (reader, mode) => {
    const item = Zotero.Items.get(reader.itemID);
    const win = reader._window || Zotero.getMainWindow();
    if (item) Zotero.Zotobs.run([item], mode, win);
  };
  const add = (type, handler) => {
    Zotero.Reader.registerEventListener(type, handler, pluginID);
    zotobsReaderHandlers.push([type, handler]);
  };
  add("createViewContextMenu", ({ reader, append }) => {
    append({ label: "zotobs-io: Exportar anotações (pasta padrão)", onCommand: () => run(reader, "default") },
           { label: "zotobs-io: Exportar anotações para…", onCommand: () => run(reader, "folder") });
  });
  add("renderToolbar", ({ reader, doc, append }) => {
    const mk = (label, title, path, mode) => {
      const b = doc.createElement("button");
      b.className = "toolbar-button";
      b.title = title;
      b.style.cssText = "width:auto;padding:0 8px;display:inline-flex;align-items:center;gap:5px;font-size:12px;";
      b.innerHTML = '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" ' +
        `stroke-linecap="round" stroke-linejoin="round"><path d="${path}"/></svg><span>${label}</span>`;
      b.addEventListener("click", () => run(reader, mode));
      return b;
    };
    append(
      mk("zotobs", "zotobs-io: exportar anotações para Markdown na pasta padrão",
         "M8 2v7M5 6.2 8 9.2l3-3M2.5 10.5V13h11v-2.5", "default"),
      mk("zotobs…", "zotobs-io: exportar anotações para Markdown em uma pasta à escolha…",
         "M2 4h4.2l1.3 1.6H14V12.5H2zM8 7.6v3.4M6.4 9.6 8 11.2l1.6-1.6", "folder"));
  });
}

function zotobsUnregisterReader() {
  for (const [type, h] of zotobsReaderHandlers) Zotero.Reader.unregisterEventListener(type, h);
  zotobsReaderHandlers = [];
}

function zotobsAddMenu(win) {
  const doc = win.document, menu = doc.getElementById("zotero-itemmenu");
  if (!menu || doc.getElementById("zotobs-menu-sep")) return;
  const sep = doc.createXULElement("menuseparator");
  sep.id = "zotobs-menu-sep";
  const mk = (id, label, mode) => {
    const mi = doc.createXULElement("menuitem");
    mi.id = id;
    mi.setAttribute("label", label);
    mi.addEventListener("command", () =>
      Zotero.Zotobs.run(win.ZoteroPane.getSelectedItems(), mode, win));
    return mi;
  };
  menu.append(sep,
    mk("zotobs-menu-default", "zotobs-io: Exportar anotações (pasta padrão)", "default"),
    mk("zotobs-menu-folder", "zotobs-io: Exportar anotações para…", "folder"));
}

function zotobsRemoveMenu(win) {
  for (const id of ["zotobs-menu-sep", "zotobs-menu-default", "zotobs-menu-folder"])
    win.document.getElementById(id)?.remove();
}

async function startup({ id, version, rootURI }) {
  await Zotero.initializationPromise;
  zotobsRootURI = rootURI;
  Services.scriptloader.loadSubScript(rootURI + "export.js");
  zotobsPaneID = await Zotero.PreferencePanes.register({
    pluginID: id,
    src: rootURI + "prefs.xhtml",
    scripts: [rootURI + "prefs-pane.js"],
    label: "zotobs-io",
  });
  for (const w of Zotero.getMainWindows()) zotobsAddMenu(w);
  zotobsRegisterReader(id);
  ZotobsBridge.version = version;
  ZotobsBridge.register();
  ZotobsBridge.log("iniciado v" + version);
}
function shutdown() {
  ZotobsBridge.unregister();
  zotobsUnregisterReader();
  for (const w of Zotero.getMainWindows()) zotobsRemoveMenu(w);
  if (zotobsPaneID) Zotero.PreferencePanes.unregister?.(zotobsPaneID);
  delete Zotero.Zotobs;
}
function onMainWindowLoad({ window }) { zotobsAddMenu(window); }
function onMainWindowUnload({ window }) { zotobsRemoveMenu(window); }
