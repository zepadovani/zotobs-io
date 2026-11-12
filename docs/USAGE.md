# Uso

`zotobs` = atalho para `skills/zotero-anotacoes/scripts/zotero_anot.py` (anotações)
e, para `libraries | collections | search | show | collection`, para
`skills/zotero-biblioteca/scripts/zotero_lib.py` (biblioteca; veja o fim deste arquivo).
Instalado por `./install.sh`. Sem o atalho:
`uv run --script skills/zotero-anotacoes/scripts/zotero_anot.py <comando>`.

Opções globais (antes do subcomando): `--zotero-dir` (padrão: lido do
`prefs.js` do Zotero, ou `~/Zotero`) e `--base-dir` (pasta base de anexos
vinculados). Variáveis: `ZOTERO_DATA_DIR`, `ZOTERO_BASE_DIR`.

## Nomes dos flags (inglês) e apelidos antigos

Os flags oficiais são em **inglês**. Os nomes antigos em português continuam
funcionando como apelidos (e os valores `ambas`/`ambos`/`mesclar`/`sobrescrever`
também), então scripts e instruções antigas não quebram.

| Flag | Apelido antigo | Valores |
|---|---|---|
| `-o`, `--output` | `--saida` | arquivo de saída |
| `--source` | `--fonte` | `auto`, `zotero`, `pdf`, `both` (`ambas`) |
| `--types` | `--tipos` | `highlight,underline,note,text,image,ink` |
| `--pages` | `--paginas` | faixa, ex.: `80-90` |
| `--images` | `--imagens` | pasta dos recortes PNG |
| `--if-exists` | `--se-existe` | `merge` (`mesclar`), `overwrite` (`sobrescrever`) |
| `--dest` | `--destino` | `zotero`, `pdf`, `both` (`ambos`) |
| `--author` | `--autor` | nome gravado nas anotações |
| `--strict` | `--estrito` | — |
| `--no-plugin` | `--sem-extensao` | — |
| `--all` | `--todas` | — |

Os demais (`--json`, `--tag`, `--offline`, `--dry-run`, `--zotero-dir`, `--base-dir`) já eram em inglês.

## `info` — o Zotero conhece este PDF?

```bash
zotobs info "/caminho/artigo.pdf"
```
Mostra item, chave do anexo, citekey e contagens (banco do Zotero × embutidas).
Se disser "NÃO encontrado como attachment", o caminho do PDF não bate com o
que o Zotero registrou (veja `--base-dir` em [TROUBLESHOOTING](TROUBLESHOOTING.md)).

## `extract` — anotações → Markdown/JSON

```bash
zotobs extract artigo.pdf -o notas.md --images notas_img
zotobs extract artigo.pdf --json                       # para agentes
zotobs extract artigo.pdf --types highlight,note --pages 80-90
zotobs extract artigo.pdf --source zotero               # só banco; pdf = só embutidas
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
zotobs add artigo.pdf marcas.md --dest pdf     # embutida no PDF
zotobs add artigo.pdf marcas.md --dest both
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

No JSON, cada anotação pode trazer as próprias tags: `"tags": ["liminal object", "lugar-escuta"]`
(elas não entram na chave da anotação). Opções úteis: `--tag agente` (tag somada a todas as
anotações nativas; `''` remove),
`--author NOME`, `--strict` (aborta se algum item falhar), `--output cópia.pdf`
(com `--dest pdf`).

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
zotobs embed artigo.pdf --output copia.pdf --types highlight,note
zotobs strip artigo.pdf                       # remove só as embutidas criadas por este projeto
zotobs strip artigo.pdf --all               # remove todas as embutidas
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


## `extract … --if-exists` — reexportar sobre uma nota existente

```bash
zotobs extract artigo.pdf -o notas.md --images notas_img                 # mescla (padrão)
zotobs extract artigo.pdf -o notas.md --images notas_img --if-exists overwrite
```
Mesclar atualiza os blocos pelo Zotero e mantém o que você escreveu entre eles
(ver [OBSIDIAN.md](OBSIDIAN.md)). Uma cópia da nota anterior fica em
`~/.cache/zotero-anot/backups/`.

## `sync-md` — levar edições do Markdown ao Zotero

```bash
zotobs sync-md artigo.pdf notas.md --dry-run     # mostra o que mudou
zotobs sync-md artigo.pdf notas.md               # grava (precisa do plugin com o Zotero aberto)
```
Sincroniza comentário e tags dos blocos exportados por `extract`.

**Tags na nota.** `extract --tag-style hash|link|both` escolhe a escrita: `#liminal_object` (padrão),
`[[liminal object]]` ou as duas. Só o espaço muda (vira `_` na hashtag); hífens ficam (`#lugar-escuta`).
Na volta, uma tag nova escrita como hashtag tem `_` trocado por espaço; escrita como `[[link]]`, vale o
nome exato. Para remover uma tag no estilo `both`, apague as duas formas.

## `bridge-token` — parear o terminal com o plugin

```bash
zotobs bridge-token     # cria o token e diz se o plugin está ativo
```
`add` usa o plugin automaticamente quando ele responde; `--no-plugin` pula
essa etapa e vai direto para a Web API/snippet.

---

# Biblioteca e coleções (`zotero_lib.py`)

