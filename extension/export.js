/* zotobs-bridge — exportação de anotações para Markdown (mesmo formato de
 * `zotobs extract`, para que `zotobs sync-md` continue valendo).
 * Carregado por bootstrap.js; define Zotero.Zotobs. */
(function () {
  const TYPE = { note: "nota", text: "texto", image: "imagem", ink: "desenho" };
  const P = "extensions.zotobs.";
  const short = (t, n) => (t.length <= n ? t : t.slice(0, n - 1) + "…");
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
      const esc = (t) => (t || "").split(/\s+/).filter(Boolean).join(" ").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
      for (const a of anns) {
        const pg = JSON.parse(a.annotationPosition).pageIndex + 1;
        if (pg !== page) {
          page = pg;
          const lab = a.annotationPageLabel && String(a.annotationPageLabel) !== String(pg)
            ? ` (impresso: ${a.annotationPageLabel})` : "";
          L.push(`#### p. ${pg}${lab}`, `[↗ abrir página](zotero://open-pdf/library/items/${att.key}?page=${pg})`, "");
        }
        const hex = (a.annotationColor || "").toLowerCase(), typ = a.annotationType;
        const link = `[↗](zotero://open-pdf/library/items/${att.key}?page=${pg}&annotation=${a.key})`;
        let head;
        if (typ === "highlight") head = hex ? `<span style="background:${hex}66;"><i>“${esc(a.annotationText)}”</i></span>` : `<i>“${esc(a.annotationText)}”</i>`;
        else if (typ === "underline") head = `<span style="text-decoration:underline;${hex ? `text-decoration-color:${hex};` : ""}text-decoration-thickness:2px;"><i>“${esc(a.annotationText)}”</i></span>`;
        else head = `<span style="${hex ? `color:${hex};` : ""}font-weight:bold;">${TYPE[typ] || typ}</span>`;
        const tags = a.getTags().map((t) => t.tag);
        if (tags.length) head += " <small>" + tags.map((t) => "#" + t.replaceAll(" ", "_")).join(" ") + "</small>";
        L.push(`> ${link} ${head}  `);
        if (imgRelByKey.has(a.key)) L.push(`> ![](${imgRelByKey.get(a.key).replaceAll(" ", "%20")})`);
        const body = a.annotationComment || (["note", "text"].includes(typ) ? a.annotationText : "");
        for (const ln of (body || "").split("\n")) if (body) L.push(ln ? "> " + ln : ">");
        L.push("");
      }
      return L.join("\n").replace(/\s+$/, "") + "\n";
    },

    /** CLI zotobs: caminho configurado, ou ~/.local/bin/zotobs(.cmd), ou o clone local do projeto. */
    async findCli() {
      if (!pref("use_cli")) return null;
      const home = Services.dirsvc.get("Home", Ci.nsIFile).path, ext = Zotero.isWin ? ".cmd" : "";
      const cands = [pref("cli_path"), PathUtils.join(home, ".local", "bin", "zotobs" + ext),
        PathUtils.join(home, "repositorios", "zotobs-io", "bin", "zotobs" + ext)];
      for (const c of cands) if (c && (await IOUtils.exists(c))) return c;
      return null;
    },

    /** Exportação completa pelo CLI (desenhos sobre imagens, texto coberto, recortes).
     *  Retorna "" se deu certo; senão, o fim do log do CLI. */
    async exportViaCli(cli, file, mdPath, imgDir, mode) {
      const tmp = Services.dirsvc.get("TmpD", Ci.nsIFile).path;
      const log = PathUtils.join(tmp, "zotobs-export.log");
      const t0 = Date.now() - 1000;
      try {
        if (Zotero.isWin) {
          // Windows (não testado): script .cmd temporário, evita problemas de aspas
          const q = (x) => '"' + x.replaceAll('"', "") + '"';
          const bat = PathUtils.join(tmp, "zotobs-export.cmd");
          await IOUtils.writeUTF8(bat, "@echo off\r\nchcp 65001 >nul\r\n" +
            'set "PATH=%USERPROFILE%\\.local\\bin;%PATH%"\r\n' +
            `call ${q(cli)} extract ${q(file)} -o ${q(mdPath)} --images ${q(imgDir)} --if-exists ${mode} > ${q(log)} 2>&1\r\n`);
          await Zotero.Utilities.Internal.exec("cmd.exe", ["/d", "/c", bat]);
        } else {
          // macOS (testado: zsh) / Linux (não testado: bash). PATH explícito: o Zotero não herda o do terminal.
          const sh = Zotero.isMac ? "/bin/zsh" : "/bin/bash";
          await Zotero.Utilities.Internal.exec(sh,
            ["-lc", 'export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"; "$0" extract "$1" -o "$2" --images "$3" --if-exists "$5" >"$4" 2>&1',
              cli, file, mdPath, imgDir, log, mode]);
        }
      } catch (e) { Zotero.debug("[zotobs-bridge] CLI: " + e + " (log em " + log + ")"); }
      if ((await IOUtils.exists(mdPath)) && (await IOUtils.stat(mdPath)).lastModified >= t0) return "";
      try { return (await IOUtils.readUTF8(log)).trim().split("\n").slice(-2).join(" | "); }
      catch (e) { return "falha desconhecida"; }
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
      let mode = "overwrite";
      if (await IOUtils.exists(mdPath)) {
        const S = Services.prompt, F = S.BUTTON_TITLE_IS_STRING;
        const r = S.confirmEx(win, "zotobs",
          `“${short(base, 60)}.md” já existe em\n${short(outDir, 70)}\n\n` +
          "Mesclar mantém o que você escreveu entre as anotações e atualiza o resto; sobrescrever recria o arquivo.",
          S.BUTTON_POS_0 * F + S.BUTTON_POS_1 * F + S.BUTTON_POS_2 * F,
          "Mesclar (manter o que escrevi)", "Sobrescrever", "Cancelar", null, {});
        if (r === 2) return { skipped: "cancelado" };
        mode = r === 0 ? "merge" : "overwrite";
      }
      await IOUtils.makeDirectory(outDir, { ignoreExisting: true, createAncestors: true });

      const cli = await Z.findCli();
      let cliErr = null;
      if (cli && file) {
        cliErr = await Z.exportViaCli(cli, file, mdPath, PathUtils.join(outDir, base + "_img"), mode);
        if (cliErr === "") return { path: mdPath, n: anns.length, via: "CLI" };
      }

      if (mode === "merge" &&
          !Services.prompt.confirm(win, "zotobs", "Sem o CLI zotobs não é possível mesclar.\n\nSobrescrever o arquivo? (o que você escreveu nele será perdido)"))
        return { skipped: "cancelado (mesclar exige o CLI)" };

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
      return { path: mdPath, n: anns.length, cliErr };
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
          if (r.path) {
            ok++;
            pw.addDescription(`✓ ${short(PathUtils.filename(r.path).replace(/\.md$/, ""), 45)} — ${r.n} anotações` +
              (r.via ? " (via CLI)" : ` (sem desenhos/texto coberto: ${r.cliErr ? "CLI falhou — " + short(r.cliErr, 80) : "CLI não encontrado"})`));
          }
          else pw.addDescription(`${att.attachmentFilename}: ${r.skipped}`);
        } catch (e) {
          Zotero.logError(e);
          pw.addDescription(`erro em ${att.attachmentFilename}: ${e.message}`);
        }
      }
      if (ok) pw.addDescription("em " + short(root, 55));
      pw.show();
      pw.startCloseTimer(8000);
    },
  };
  Zotero.Zotobs = Z;
})();
