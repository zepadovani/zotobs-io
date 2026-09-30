# Changelog

## 0.1.0 — 2026-09-30
- extract: banco do Zotero + anotações embutidas, Markdown/JSON, imagens com o
  traço, texto coberto por desenhos na margem, links `zotero://`.
- add: anotações nativas via Web API (padrão) com fallback para snippet JS
  (`--offline`); destino `pdf`/`ambos`; entrada JSON ou Markdown do Obsidian;
  idempotente por chave determinística.
- embed (Zotero → PDF), strip, info, pages.
- Skill `zotero-anotacoes` para Claude Code, opencode e Antigravity.
- Documentação e plano da extensão do Zotero.
