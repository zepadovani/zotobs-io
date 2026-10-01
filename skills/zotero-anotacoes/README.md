# zotero-anotacoes

CLI determinística (`scripts/zotero_anot.py`) + SKILL.md para agentes.
Extrai anotações do Zotero/PDF para Markdown/JSON e grava anotações no PDF.

## Uso rápido
    uv run --script scripts/zotero_anot.py info    arquivo.pdf
    uv run --script scripts/zotero_anot.py extract arquivo.pdf -o notas.md --images notas_img
    uv run --script scripts/zotero_anot.py add     arquivo.pdf marcas.json --dry-run
    uv run --with pymupdf --with pytest pytest tests/ -q

## Instalar em outros agentes
Formato SKILL.md padrão. opencode lê `~/.claude/skills`; Antigravity/Gemini e
outros leem `~/.agents/skills` ou `.agent/skills`: `ln -s ~/.claude/skills/zotero-anotacoes ~/.agents/skills/`.

## Como virar repositório próprio
1. `git init zotero-anot`; mover `scripts/zotero_anot.py` para `src/zotero_anot/` dividindo em
   `zdb.py` (banco), `extract.py`, `write.py`, `cli.py` (as seções já estão separadas por comentários).
2. `pyproject.toml` com `dependencies=["pymupdf"]` e `[project.scripts] zotero-anot = ...`.
3. Manter SKILL.md como fina camada de instruções; testes em `tests/`.

## Roteiro
- [x] extract (banco + PDF, md/json, imagens com traço, texto coberto por desenho, links zotero://)
- [x] add nativo via Web API (padrão) com fallback JS; add embutido (`--dest pdf`); entrada JSON ou Markdown
- [x] embed (Zotero -> PDF, todos os tipos), strip
- [ ] testar a Web API com chave real (a implementação segue a doc; só o fallback foi exercitado)
- [ ] `sync-md`: editar comentário de anotação existente pelo .md (PATCH com versão)
- [ ] add de image/ink; mapa cor -> significado configurável (verde=definição, vermelho=objeção)
