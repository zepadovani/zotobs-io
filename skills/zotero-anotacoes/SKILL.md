---
name: zotero-anotacoes
description: Extrai anotações de um PDF lido no Zotero (destaques, sublinhados, notas, texto livre, imagens, desenhos com o texto coberto — inclusive as feitas no leitor do Zotero, que ficam no banco e não no arquivo) para Markdown/JSON (Obsidian), e inclui anotações (highlight, underline, nota, texto) a partir de JSON ou de uma nota Markdown — por padrão como anotações NATIVAS do Zotero (Web API, com fallback JS), ou embutidas no PDF; converte anotações do Zotero em embutidas (embed). Use quando o usuário pedir "extrair minhas anotações/marcações do PDF", "passar meus destaques do Zotero para o Obsidian/markdown", "marcar/destacar/anotar este trecho no PDF/no Zotero", "colocar comentários nas páginas a partir das minhas notas", ou mencionar anotações do Zotero. Funciona com qualquer agente que execute shell (Claude Code, opencode, Gemini/Antigravity).
---

# zotero-anotacoes

Scripts determinísticos em `scripts/` (`zotero_anot.py` + `zotero_native.py`),
sem instalar nada global: `uv run --script` baixa `pymupdf` sozinho. Sem `uv`:
`python3 scripts/zotero_anot.py ...` com `pymupdf` instalado.
Abreviação: `Z=~/.claude/skills/zotero-anotacoes/scripts/zotero_anot.py`
(em outros agentes, use o caminho onde a skill estiver instalada).

## Modelo mental

| Onde vive a anotação | Como nasce | Como sai |
|---|---|---|
| **Banco do Zotero** (nativa; o leitor do Zotero grava aqui) | leitor do Zotero; `add` (padrão) | `extract` |
| **Dentro do PDF** (embutida; Preview/Skim/Acrobat/leitores externos) | `add --destino pdf`, `embed` | `extract` |

- **Padrão = nativa.** O script **nunca escreve em `zotero.sqlite`**; usa a Web
  API do Zotero ou o snippet JS (abaixo).
- `extract` junta as duas fontes sem duplicar (lê o banco numa cópia, pois o
  Zotero o mantém travado).
- Páginas: `page` = índice do PDF (base 1). O texto impresso pode ter outra
  numeração: use `page_label` ("57", "ix") ou `pages` para ver a tabela.

## Extrair → Markdown (Zotero/PDF → Obsidian)

```bash
uv run --script $Z extract "/caminho/arquivo.pdf" -o notas.md --imagens notas_img
```

Opções: `--json`, `--fonte auto|zotero|pdf|ambas`, `--tipos highlight,note,ink`,
`--paginas 80-90`, `--imagens DIR`. Saída agrupada por página (com página
impressa), cor, texto (`>`), comentário e link `zotero://open-pdf/...` que
abre o leitor na anotação; YAML com `citekey`/`zotero_item`.
Desenhos: o PNG traz o traço por cima; se está na margem, o texto das linhas
cobertas pela extensão vertical vira `texto` (`texto_coberto: true`);
círculos/setas sobre figuras ou muito largos não geram texto.
Diagnóstico: `uv run --script $Z info arquivo.pdf`.

## Incluir anotações (Obsidian/agente → Zotero)

Entrada: JSON **ou** uma nota Markdown.

**Markdown (para escrever à mão no Obsidian).** Sob um título de página:

```markdown
## p. 57            <- página do PDF (índice). Aceita o título gerado por `extract`
## pl. ix           <- página pelo rótulo impresso
> trecho literal do PDF :: seu comentário {verde}     -> destaque
_> trecho literal :: comentário                       -> sublinhado
- :: comentário geral da página {azul}                -> nota de página
```
Linhas sem `::` (como as geradas por `extract`) são ignoradas, então dá para
editar a própria nota exportada e reenviar.

