/* zotobs-bridge — exportação de anotações para Markdown (mesmo formato de
 * `zotobs extract`, para que `zotobs sync-md` continue valendo).
 * Carregado por bootstrap.js; define Zotero.Zotobs. */
(function () {
  const COLORS = {
    "#ffd400": "amarelo", "#ff6666": "vermelho", "#5fb236": "verde", "#2ea8e5": "azul",
    "#a28ae5": "roxo", "#e56eee": "magenta", "#f19837": "laranja", "#aaaaaa": "cinza",
  };
  const EMOJI = { amarelo: "🟡", vermelho: "🔴", verde: "🟢", azul: "🔵", roxo: "🟣", magenta: "🟣", laranja: "🟠", cinza: "⚪" };
  const TYPE = { highlight: "destaque", underline: "sublinhado", note: "nota", text: "texto livre", image: "imagem", ink: "desenho" };
  const P = "extensions.zotobs.";
  const pref = (k) => Zotero.Prefs.get(P + k, true);

  const Z = {
    async pickFolder(win, title) {
      const { FilePicker } = ChromeUtils.importESModule("chrome://zotero/content/modules/filePicker.mjs");
      const fp = new FilePicker();
      fp.init(win, title, fp.modeGetFolder);
      return (await fp.show()) === fp.returnOK ? fp.file : null;
    },

    /** Itens selecionados -> anexos PDF únicos (aceita item pai ou anexo). */
    pdfAttachments(items) {
      const seen = new Map();
      for (const it of items) {
        const atts = it.isAttachment() ? [it] : it.isRegularItem() ? Zotero.Items.get(it.getAttachments()) : [];
        for (const a of atts) if (a.isPDFAttachment && a.isPDFAttachment()) seen.set(a.id, a);
      }
      return [...seen.values()];
    },

    buildMarkdown(att, parent, anns, imgRelByKey, pdfName) {
      const get = (f) => { try { return (parent && parent.getField(f)) || ""; } catch (e) { return ""; } };
      const title = get("title") || pdfName;
      const L = ["---", `title: "${title.replaceAll('"', "'")}"`];
      const ck = get("citationKey");
      if (ck) L.push(`citekey: ${ck}`);
      if (parent) L.push(`zotero_item: ${parent.key}`);
      const d = new Date(), z = (n) => String(n).padStart(2, "0");
      L.push(`pdf: "${pdfName}"`, `anotacoes: ${anns.length}`,
        `extraido_em: ${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())} ${z(d.getHours())}:${z(d.getMinutes())}`,
        "---", "", `# Anotações — ${title}`, "");
      const cont = new Map();
      for (const a of anns) cont.set(a.annotationType, (cont.get(a.annotationType) || 0) + 1);
      L.push("_" + [...cont].map(([t, n]) => `${n} ${t}`).join(", ") + "_", "");
      let page = null;
      for (const a of anns) {
        const pg = JSON.parse(a.annotationPosition).pageIndex + 1;
        if (pg !== page) {
          page = pg;
          const lab = a.annotationPageLabel && String(a.annotationPageLabel) !== String(pg)
            ? ` (impresso: ${a.annotationPageLabel})` : "";
          L.push(`## p. ${pg}${lab}`, "");
        }
        const hex = (a.annotationColor || "").toLowerCase();
        const cn = COLORS[hex] || hex;
        let head = `${EMOJI[cn] || "▫️"} **${TYPE[a.annotationType] || a.annotationType}**` + (cn ? ` · ${cn}` : "");
        const tags = a.getTags().map((t) => t.tag);
        if (tags.length) head += " · " + tags.map((t) => "#" + t.replaceAll(" ", "_")).join(" ");
        L.push(`${head} [↗](zotero://open-pdf/library/items/${att.key}?page=${pg}&annotation=${a.key})`);
        if (a.annotationText) L.push(...a.annotationText.split("\n").map((l) => "> " + l));
        if (imgRelByKey.has(a.key)) L.push(`![](${imgRelByKey.get(a.key).replaceAll(" ", "%20")})`);
        if (a.annotationComment) {
          L.push("", `**${["highlight", "underline", "image", "ink"].includes(a.annotationType) ? "Comentário" : "Conteúdo"}:** ${a.annotationComment}`);
        }
        L.push("");
      }
      return L.join("\n").replace(/\s+$/, "") + "\n";
    },

    /** Exporta um anexo. outDir = pasta final onde vão <nome>.md e <nome>_img/. */
    async exportOne(att, outDir, win) {
      const parent = att.parentItem;
      const file = await att.getFilePathAsync();
      const pdfName = file ? PathUtils.filename(file) : att.attachmentFilename;
      const base = Zotero.File.getValidFileName(pdfName.replace(/\.pdf$/i, ""));
      const anns = att.getAnnotations().sort((a, b) => (a.annotationSortIndex < b.annotationSortIndex ? -1 : 1));
      if (!anns.length) return { skipped: "sem anotações" };

      const mdPath = PathUtils.join(outDir, base + ".md");
      if (await IOUtils.exists(mdPath) &&
          !Services.prompt.confirm(win, "zotobs", `“${base}.md” já existe em\n${outDir}\n\nSobrescrever? (edições feitas na nota serão perdidas)`))
        return { skipped: "já existe (mantido)" };
      await IOUtils.makeDirectory(outDir, { ignoreExisting: true, createAncestors: true });

      const imgs = new Map();
      if (pref("export_images")) {
        const want = anns.filter((a) => a.annotationType === "image");
        if (want.length) {
          try { await Zotero.PDFRenderer.renderAttachmentAnnotations(att.id); } catch (e) { Zotero.debug("[zotobs-bridge] render: " + e); }
          for (const a of want) {
            try {
              if (!(await Zotero.Annotations.hasCacheImage(a))) continue;
              const dir = PathUtils.join(outDir, base + "_img");
              await IOUtils.makeDirectory(dir, { ignoreExisting: true });
              await IOUtils.copy(Zotero.Annotations.getCacheImagePath(a), PathUtils.join(dir, a.key + ".png"));
              imgs.set(a.key, `${base}_img/${a.key}.png`);
            } catch (e) { Zotero.debug("[zotobs-bridge] imagem " + a.key + ": " + e); }
          }
        }
      }
      await IOUtils.writeUTF8(mdPath, Z.buildMarkdown(att, parent, anns, imgs, pdfName));
      return { path: mdPath, n: anns.length };
    },

    /** mode "default": <pasta padrão>/<nome do PDF>/ ; mode "folder": <escolhida>/ direto. */
    async run(items, mode, win) {
      const atts = Z.pdfAttachments(items);
      const pw = new Zotero.ProgressWindow({ closeOnClick: true });
      pw.changeHeadline("zotobs — exportar anotações");
      if (!atts.length) { pw.addDescription("Selecione itens com PDF."); pw.show(); pw.startCloseTimer(4000); return; }
      let root = pref("export_dir");
      if (mode === "folder") root = await Z.pickFolder(win, "Exportar anotações para…");
      else if (!root) { pw.addDescription("Defina a pasta padrão em Configurações → zotobs."); pw.show(); pw.startCloseTimer(6000); return; }
      if (!root) return;
      let ok = 0;
      for (const att of atts) {
        try {
          let out = root;
          if (mode === "default") {
            const file = await att.getFilePathAsync();
            const base = Zotero.File.getValidFileName(PathUtils.filename(file || att.attachmentFilename).replace(/\.pdf$/i, ""));
            out = PathUtils.join(root, base);
          }
          const r = await Z.exportOne(att, out, win);
          if (r.path) { ok++; pw.addDescription(`${r.n} anotações → ${r.path}`); }
          else pw.addDescription(`${att.attachmentFilename}: ${r.skipped}`);
        } catch (e) {
          Zotero.logError(e);
          pw.addDescription(`erro em ${att.attachmentFilename}: ${e.message}`);
        }
      }
      pw.show();
      pw.startCloseTimer(8000);
    },
  };
  Zotero.Zotobs = Z;
})();
