var ZotobsPrefs = {
  init() {
    const btn = document.getElementById("zotobs-choose-dir");
    if (btn.dataset.bound) return;
    btn.dataset.bound = "1";
    btn.addEventListener("command", async () => {
      const dir = await Zotero.Zotobs.pickFolder(window, "Pasta padrão de exportação");
      if (!dir) return;
      Zotero.Prefs.set("extensions.zotobs.export_dir", dir, true);
      document.getElementById("zotobs-export-dir").value = dir;
    });
  },
};
