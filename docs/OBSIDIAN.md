# Fluxo Obsidian ⇄ Zotero

## 1. Zotero → Obsidian

```bash
zotobs extract "/caminho/artigo.pdf" -o "Vault/leituras/artigo.md" --imagens "Vault/leituras/artigo_img"
```

Você recebe uma nota com YAML (`citekey`, `zotero_item`), seções por página e
blocos como:

```markdown
## p. 87 (impresso: 57)

🟡 **destaque** · amarelo [↗](zotero://open-pdf/library/items/ABCD1234?page=87&annotation=EFGH5678)
> trecho destacado

**Comentário:** meu comentário
```

O link `↗` abre o Zotero na anotação exata. Refazer a exportação regenera a
nota (não edite os blocos exportados esperando que voltem ao Zotero: só a
**criação** de anotações é suportada hoje).

## 2. Obsidian → Zotero (comentários novos)

Numa nota qualquer (pode ser a exportada), escreva sob um título de página:

```markdown
## p. 57                 ← página do PDF (índice, base 1)
> trecho literal do PDF :: seu comentário {verde}
_> outro trecho literal :: sublinhado com comentário
- :: comentário geral sobre a página {azul}

## pl. ix                ← página pelo número impresso
> The acknowledgments :: agradecimentos bem feitos
```

| Linha | Cria |
|---|---|
| `> trecho :: comentário {cor}` | destaque com comentário |
| `_> trecho :: comentário {cor}` | sublinhado com comentário |
| `- :: comentário {cor}` | nota de página (ícone) |

- O **trecho** precisa existir literalmente na página (o localizador ignora
  quebras de linha e hifenização de fim de linha). Pode vir entre `==...==` ou
  aspas.
- `{cor}` é opcional (padrão amarelo).
- Linhas sem `::` — inclusive os blocos gerados pelo `extract` — são ignoradas,
  então dá para usar a mesma nota nos dois sentidos.
- Comentário vazio é válido: `> trecho ::` cria só o destaque.

Depois:

```bash
zotobs add "/caminho/artigo.pdf" "Vault/leituras/artigo.md" --dry-run
zotobs add "/caminho/artigo.pdf" "Vault/leituras/artigo.md"
```

## 3. Dica: comentários gerados por agente

Peça ao agente para escrever as marcações **numa nota Markdown** na sintaxe
acima, revise no Obsidian (ajuste/apague linhas) e só então rode o `add`. O
JSON é o formato para automação; o Markdown é o formato para revisão humana.

## 4. Números de página

Teses e livros costumam ter capa/romanos, então "página 57" impressa pode ser
a 87 do PDF. Use `## pl. 57` (rótulo impresso) ou `## p. 87` (índice do
PDF). `zotobs pages arquivo.pdf` mostra a tabela.

## Formato da nota exportada (`extract`)

Um bloco de citação por anotação: link `[↗]` para o leitor do Zotero, o trecho
(ou rótulo) na cor da anotação e, logo abaixo, o comentário.

```markdown
> [↗](zotero://open-pdf/…&annotation=KEY) <span style="background:#ffd40066;">“trecho destacado”</span> <small>#tag</small>
> meu comentário
```

| Tipo | 1ª linha do bloco |
|---|---|
| destaque | trecho entre aspas com fundo na cor |
| sublinhado | trecho entre aspas sublinhado na cor |
| nota / texto livre | rótulo `nota`/`texto` na cor; o conteúdo vem abaixo |
| imagem | rótulo `imagem` + recorte (`![]()`) abaixo |
| desenho | rótulo `desenho` na cor, seguido do trecho coberto em *“itálico”* (se houver) + recorte abaixo |

Editar o comentário (linhas `> …` abaixo da 1ª) ou as `<small>#tags</small>` e rodar
`zotobs sync-md` leva a mudança de volta ao Zotero.

### Reexportar sem perder o que você escreveu

Cada página aparece como `#### p. N` seguida de um link para a página. Ao rodar
`zotobs extract … -o nota.md` de novo sobre uma nota existente (padrão
`--se-existe mesclar`):

- os blocos de anotação são **atualizados a partir do Zotero** (casados pela
  chave `annotation=KEY`; anotações novas entram, apagadas saem);
- qualquer texto seu **fora dos blocos** (entre duas anotações, por exemplo)
  é mantido e reinserido logo depois do bloco que o precedia; se esse bloco foi
  apagado, vai para antes do seguinte; sem nenhum dos dois, vai para o fim, sob
  “trechos sem anotação de origem”;
- o cabeçalho (frontmatter) é preservado, atualizando só `anotacoes` e `extraido_em`;
- uma cópia da nota anterior fica em `~/.cache/zotero-anot/backups/`;
- imagens `CHAVE.png` que não pertencem mais a nenhuma anotação são removidas.

Atenção: o Zotero prevalece sobre os comentários dentro dos blocos. Se você editou
um comentário no `.md`, rode `zotobs sync-md` **antes** de reexportar (o comando
avisa quando há diferenças). Use `--se-existe sobrescrever` para recriar o arquivo do zero.
