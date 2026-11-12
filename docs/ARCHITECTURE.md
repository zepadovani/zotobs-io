# Arquitetura e decisões

## Onde vivem as anotações

| Local | Quem cria | Como o projeto acessa |
|---|---|---|
| **Banco `zotero.sqlite`** (tabela `itemAnnotations`) — anotações nativas | leitor do Zotero | leitura por **cópia** do banco (+WAL) em cache; escrita **nunca** direta |
| **Dentro do PDF** (objetos `/Annot`) — anotações embutidas | Preview, Skim, Acrobat… e `--dest pdf`/`embed` | PyMuPDF |

O Zotero mantém o banco travado enquanto aberto, então `extract` trabalha
numa cópia (`$TMPDIR/zotero_anot_cache`), refeita quando o original muda.

**Decisão:** o projeto não escreve em `zotero.sqlite`. A escrita nativa vai
pela Web API do Zotero (o desktop baixa no sync) ou por código executado
dentro do Zotero (`Zotero.Annotations.saveFromJSON`), que valida e sincroniza
corretamente. Escrever SQL direto arriscaria corromper ou dessincronizar o banco.

## Modelo de dados do Zotero

`itemAnnotations`: `type` 1 highlight, 2 note, 3 image, 4 ink, 5 underline,
6 text; `text`, `comment`, `color` (hex), `pageLabel`, `sortIndex`,
`position` (JSON), `authorName`, `isExternal`. O anexo (`itemAttachments`)
guarda o caminho: `attachments:REL` (relativo à pasta base de anexos
vinculados, do `prefs.js`) ou `storage:nome` (em `~/Zotero/storage/<KEY>/`).

`position` (coordenadas **PDF**, origem embaixo-esquerda):
- highlight/underline: `{"pageIndex": N, "rects": [[x0,y0,x1,y1], ...]}` (um por linha)
- note/image: uma `rect` (nota: 22×22)
- text: idem + `fontSize`, `rotation`
- ink: `{"pageIndex", "width", "paths": [[x,y,x,y,...], ...]}`

`sortIndex`: `"<pageIndex:5>|<offset de caractere:6>|<topo:5>"`.

O PyMuPDF trabalha com origem no **topo**-esquerdo; a conversão usa
`page.transformation_matrix` (e sua inversa).

## Chaves determinísticas (idempotência)

Cada anotação a incluir recebe um id `sha1(página|rótulo|tipo|texto|comentário|ocorrência)`
e, dele, uma **chave Zotero de 8 caracteres** (alfabeto `23456789ABCDEFGHIJKLMNPQRSTUVWXYZ`).
Web API e snippet JS usam a mesma chave ⇒ reenviar não duplica, mesmo
alternando entre os dois. Embutidas no PDF usam o id como `/NM` (nome).

## Localizador de trechos

Casa o texto **palavra a palavra** sobre `page.get_text("words")`, junta
palavras hifenizadas no fim de linha, tolera pontuação colada, devolve um
quad por linha visual (multi-linha ok). Se o trecho ocorre mais de uma vez,
exige `occurrence`/`context`, em vez de adivinhar.

## Desenhos (caneta)

- O PNG é o recorte da região com o traço redesenhado por cima (o traço só
  existe no banco).
- **Texto coberto:** para desenhos estreitos, fora de figuras (`get_image_info`),
  pega as linhas cujo centro vertical está entre o topo e a base do traço, do
  lado do traço em diante (traço à esquerda → palavras à direita).

## Estrutura do código

```
skills/zotero-anotacoes/
  SKILL.md                 instruções para agentes
  scripts/zotero_anot.py   CLI: extract, add, embed, strip, info, pages
  scripts/zotero_native.py backends nativos: chaves, posição, Web API, snippet JS
  tests/test_roundtrip.py  PDF sintético: add/extract/strip/markdown/nativo
skills/zotero-biblioteca/
  SKILL.md                 instruções para agentes (busca e coleções)
  scripts/zotero_lib.py    CLI: libraries, collections, search, show, collection create/add
  tests/test_lib.py        banco sintético, plugin falso, JS do plugin em node
  tests/harness.js         Zotero simulado para rodar o JS do plugin em node
bin/zotobs                 atalho (escolhe o script pelo subcomando)
install.sh                 symlinks para os agentes
docs/                      documentação
extension/                 (futuro) extensão do Zotero
```

Seções de `zotero_anot.py` (candidatas a virar módulos num pacote):
config do Zotero e banco → extração → desenhos → páginas → info → localizador
→ `resolve_spec` / escritores → entrada Markdown → comandos.

## Coleções e busca na biblioteca

- **Escrita só pelo plugin/snippet, nunca pela Web API.** O banco local pode estar à frente do
  servidor (itens ainda não sincronizados), e alterar coleções pela Web API exigiria a versão
  atual de cada item. O plugin usa a API interna (`Zotero.Collection.saveTx`,
  `item.addToCollection` + `saveTx`), que sincroniza normalmente depois.
- **Um só código JS.** `zotobsCollectionOp` roda no plugin (`/zotobs/collection`) e dentro do
  snippet; fica entre marcadores em `extension/bootstrap.js` e em `JS_CORE` de `zotero_lib.py`,
  e um teste garante que são idênticos. O Python decide (resolve nomes, prévia); o JS só executa
  e é idempotente (reaproveita coleção de mesmo nome e mesma mãe; pula item que já está).
- **Leitura.** Mesma cópia do banco usada pelas anotações. A busca carrega os itens da biblioteca
  e casa em Python (normaliza acentos/caixa; início de palavra), com pesos por campo. O texto
  completo consulta o FTS5 do próprio Zotero (`fulltext.sqlite`, `fulltextContent`, `rowid` =
  anexo → item pai); o layout é o do Zotero 10 (em versões anteriores o índice não é lido).
- Coleções na lixeira (`deletedCollections`) e itens apagados (`deletedItems`) são ignorados.

## Limites conhecidos

- `search`/`collection` só enxergam itens que já estão na biblioteca; não importam referências novas.
- Não removem itens de coleções nem renomeiam/apagam coleções.
- `add` cria highlight, underline, note e text; **não** cria image/ink.
- Não edita comentário de anotação existente (só cria).
- A Web API exige sync com o servidor do Zotero e o anexo já sincronizado.
- O snippet JS depende da API interna do Zotero (`Zotero.Annotations`).
- PDFs sem camada de texto (escaneados) não permitem localizar trechos.
