#!/usr/bin/env bash
# Instala a skill (symlinks) nos diretórios de skills dos agentes, o atalho `zotobs`
# e um config.json de exemplo. Não sobrescreve nada existente sem --force.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
SKILL="$ROOT/skills/zotero-anotacoes"
FORCE=0; TARGETS=()
usage() { cat <<U
uso: ./install.sh [--claude] [--agents] [--opencode] [--all] [--force]
  --claude    ~/.claude/skills         (Claude Code; opencode também lê esta pasta)
  --agents    ~/.agents/skills         (padrão compartilhado; Antigravity/Gemini e outros)
  --opencode  ~/.config/opencode/skills
  --all       os três acima
  --force     substitui destino existente (só se for symlink ou você confirmar)
Também instala ~/.local/bin/zotobs e cria ~/.config/zotero-anot/config.json (modelo).
U
}
for a in "$@"; do case $a in
  --claude) TARGETS+=("$HOME/.claude/skills");;
  --agents) TARGETS+=("$HOME/.agents/skills");;
  --opencode) TARGETS+=("$HOME/.config/opencode/skills");;
  --all) TARGETS+=("$HOME/.claude/skills" "$HOME/.agents/skills" "$HOME/.config/opencode/skills");;
  --force) FORCE=1;;
  -h|--help) usage; exit 0;;
  *) usage; exit 1;;
esac; done
[ ${#TARGETS[@]} -eq 0 ] && { usage; exit 1; }
command -v uv >/dev/null || echo "aviso: 'uv' não encontrado (https://docs.astral.sh/uv/). Alternativa: pip install pymupdf e usar python3."
for t in "${TARGETS[@]}"; do
  mkdir -p "$t"; dest="$t/zotero-anotacoes"
  if [ -L "$dest" ]; then ln -sfn "$SKILL" "$dest"; echo "atualizado: $dest"
  elif [ -e "$dest" ]; then
    if [ $FORCE -eq 1 ]; then echo "existe e NÃO é symlink: $dest — remova manualmente (ou faça backup) e rode de novo"; else echo "pulado (já existe): $dest  [--force não apaga diretórios reais; mova-o antes]"; fi
  else ln -s "$SKILL" "$dest"; echo "instalado: $dest -> $SKILL"; fi
done
mkdir -p "$HOME/.local/bin"; ln -sfn "$ROOT/bin/zotobs" "$HOME/.local/bin/zotobs"; echo "atalho: ~/.local/bin/zotobs (confira se está no PATH)"
CFG="$HOME/.config/zotero-anot/config.json"
if [ ! -e "$CFG" ]; then mkdir -p "$(dirname "$CFG")"; printf '{\n  "api_key": "COLE_A_CHAVE_AQUI"\n}\n' > "$CFG"; chmod 600 "$CFG"; echo "modelo criado: $CFG  (veja docs/API-KEY.md)"; fi