Busca itens por tema e organiza a bibliografia em coleções (subpastas). Só lê o
banco (numa cópia, com o Zotero aberto ou fechado); escrever é **só** criar
coleções e adicionar itens a elas, pelo plugin ≥ 0.1.2 ou por um snippet JS.
Trabalha com itens que **já estão** na biblioteca. Itens são identificados pela
chave de 8 caracteres (ex.: `PWTUF7PV`). Uma biblioteca por comando: a pessoal por
padrão, `-L NOME|NÚMERO` para um grupo (veja `libraries`).

## `libraries` e `collections` — onde as coisas estão

```bash
zotobs libraries                              # pessoal e de grupos (marca as somente leitura)
zotobs collections                            # árvore inteira, com [chave] e nº de itens
zotobs collections --filter bibliografia      # só as que têm o texto no nome, com caminho completo
zotobs collections --depth 1 --json
```
Nomes repetidos são comuns. Em qualquer comando, uma coleção pode ser indicada pela
**chave**, pelo **nome**, por um **caminho** `A/B` (casa o final do caminho) ou por `/A/B`
(a partir da raiz). Se houver mais de uma candidata, o comando lista as chaves e pede
que você escolha.

## `search` — buscar por tema

```bash
zotobs search ritmo pulso                                   # qualquer um dos termos (OR)
zotobs search ritmo pulso --match all                       # todos os termos
zotobs search "música eletroacústica" --in all              # inclui notas, anotações e texto completo
zotobs search ritmo --not-in /Pesquisa/Ritmo --recursive    # o que ainda não está nessa coleção (nem nas subcoleções)
zotobs search --collection /Pesquisa/Ritmo                  # sem termos: lista o conteúdo
zotobs search timbre --types book,thesis --year 2000- --tag oficina
zotobs search ritmo --json                                  # para agentes
```
- **Casamento:** sem diferenciar maiúsculas e acentos; o termo vale como **início de palavra**
  (`ritm` acha ritmo/rítmico/ritmos); `--whole-word` exige a palavra inteira.
- **Campos (`--in`):** `title`, `abstract`, `tags`, `creators`, `publication`, `notes`,
  `annotations`, `fulltext` ou `all` (padrão: sem `annotations` e `fulltext`). Cada campo
  tem um peso (título 5, tags 4, resumo 3, notas/anotações/autores 2, publicação/texto
  completo 1); o `score` soma os campos em que cada termo casou e só serve para **ordenar**.
  A linha de cada resultado mostra quais termos casaram em quais campos.
- **Texto completo** (`fulltext`) usa o índice do próprio Zotero (`fulltext.sqlite`, Zotero 10+);
  é o campo mais ruidoso: um termo qualquer num livro inteiro conta.
- **Filtros:** `-c/--collection`, `--not-in` (ambos aceitam `--recursive` para incluir subcoleções),
  `--tag` (repetível), `--types`, `--year` (`2015`, `2010-2020`, `2010-`, `-2020`), `--limit` (30; `0` = todos).
- Não entram anexos, notas soltas e itens na lixeira.

## `show` — conferir antes de decidir

```bash
zotobs show PWTUF7PV NTGREQH2          # resumo, tags, coleções onde já está, anexos/notas/anotações, link zotero://select/…
```

## `collection create` / `collection add` — organizar

```bash
zotobs collection create Ritmo --parent /Pesquisa --dry-run   # só cria a subcoleção
zotobs collection add Ritmo ABCD1234 EFGH5678 --parent /Pesquisa --create --dry-run   # prévia
zotobs collection add Ritmo ABCD1234 EFGH5678 --parent /Pesquisa --create             # grava
zotobs search ritmo --json | zotobs collection add /Pesquisa/Ritmo -                  # chaves pela entrada padrão
```
- **Opcional — subcoleções por nicho:** `--groups mapa.json`, com `{"nome da subcoleção": ["CHAVE", …]}`,
  cria cada grupo como subcoleção dentro de DESTINO (`zotobs collection add Tese --groups mapa.json --create`;
  use `--dry-run` antes). Equivale a um `collection add "Tese/<nome>"` por grupo, é idempotente e não se
  combina com chaves avulsas. Sem `--groups`, tudo vai para uma coleção só.
- Chaves podem vir como argumentos ou por `-` (stdin): o JSON de `search --json` ou chaves soltas
  separadas por espaço, vírgula ou linha.
- `--create` cria o destino se ele não existir; **`--parent` diz onde** (sem ele, um destino novo nasce
  na raiz; a prévia mostra onde). Os níveis que faltarem em `A/B/C` também são criados.
- A prévia marca cada item: `+` adicionar · `=` já está na coleção · `!` problema (não existe nesta
  biblioteca, está na lixeira ou é anexo/nota). `--strict` não grava nada se houver `!`.
  Sem `--strict`, grava o que dá e termina com código 1.
- **Como grava:** pelo plugin `zotobs-bridge` ≥ 0.1.2 (Zotero aberto; vale na hora, sem rede nem chave).
  Sem plugin, com plugin antigo, sem token ou com o Zotero fechado, o comando diz o motivo e gera um
  **snippet JS** (`~/.cache/zotero-anot/ultima_colecao.js`, copiado para a área de transferência):
  Zotero → Ferramentas → Developer → Run JavaScript → colar → Run. `--no-plugin` (ou `--offline`) vai direto ao snippet.
  A Web API do Zotero **não** é usada aqui (veja [ARCHITECTURE.md](ARCHITECTURE.md)).
- Idempotente: repetir não duplica nem recria coleção existente de mesmo nome e mesma mãe.
- Só cria coleções e adiciona itens; **não** remove itens de coleções, não renomeia nem apaga coleções.
  Bibliotecas de grupo somente leitura recusam a escrita.
