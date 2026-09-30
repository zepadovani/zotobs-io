# Uso

`zotobs` = atalho para `skills/zotero-anotacoes/scripts/zotero_anot.py`
(instalado por `./install.sh`). Sem o atalho:
`uv run --script skills/zotero-anotacoes/scripts/zotero_anot.py <comando>`.

Opções globais (antes do subcomando): `--zotero-dir` (padrão: lido do
`prefs.js` do Zotero, ou `~/Zotero`) e `--base-dir` (pasta base de anexos
vinculados). Variáveis: `ZOTERO_DATA_DIR`, `ZOTERO_BASE_DIR`.

## `info` — o Zotero conhece este PDF?

```bash
zotobs info "/caminho/artigo.pdf"
```
Mostra item, chave do anexo, citekey e contagens (banco do Zotero × embutidas).
Se disser "NÃO encontrado como attachment", o caminho do PDF não bate com o
que o Zotero registrou (veja `--base-dir` em [TROUBLESHOOTING](TROUBLESHOOTING.md)).

## `extract` — anotações → Markdown/JSON

```bash
zotobs extract artigo.pdf -o notas.md --imagens notas_img
zotobs extract artigo.pdf --json                       # para agentes
zotobs extract artigo.pdf --tipos highlight,note --paginas 80-90
zotobs extract artigo.pdf --fonte zotero               # só banco; pdf = só embutidas
```

O Markdown agrupa por página (com o número **impresso** quando difere do
índice do PDF), traz cor, texto destacado (`>`), comentário e um link
`zotero://open-pdf/...` que abre o leitor na anotação.

- **Desenho (caneta):** o PNG traz o traço por cima. Se o desenho está na
  margem, o texto das linhas cobertas pela extensão vertical do traço vira o
  texto da anotação (`texto_coberto: true`). Círculos/setas sobre figuras, ou
  muito largos, não geram texto.

## `add` — incluir anotações

Entrada: **Markdown** ([sintaxe](OBSIDIAN.md)) ou **JSON**.

```bash
zotobs add artigo.pdf marcas.md --dry-run     # valida, não grava
zotobs add artigo.pdf marcas.md               # padrão: nativa no Zotero
zotobs add artigo.pdf marcas.md --destino pdf     # embutida no PDF
zotobs add artigo.pdf marcas.md --destino ambos
cat marcas.json | zotobs add artigo.pdf -     # stdin
```

JSON (lista):

```json
[{"page_label": "57", "type": "highlight", "color": "green",
  "text": "trecho literal", "comment": "por que importa"},
 {"page": 9, "type": "note", "comment": "nota na margem"},
 {"page": 87, "type": "text", "comment": "caixa livre", "rect": [300, 60, 540, 110]}]
```

| Campo | Significado |
|---|---|
| `type` | `highlight`, `underline`, `note`, `text` |
| `page` / `page_label` | índice do PDF (base 1) ou número impresso ("ix", "57") |
| `text` | trecho **literal e contínuo** (obrigatório em highlight/underline) |
| `occurrence`, `context` | desambiguam trechos repetidos na página |
| `comment`, `color` | comentário; cor por nome ou `#rrggbb` |
| `point`, `rect` | posição (note / text) |

Cores: yellow/amarelo, red/vermelho, green/verde, blue/azul, purple/roxo,
magenta, orange/laranja, gray/cinza.

Opções úteis: `--tag agente` (tag nas anotações nativas; `''` remove),
`--autor NOME`, `--estrito` (aborta se algum item falhar), `--saida cópia.pdf`
(com `--destino pdf`).

### Como a escrita nativa escolhe o caminho

1. **Web API** se houver chave ([API-KEY.md](API-KEY.md)) e rede.
2. Senão, ou com `--offline`, gera o **snippet JS**.

### Modo offline (sem rede nem chave)

```bash
zotobs add artigo.pdf marcas.md --offline
```
O snippet fica em `~/.cache/zotero-anot/ultimo_import.js` e é copiado para a
área de transferência (`ZOTERO_ANOT_NO_CLIP=1` desliga). No Zotero:

1. **Ferramentas → Developer → Run JavaScript**
2. Apague o conteúdo anterior, cole (⌘V), mantenha **Run as async function** marcado
3. **Run** (⌘R). Resultado esperado: `criadas: N, puladas (já existiam): M`
4. As anotações aparecem no leitor na hora (sem precisar sincronizar).

### Idempotência

Cada anotação tem uma chave Zotero determinística (derivada de página, tipo,
texto e comentário). Reenviar o mesmo arquivo pula o que já existe — mesmo
alternando API e snippet JS.

## `embed` / `strip` — Zotero ⇄ PDF

```bash
zotobs embed artigo.pdf                       # anotações do banco → embutidas (inclui desenho/imagem)
zotobs embed artigo.pdf --saida copia.pdf --tipos highlight,note
zotobs strip artigo.pdf                       # remove só as embutidas criadas por este projeto
zotobs strip artigo.pdf --todas               # remove todas as embutidas
```
Alterações in-place fazem backup em `~/.cache/zotero-anot/backups/`
(`ZOTERO_ANOT_BACKUPS` muda a pasta). Depois, feche e reabra a aba do PDF no
Zotero. Para trazer ao banco anotações embutidas por *outros* programas, use o
próprio Zotero: no leitor, **Arquivo → Importar anotações…**

## `pages` — índice PDF ⇄ número impresso

```bash
zotobs pages artigo.pdf | head
```

## Com agentes

Instale a skill ([INSTALL.md](INSTALL.md)) e peça em linguagem natural:
"extraia minhas anotações deste PDF do Zotero para markdown", "marque na
introdução os trechos com problema de clareza, com comentários". O agente lê o
PDF, gera o JSON/Markdown, roda `--dry-run`, mostra o resumo e só então grava.
