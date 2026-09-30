#!/usr/bin/env python3
"""Empacota a extensão e prepara a atualização automática. Funciona em macOS, Linux e Windows.

    python3 extension/build.py            # gera build/zotobs-bridge-<versão>.xpi (+ .sha256)
    python3 extension/build.py --updates  # também reescreve extension/updates.json

O .xpi é reprodutível (datas fixas no zip): o mesmo código gera o mesmo hash, que é o
`update_hash` de updates.json. Publique EXATAMENTE o arquivo gerado (ver docs/RELEASE.md).
"""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = ["manifest.json", "bootstrap.js", "export.js", "prefs.js", "prefs.xhtml", "prefs-pane.js"]
REPO = "zepadovani/zotobs-io"


def build() -> tuple[Path, str, str]:
    manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    ver = manifest["version"]
    out = HERE / "build" / f"zotobs-bridge-{ver}.xpi"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in FILES:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, (HERE / name).read_bytes())
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    out.with_name(out.name + ".sha256").write_text(f"{sha}  {out.name}\n")
    return out, ver, sha


def write_updates(ver: str, sha: str, xpi_name: str):
    manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    app = manifest["applications"]["zotero"]
    data = {"addons": {app["id"]: {"updates": [{
        "version": ver,
        "update_link": f"https://github.com/{REPO}/releases/download/v{ver}/{xpi_name}",
        "update_hash": f"sha256:{sha}",
        "applications": {"zotero": {"strict_min_version": app["strict_min_version"]}},
    }]}}}
    (HERE / "updates.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--updates", action="store_true", help="reescreve updates.json para esta versão")
    a = ap.parse_args()
    out, ver, sha = build()
    print(f"gerado: {out}\nsha256: {sha}")
    if a.updates:
        write_updates(ver, sha, out.name)
        print("updates.json atualizado")
