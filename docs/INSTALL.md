# Instalação

## Requisitos

- macOS ou Linux (testado em macOS). Zotero 7 ou superior (testado no 10.0.4).
- [`uv`](https://docs.astral.sh/uv/) — recomendado. O script declara suas
  dependências (`pymupdf`) no próprio cabeçalho (PEP 723) e `uv run --script`
  as instala em cache isolado. Sem `uv`: `pip install pymupdf` e `python3 skills/zotero-anotacoes/scripts/zotero_anot.py ...`.
- Nada é instalado no Python global.

## Instalação rápida

```bash
git clone git@github.com:zepadovani/zotobs-io.git ~/repositorios/zotero
cd ~/repositorios/zotero
./install.sh --all
```

`install.sh` cria **symlinks** (não copia) da skill para as pastas de skills
dos agentes, instala `~/.local/bin/zotobs` e um `config.json` de modelo.
Não sobrescreve diretórios existentes: se já houver uma cópia real da skill
no destino, ele avisa e pula (mova-a antes).

| Opção | Pasta | Quem lê |
|---|---|---|
| `--claude` | `~/.claude/skills` | Claude Code (e o opencode também lê esta pasta) |
| `--agents` | `~/.agents/skills` | padrão compartilhado (Antigravity/Gemini e outros) |
| `--opencode` | `~/.config/opencode/skills` | opencode |

Garanta que `~/.local/bin` está no `PATH` para usar `zotobs`.

## Por agente

**Claude Code** — a skill `zotero-anotacoes` aparece na lista de skills; peça
"extraia as anotações deste PDF do Zotero". Sem instalação, também dá para
apontar: "leia skills/zotero-anotacoes/SKILL.md e faça …".

**opencode** — lê `~/.claude/skills` e `~/.config/opencode/skills`
(`./install.sh --claude` ou `--opencode`). Modelos que não seguem skills
automaticamente: cole no prompt "siga `skills/zotero-anotacoes/SKILL.md`".

**Antigravity / Gemini** — instale com `--agents` (ou copie/symlink para a
pasta de skills do workspace, `.agent/skills/`). Peça explicitamente para
usar a skill `zotero-anotacoes`.

**Sem agente** — use `zotobs` no terminal ([USAGE.md](USAGE.md)).

O que os agentes precisam: acesso a shell e permissão de leitura em
`~/Zotero` (ou onde estiver seu diretório de dados) e nos PDFs.

## Configuração do Zotero

Nada a configurar em geral: o `prefs.js` do perfil do Zotero informa o
diretório de dados e a pasta base de anexos vinculados. Se o seu não for
detectado:

```bash
zotobs --zotero-dir ~/Zotero --base-dir /caminho/base/dos/anexos info arquivo.pdf
# ou: export ZOTERO_DATA_DIR=... ZOTERO_BASE_DIR=...
```

## Chave da API (para escrever no Zotero)

Veja [API-KEY.md](API-KEY.md). Sem ela, `extract` funciona normalmente e
`add` usa o modo offline.

## Verificar

```bash
make test                       # testes automáticos
zotobs info "/caminho/artigo.pdf"
```

## Desinstalar

```bash
rm ~/.claude/skills/zotero-anotacoes ~/.agents/skills/zotero-anotacoes \
   ~/.config/opencode/skills/zotero-anotacoes ~/.local/bin/zotobs   # só symlinks
rm -r ~/.config/zotero-anot ~/.cache/zotero-anot                   # config e backups (opcional)
```