**JSON:**
```json
[{"page_label": "57", "type": "highlight", "color": "green",
  "text": "felt-tip end of the drumstick", "comment": "por que importa"},
 {"page": 9, "type": "note", "comment": "nota na margem"},
 {"page": 87, "type": "text", "comment": "caixa livre", "rect": [300, 60, 540, 110]}]
```
`type`: highlight | underline | note | text. `text` = trecho **literal e
contínuo** (achado palavra a palavra; tolera quebra de linha e hifenização de
fim de linha). `occurrence` (n-ésima) ou `context` (texto vizinho) quando o
trecho se repete. `color`: yellow, red, green, blue, purple, magenta, orange,
gray (ou amarelo, vermelho, verde, azul, roxo, magenta, laranja, cinza; ou `#rrggbb`).

```bash
uv run --script $Z add arquivo.pdf marcas.md --dry-run     # valida, não grava
uv run --script $Z add arquivo.pdf marcas.md               # nativa no Zotero (padrão)
uv run --script $Z add arquivo.pdf marcas.md --destino pdf # embutida no PDF (backup + gravação incremental)
uv run --script $Z add arquivo.pdf marcas.md --destino ambos
```

### Como a escrita nativa funciona
1. **Web API (padrão).** Cria itens `annotation` na sua biblioteca online; o
   Zotero desktop os baixa no próximo sync (aperte o botão de sync). Precisa
   de chave com escrita: crie em zotero.org/settings/keys e salve em
   `~/.config/zotero-anot/config.json` como `{"api_key": "..."}` (ou
   `ZOTERO_API_KEY`). O attachment precisa já ter sido sincronizado.
2. **Fallback JS (`--offline`, sem chave, sem rede ou erro da API).** Gera
   `~/.cache/zotero-anot/ultimo_import.js`, copia para a área de transferência
   (desligue com `ZOTERO_ANOT_NO_CLIP=1`) e instrui: Zotero > Ferramentas >
   Developer > Run JavaScript > colar > Run. Roda dentro do Zotero (seguro
   para o banco, funciona offline).
- **Idempotente**: cada anotação tem chave Zotero determinística; reenviar o
  mesmo arquivo pula o que existe, mesmo alternando API e JS.
- As anotações nativas recebem a tag `agente` (`--tag ''` remove) e autor
  `--autor`.
- Erros por item (texto não achado, ocorrência ambígua) são listados e não
  derrubam o lote; `--estrito` aborta se houver qualquer erro.

## Converter Zotero → PDF embutido, e limpar

```bash
uv run --script $Z embed arquivo.pdf            # todas as anotações do banco viram embutidas (inclui ink/imagem)
uv run --script $Z embed arquivo.pdf --saida copia.pdf --tipos highlight,note
uv run --script $Z strip arquivo.pdf            # remove só as embutidas criadas por este script
uv run --script $Z strip arquivo.pdf --todas    # remove todas as embutidas
```
Alterações in-place fazem backup em `~/.cache/zotero-anot/backups/`
(`ZOTERO_ANOT_BACKUPS` muda a pasta); `--saida` grava numa cópia. Depois de
alterar o PDF, feche e reabra a aba dele no Zotero. Anotações embutidas por
outros programas podem ser trazidas ao banco no próprio Zotero:
Arquivo > Importar anotações… (no leitor).

## Regras para o agente
- Antes de gravar em PDF/Zotero do usuário: `--dry-run` e mostrar o resumo.
  PDFs em pastas sincronizadas (Nextcloud) são o arquivo real do Zotero.
- Não invente trechos: só marque texto que você leu no PDF.
- Configuração do Zotero vem de `prefs.js`; sobrescreva com `--zotero-dir` /
  `--base-dir` ou `ZOTERO_DATA_DIR` / `ZOTERO_BASE_DIR`.
- Limitações: `add` não cria imagem/desenho; não há edição de comentário de
  anotação já existente (só criação). Ver `README.md`.
