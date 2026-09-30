# zotobs-io

Anotações do **Zotero** ⇄ **Markdown/Obsidian**, de forma determinística e
utilizável por agentes de IA (Claude Code, opencode, Gemini/Antigravity) ou
direto no terminal.

- **Exportar** destaques, sublinhados, notas, texto livre, imagens e desenhos
  (com o texto que o desenho cobre) do leitor do Zotero para Markdown/JSON,
  com link `zotero://` de volta à anotação.
- **Importar** comentários escritos no Obsidian (ou gerados por um agente
  após ler o PDF) como **anotações nativas do Zotero**, que aparecem no leitor
  na página certa.
- **Converter** entre anotações do Zotero (no banco) e anotações embutidas no
  PDF, nos dois sentidos.

> Por que isso é necessário: o leitor do Zotero **não grava as anotações no
> PDF**; elas vivem no banco `zotero.sqlite`. Ferramentas comuns de PDF não as
> enxergam. Veja [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Início rápido

```bash
git clone git@github.com:zepadovani/zotobs-io.git ~/repositorios/zotero   # ou já estar aqui
cd ~/repositorios/zotero
./install.sh --all            # skill para os agentes + atalho `zotobs` + modelo de config
# (opcional, para escrever anotações no Zotero) crie a chave: docs/API-KEY.md

zotobs info    "/caminho/artigo.pdf"                       # o Zotero reconhece este PDF?
zotobs extract "/caminho/artigo.pdf" -o notas.md --imagens notas_img
zotobs add     "/caminho/artigo.pdf" notas.md --dry-run     # valida as marcações do .md
zotobs add     "/caminho/artigo.pdf" notas.md               # cria no Zotero
```

Requisitos: macOS/Linux, Zotero 7+ (testado no 10.0.4), [`uv`](https://docs.astral.sh/uv/)
(baixa o `pymupdf` sozinho; sem `uv`, use `pip install pymupdf` e `python3`).

## Como uma anotação chega ao Zotero

```
 nota Markdown (Obsidian) ─┐
 JSON (agente)            ─┴─►  zotobs add  ──►  1. Web API do Zotero     (padrão, precisa de chave e rede)
                                                 2. Snippet JS (--offline) (colar em Run JavaScript)
                                                 3. [futuro] extensão local (sem rede, sem colar)
                                                 4. --destino pdf          (embutida no arquivo)
```

Rodar de novo o mesmo arquivo **não duplica**: cada anotação tem chave
determinística.

## Documentação

| Documento | Para quê |
|---|---|
| [docs/INSTALL.md](docs/INSTALL.md) | Instalação em Claude Code, opencode, Antigravity/Gemini e uso solo |
| [docs/API-KEY.md](docs/API-KEY.md) | **Como gerar a chave da API do Zotero** (para quem nunca fez) |
| [docs/USAGE.md](docs/USAGE.md) | Receitas de uso de cada comando |
| [docs/OBSIDIAN.md](docs/OBSIDIAN.md) | Fluxo Obsidian ⇄ Zotero e sintaxe da nota |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Modelo de dados, decisões e limites |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Erros conhecidos e soluções |
| [docs/PLUGIN-PLAN.md](docs/PLUGIN-PLAN.md) | Plano da extensão do Zotero (modo offline automático) |
| [skills/zotero-anotacoes/SKILL.md](skills/zotero-anotacoes/SKILL.md) | Instruções que os agentes leem |

## Estado

| Recurso | Estado |
|---|---|
| extract (banco + PDF, md/json, imagens, desenhos + texto coberto) | ✅ testado em PDF real |
| add nativo via Web API | ✅ testado ponta a ponta |
| add nativo via snippet JS (`--offline`) | ✅ testado no Zotero 10.0.4 |
| add embutido no PDF, `embed`, `strip` | ✅ testado |
| Extensão do Zotero | 📝 planejada (docs/PLUGIN-PLAN.md) |
| Editar comentário de anotação já existente | ⏳ roteiro |

## Nomes internos

O projeto se chama **zotobs-io**; o CLI/skill ainda usa o nome de origem
(`zotero_anot.py`, skill `zotero-anotacoes`, pasta de config
`~/.config/zotero-anot`). O atalho de terminal é `zotobs`.

## Testes

```bash
make test
```

## Autoria

José Henrique Padovani — <zepadovani@gmail.com>
