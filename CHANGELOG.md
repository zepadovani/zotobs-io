# Changelog

## Não lançado
- **Flags do CLI em inglês** (`--output`, `--source`, `--types`, `--pages`, `--images`, `--if-exists`,
  `--dest`, `--author`, `--strict`, `--no-plugin`, `--all`). Os nomes e valores antigos em português
  seguem aceitos como apelidos, então nada quebra. Documentação e testes migrados.

## zotobs-bridge 0.1.0 (plugin) e novidades do CLI — 2026-09-30
- **Plugin `zotobs-bridge` para o Zotero 7+** (`extension/`): recebe anotações do CLI
  por endpoint local com token (`/zotobs/import`, `/zotobs/update`), exporta anotações para
  Markdown (menu do botão direito, botões e menu no leitor de PDF, painel de
  configurações com pasta padrão) e usa o CLI para desenhos/texto coberto/mescla.
- `add` tenta o plugin antes da Web API e do snippet; `sync-md` e `bridge-token` novos;
  envio em lotes e mensagens de erro acionáveis.
- **Formato Markdown novo**: um bloco por anotação (link + trecho colorido em `span`,
  comentário logo abaixo), páginas como `#### p. N` com link; trechos do texto em aspas e itálico.
- **Reexportar mesclando** (`--se-existe mesclar`, padrão): mantém o que o usuário escreveu
  entre as anotações; backup da nota anterior; remove imagens órfãs.
- M4: `extension/build.py` (xpi reprodutível + `updates.json`), [docs/RELEASE.md](docs/RELEASE.md).
- Portabilidade (não testada fora do macOS): `bin/zotobs.cmd`, `install.ps1`, detecção de
  perfil do Zotero no Windows, execução do CLI por plataforma, área de transferência
  (`wl-copy`/`xclip`/`clip`).
- Documentação de instalação reescrita para iniciantes (instalação do `uv`, por sistema).

## CLI 0.1.0 — 2026-09-30
- extract: banco do Zotero + anotações embutidas, Markdown/JSON, imagens com o
  traço, texto coberto por desenhos na margem, links `zotero://`.
- add: anotações nativas via Web API (padrão) com fallback para snippet JS
  (`--offline`); destino `pdf`/`ambos`; entrada JSON ou Markdown do Obsidian;
  idempotente por chave determinística.
- embed (Zotero → PDF), strip, info, pages.
- Skill `zotero-anotacoes` para Claude Code, opencode e Antigravity.
- Documentação e plano da extensão do Zotero.
