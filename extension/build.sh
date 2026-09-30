#!/usr/bin/env bash
# Empacota a extensão em build/zotobs-bridge.xpi (um zip com manifest.json na raiz).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build
rm -f build/zotobs-bridge.xpi
zip -q -r build/zotobs-bridge.xpi manifest.json bootstrap.js
echo "gerado: $(pwd)/build/zotobs-bridge.xpi"
