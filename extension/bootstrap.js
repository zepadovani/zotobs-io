/* zotobs-bridge — plugin bootstrapped do Zotero 7+.
 *
 * Registra endpoints em http://127.0.0.1:23119/zotobs/* :
 *   GET  /zotobs/ping    -> {ok, version, zotero}
 *   POST /zotobs/import  -> cria anotações (mesmo JSON do snippet do CLI)
 *   POST /zotobs/update  -> altera comentário/tags de anotações já existentes
 *
 * Segurança: exige o cabeçalho X-Zotobs-Token igual ao conteúdo de
 * ~/.config/zotero-anot/bridge_token (criado por `zotobs bridge-token`) e
 * recusa requisições com Origin (navegadores). Só cria anotações.
 */
var ZotobsBridge = {
  id: "zotobs-bridge@zotobs-io",
  version: "0.1.0",
  MAX_ITEMS: 500,
  endpoints: ["/zotobs/ping", "/zotobs/import", "/zotobs/update"],

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
        if (await it.saveTx()) out.atualizadas.push(d.key); else out.inalteradas.push(d.key);
      } catch (e) {
        this.log("falha em " + d.key + ": " + e);
        out.falhas.push((d.key || "?") + ": " + e.message);
      }
    }
    this.log("update: " + out.atualizadas.length + " atualizadas, " + out.falhas.length + " falhas");
    return this.reply(200, out);
  },

  register() {
    const self = this;
    const E = Zotero.Server.Endpoints;
    E["/zotobs/ping"] = function () {};
    E["/zotobs/ping"].prototype = {
      supportedMethods: ["GET"],
      init: async function (req) {
        if (!(await self.authorized(req))) return self.reply(403, { error: "token" });
        return self.reply(200, { ok: true, version: self.version, zotero: Zotero.version });
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
  },

  unregister() {
    for (const p of this.endpoints) delete Zotero.Server.Endpoints[p];
  },
};

function install() {}
function uninstall() {}
var zotobsRootURI = null, zotobsPaneID = null;

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
  ZotobsBridge.version = version;
  ZotobsBridge.register();
  ZotobsBridge.log("iniciado v" + version);
}
function shutdown() {
  ZotobsBridge.unregister();
  for (const w of Zotero.getMainWindows()) zotobsRemoveMenu(w);
  if (zotobsPaneID) Zotero.PreferencePanes.unregister?.(zotobsPaneID);
  delete Zotero.Zotobs;
}
function onMainWindowLoad({ window }) { zotobsAddMenu(window); }
function onMainWindowUnload({ window }) { zotobsRemoveMenu(window); }
