# zotobs-io

🇬🇧 [English version: README.md](README.md) · 🇧🇷 Português

Anotações do **Zotero** ⇄ **Markdown/Obsidian**, nos dois sentidos, com um
**plugin para o Zotero** e um **comando de terminal** (`zotobs`) que também
pode ser usado por agentes de IA (qualquer agente que execute comandos de shell).

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
é um plugin do Obsidian para **citar e importar referências** (e, em mão
única, anotações) de dentro do Obsidian. O zotobs-io trata das **anotações em
si**: roda no Zotero e no terminal, funciona **nos dois sentidos** (cria e
edita anotações nativas do Zotero), **mescla** reexportações com notas que você
editou, captura desenhos e áreas de imagem e pode ser operado por um agente.
Eles se complementam; use os dois se quiser.

## Casos de uso

Os comandos abaixo supõem o atalho `zotobs` instalado
([docs/INSTALL.md](docs/INSTALL.md)). No Zotero, o plugin faz a mesma
exportação pelo botão direito e pelos botões do leitor de PDF.

### Sem agente

**1. Exportar suas anotações de leitura para o Obsidian**
```bash
zotobs extract artigo.pdf -o Vault/artigo.md --images Vault/artigo_img
```
Você recebe um bloco por anotação — o trecho na cor do destaque, um link que
abre o ponto exato no Zotero e o seu comentário logo abaixo:

```markdown
#### p. 12
> [↗](zotero://open-pdf/…) <span style="background:#ffd40066;"><i>“o trecho citado”</i></span>
> meu comentário
```

**2. Continuar escrevendo na nota e reexportar depois.** Acrescente parágrafos
seus entre os blocos, anote mais no Zotero e rode o mesmo comando (ou o botão
do plugin) de novo: escolha **Mesclar** e os blocos são atualizados enquanto o
que você escreveu entre eles fica no lugar.

**3. Anotar no Obsidian e enviar ao Zotero.** Sob o título de uma página,
escreva um trecho que exista nela, `::` e o seu comentário:
```markdown
## p. 3
> trecho literal da página :: por que importa {verde}
- :: comentário geral sobre esta página {laranja}
```
```bash
zotobs add artigo.pdf notas.md --dry-run   # confere se todos os trechos são achados
zotobs add artigo.pdf notas.md             # cria anotações nativas no Zotero
```
Rodar de novo não cria duplicatas.

**4. Editar comentários no Obsidian e devolver as edições.** Altere um
comentário ou uma `#tag` na nota exportada e rode:
```bash
zotobs sync-md artigo.pdf Vault/artigo.md --dry-run
zotobs sync-md artigo.pdf Vault/artigo.md
```

### Com agente

Dê a qualquer agente que execute comandos de shell as instruções de
[`skills/zotero-anotacoes/SKILL.md`](skills/zotero-anotacoes/SKILL.md) e peça
em linguagem natural. O agente só roda os mesmos comandos determinísticos,
então você sempre pode prever (`--dry-run`) e revisar antes de algo chegar ao Zotero.

**5. Perguntar sobre as suas próprias anotações**
> “Resuma meus destaques e comentários em `artigo.pdf`, agrupados por tema, e
> liste as dúvidas que deixei em aberto.”

O agente lê as anotações com `zotobs extract artigo.pdf --json`.

**6. Deixar o agente anotar o artigo por você**
> “Leia `artigo.pdf` e destaque as passagens que definem o método principal,
> com um comentário de uma linha em cada.”

O agente escreve as anotações no formato Markdown/JSON do `zotobs add`, valida
com `--dry-run` e, com a sua concordância, as cria no Zotero. Elas recebem por
padrão a tag `agente`, para você filtrar, revisar ou apagar exatamente o que o
agente adicionou.

**7. Ciclo de revisão entre você e um agente**
> “Escreva um rascunho de comentário para cada destaque meu que está sem
> comentário, na nota exportada.”

Você lê os rascunhos no Obsidian, edita o que quiser e os envia ao Zotero com
`zotobs sync-md`.

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
zotobs extract "/caminho/artigo.pdf" -o notas.md --images notas_img
```

Os flags são em inglês (`--output`, `--source`, `--types`, `--pages`, `--images`,
`--if-exists`, `--dest`, …); os nomes antigos em português (`--saida`, `--fonte`, …)
continuam funcionando como apelidos. Tabela completa em [docs/USAGE.md](docs/USAGE.md).

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
                                                 4. --dest pdf        (embutida no arquivo)
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
