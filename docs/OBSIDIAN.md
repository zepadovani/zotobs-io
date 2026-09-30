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
