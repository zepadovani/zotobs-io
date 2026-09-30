# zotobs-io

🇬🇧 [English version: README.md](README.md) · 🇧🇷 Português

Anotações do **Zotero** ⇄ **Markdown/Obsidian**, nos dois sentidos, com um
**plugin para o Zotero** e um **comando de terminal** (`zotobs`) que também
pode ser usado por agentes de IA (Claude Code, opencode, Gemini/Antigravity).

- **Exportar** destaques, sublinhados, notas, texto livre, imagens e desenhos
  (com o texto que o desenho cobre e o recorte da página com o rabisco) do
  leitor do Zotero para Markdown/JSON. Cada anotação tem um link `zotero://`
  de volta ao leitor.
- **Reexportar sem perder o que você escreveu:** o que você insere entre as
  anotações na nota do Obsidian é mantido quando a nota é atualizada.
- **Enviar de volta:** comentários/tags editados no Obsidian viram edições nas
  anotações do Zotero (`sync-md`), e anotações escritas no Obsidian ou geradas
  por um agente viram **anotações nativas do Zotero**, na página certa.
- **Converter** anotações do Zotero em anotações embutidas no PDF, e vice-versa.

> Por que isso é necessário: o leitor do Zotero **não grava as anotações no
> PDF**; elas vivem no banco `zotero.sqlite`. Ferramentas comuns de PDF não as
> enxergam. Veja [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Como se diferencia do obsidian-zotero-integration

O [obsidian-zotero-integration](https://github.com/obsidian-community/obsidian-zotero-integration)
(hoje mantido em `community-archive/`) é um **plugin do Obsidian** muito usado
para inserir citações e bibliografias e para importar notas e anotações de PDF
do Zotero para o Obsidian; segundo o README dele, exige o Better BibTeX. É o
caminho certo se você quer **buscar e citar referências de dentro do Obsidian**.

O zotobs-io resolve outro problema e os dois se complementam:

| | obsidian-zotero-integration | zotobs-io |
|---|---|---|
| Onde roda | dentro do Obsidian | dentro do **Zotero** (plugin) e no **terminal** (CLI/agentes); o Obsidian só precisa abrir arquivos `.md` |
| Foco | citações, bibliografias, notas de leitura e importação de anotações para o Obsidian | o **ciclo das anotações** entre Zotero e Markdown |
| Direção | Zotero → Obsidian (conforme o README do projeto) | Zotero → Markdown **e** Markdown → Zotero |
| Escreve no Zotero | não descrito | sim: cria anotações nativas e edita comentário/tags de existentes |
| Reimportar sobre nota editada | — | **mescla**: atualiza os blocos e mantém o que você escreveu entre eles |
| Desenhos e imagens | — | recorte da página com o rabisco por cima e o texto coberto pelo desenho |
| Automação por IA | — | comando determinístico + *skill* para agentes |
| Depende de Better BibTeX | sim (README do projeto) | não |
| Funciona sem Obsidian | não | sim (qualquer editor de Markdown) |

Em resumo: use o obsidian-zotero-integration para **citar e importar
referências**; use o zotobs-io quando as **anotações** são o material de
trabalho — para revisá-las, comentá-las no Obsidian, devolvê-las ao Zotero ou
entregá-las a um agente. Nada impede usar os dois juntos.

## Comece por aqui

| Quero… | Leia |
|---|---|
| **Instalar** (inclui como instalar o `uv`; macOS/Linux/Windows) | [docs/INSTALL.md](docs/INSTALL.md) |
| Usar o plugin no Zotero e o fluxo com o Obsidian | [docs/OBSIDIAN.md](docs/OBSIDIAN.md) · [extension/README.md](extension/README.md) |
| Receitas de cada comando do terminal | [docs/USAGE.md](docs/USAGE.md) |
| Gerar a chave da API do Zotero (opcional) | [docs/API-KEY.md](docs/API-KEY.md) |
| Resolver um erro | [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) |
| Entender o modelo de dados e as decisões | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Publicar uma nova versão do plugin | [docs/RELEASE.md](docs/RELEASE.md) |
| Instruções que os agentes leem | [skills/zotero-anotacoes/SKILL.md](skills/zotero-anotacoes/SKILL.md) |

## Início rápido (macOS/Linux)

Detalhes e o passo a passo para iniciantes em [docs/INSTALL.md](docs/INSTALL.md).

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh     # instala o `uv` (abra um terminal novo depois)
git clone https://github.com/zepadovani/zotobs-io.git ~/repositorios/zotobs-io
cd ~/repositorios/zotobs-io
./install.sh --all                                   # comando `zotobs` + skill para agentes
zotobs info "/caminho/artigo.pdf"                    # o Zotero reconhece este PDF?
zotobs extract "/caminho/artigo.pdf" -o notas.md --imagens notas_img
```

Depois instale o plugin (arquivo `.xpi`) no Zotero: *Ferramentas → Plugins →
engrenagem → Install Plugin From File…*, e escolha a pasta de exportação em
*Configurações → zotobs-io*.

## Plataformas

| Sistema | Estado |
|---|---|
| **macOS** | ✅ desenvolvido e testado (Zotero 10.0.4) |
| **Linux** | ⚠️ **não testado** — escrito para funcionar (caminhos e `bash`); relatos são bem-vindos |
| **Windows** | ⚠️ **não testado** — há `install.ps1` e `zotobs.cmd`, mas nunca foram executados; relatos são bem-vindos |

Requer Zotero 7 ou mais novo. Como relatar um teste em Linux/Windows:
[docs/INSTALL.md → Ajude a testar](docs/INSTALL.md#ajude-a-testar-linux-e-windows).

## Como uma anotação chega ao Zotero

```
 nota Markdown (Obsidian) ─┐
 JSON (agente)            ─┴─►  zotobs add  ──►  1. Plugin zotobs-bridge (local, sem rede, sem chave)
                                                 2. Web API do Zotero    (precisa de chave e rede)
                                                 3. Snippet JS           (colar em Run JavaScript)
                                                 4. --destino pdf        (embutida no arquivo)
```

Rodar de novo o mesmo arquivo **não duplica**: cada anotação tem chave
determinística.

## Estado dos recursos

| Recurso | Estado |
|---|---|
| extract (banco + PDF, md/json, imagens, desenhos + texto coberto) | ✅ testado em PDF real |
| Plugin: exportar pelo menu do botão direito + configurações (via CLI) | ✅ testado no Zotero 10.0.4 (macOS) |
| Plugin: botões e menu dentro do leitor de PDF; diálogo “Mesclar/Sobrescrever” | ✅ testado no Zotero 10.0.4 (macOS) |
| Reexportar mesclando com a nota editada | ✅ testado (CLI e plugin) |
| add nativo pelo plugin / Web API / snippet JS | ✅ testado (Zotero aberto e fechado) |
| Editar comentário/tags de anotação existente (`sync-md`) | ✅ testado no Zotero 10.0.4 |
| add embutido no PDF, `embed`, `strip` | ✅ testado |
| Atualização automática do plugin (`updates.json`) | 🧪 pronta, depende de publicar uma release (ver [docs/RELEASE.md](docs/RELEASE.md)) |

## Licença

[GNU AGPL-3.0 ou posterior](LICENSE) (`AGPL-3.0-or-later`). Motivo: o CLI usa o
[PyMuPDF](https://pymupdf.readthedocs.io/), licenciado sob AGPL-3.0, e o Zotero
também é AGPL-3.0. Em termos práticos: você pode usar, estudar, modificar e
redistribuir; versões modificadas que você distribuir (ou oferecer como
serviço de rede) devem continuar sob a mesma licença, com o código-fonte.

## Nomes internos

O projeto se chama **zotobs-io**; o CLI/skill ainda usa o nome de origem
(`zotero_anot.py`, skill `zotero-anotacoes`, pasta de config
`~/.config/zotero-anot`). O atalho de terminal é `zotobs`.

## Testes

```bash
make test
```

## Autoria

José Henrique Padovani
