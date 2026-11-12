---
name: zotero-biblioteca
description: Busca itens na biblioteca do Zotero por tema (título, resumo, tags, autores, notas, anotações e texto completo dos PDFs) e organiza a bibliografia em coleções (subpastas) — cria a subcoleção e coloca nela os itens escolhidos. Use quando o usuário pedir "buscar na minha biblioteca textos sobre X", "montar/organizar a bibliografia de X numa subpasta/coleção", "o que eu tenho no Zotero sobre X?", "adicionar estes itens à coleção Y", "criar uma subcoleção", "ver a árvore de coleções" ou "o que ainda não está na coleção Z". Só trabalha com itens que JÁ estão na biblioteca (não importa referências novas). Funciona com qualquer agente que execute shell (Claude Code, opencode, Gemini/Antigravity).
---

# zotero-biblioteca

Script determinístico em `scripts/zotero_lib.py` (só stdlib; `uv run --script`
dispensa instalar qualquer coisa). Abreviação:
`Z=~/.claude/skills/zotero-biblioteca/scripts/zotero_lib.py` (em outros agentes,
use o caminho onde a skill estiver instalada). Se o atalho `zotobs` estiver
instalado, `zotobs search …` equivale a `uv run --script $Z search …`.

> Irmã da skill `zotero-anotacoes` (anotações de PDF). Esta cuida da **biblioteca**: busca e coleções.

## Modelo mental
- **Leitura:** o banco do Zotero é lido numa cópia (o Zotero o mantém travado);
  funciona com o Zotero aberto ou fechado. Nunca se escreve em `zotero.sqlite`.
- **Escrita:** só duas coisas — **criar coleções** e **adicionar itens a coleções**
  (nada é removido, renomeado ou apagado). Vai pelo plugin `zotobs-bridge`
  (≥ 0.1.2, com o Zotero aberto, vale na hora). Sem ele, o comando gera um
  **snippet JS** (salvo e copiado para a área de transferência) para colar em
  Zotero > Ferramentas > Developer > Run JavaScript > Run.
- Tudo é **idempotente**: repetir não duplica nada.
- Uma biblioteca por comando: a **pessoal** por padrão; `-L NOME|NÚMERO` escolhe um
  grupo (`libraries` lista). Bibliotecas de grupo "somente leitura" não aceitam escrita.
- Itens são identificados pela **chave** de 8 caracteres (ex.: `PWTUF7PV`), única na biblioteca.

## Fluxo recomendado: montar uma subcoleção sobre um tema

1. **Achar o lugar.** `uv run --script $Z collections --filter bibliografia`
   (mostra caminho completo, chave e nº de itens). Nomes repetidos são comuns:
   se `collection` acusar ambiguidade, use a **chave** ou o caminho com `/` inicial (`/Pesquisa/Ritmo`).
2. **Expandir o tema em termos de busca:** sinônimos, variantes em português e
   inglês, termos do autor. Na dúvida sobre o escopo, pergunte ao usuário.
3. **Buscar em camadas**, do mais preciso ao mais amplo:
   ```bash
   uv run --script $Z search ritmo "pulso" --in title,tags,abstract --json    # núcleo
   uv run --script $Z search ritmo pulso --in all --not-in "/Pesquisa/Ritmo"   # amplia (notas, anotações, texto completo) e esconde o que já está
   ```
   (`--not-in` e `--collection` exigem que a coleção já exista; na primeira busca, omita `--not-in`.)
4. **Avaliar de verdade.** O `score` só ordena; **não inclua pelo score**. Leia
   título/resumo (`show CHAVE…` traz resumo, tags e onde o item já está) e
   descarte o que casou por acaso (um termo em texto completo de um livro é fraco).
5. **Mostrar ao usuário** a lista curta (chave, ano, autores, título e por que
   entrou) e **pedir aprovação** antes de gravar. Cite o que deixou de fora quando houver dúvida.
6. **Prévia e gravação:**
   ```bash
   uv run --script $Z collection add Ritmo CHAVE1 CHAVE2 … --parent /Pesquisa --create --dry-run
   uv run --script $Z collection add Ritmo CHAVE1 CHAVE2 … --parent /Pesquisa --create
   ```
   Também aceita `-` para ler chaves da entrada padrão: a saída de `search --json`
   (usa `results[].key`) ou chaves soltas separadas por espaço/vírgula/linha.

### Opcional: dividir em subcoleções por nicho
Só se o usuário quiser (o padrão é uma coleção única). Agrupe as chaves aprovadas por nicho num JSON
(`mapa.json`) e crie tudo de uma vez; cada grupo vira uma subcoleção dentro de DESTINO:
```json
{"Técnica e individuação": ["662S3JWK", "4T3XG5BE"], "Economia política": ["R399YPPQ"], "Sonologia": ["PP774FQG"]}
```
```bash
uv run --script $Z collection add Tese --groups mapa.json --create --dry-run   # prévia de cada subcoleção
uv run --script $Z collection add Tese --groups mapa.json --create             # grava
```
Equivale a um `collection add "Tese/<nicho>"` por grupo; sem `--parent`, `Tese` nasce na raiz
(use `--parent` para criá-la dentro de outra). Um item pode constar em mais de um grupo. Os nomes
dos grupos não podem conter `/`. Também dá para dividir depois, rodando `collection add` com um destino por nicho.

## Comandos

| Comando | Para quê |
|---|---|
| `libraries` | bibliotecas (pessoal e de grupos) |
| `collections [--filter T] [--depth N] [--json]` | árvore de coleções com chaves e contagens |
| `search [TERMOS…] [filtros]` | busca por tema |
| `show CHAVE… [--json]` | detalhes (resumo, tags, coleções, link `zotero://select/…`) |
| `collection create DESTINO [--parent P]` | cria a coleção (e as que faltarem no caminho) |
| `collection add DESTINO CHAVE… [--create] [--parent P]` | adiciona itens |
| `collection add DESTINO --groups mapa.json [--create]` | (opcional) uma subcoleção por nicho, de uma vez |

**`search`**
- Termos: cada argumento é um termo ou frase (`"música eletroacústica"`); por padrão basta **um** deles (`--match all` exige todos).
- Casa **sem diferenciar maiúsculas nem acentos**, e o termo vale como **início de palavra** (`ritm` acha ritmo, rítmico, ritmos); `--whole-word` exige a palavra inteira.
- `--in CAMPOS`: `title,abstract,tags,creators,publication,notes,annotations,fulltext` ou `all`.
  Padrão: `title,abstract,tags,creators,publication,notes`. Pesos: título 5, tags 4, resumo 3,
  notas/anotações/autores 2, publicação/texto completo 1. `fulltext` usa o índice do próprio
  Zotero (exige Zotero 10+) e é o mais ruidoso.
- Filtros: `-c/--collection C` (só itens dela), `--not-in C` (exclui os que já estão), `--recursive`
  (as duas opções passam a incluir subcoleções), `--tag T` (repetível), `--types journalArticle,book,thesis`,
  `--year 2015 | 2010-2020 | 2010- | -2020`, `--limit N` (padrão 30; 0 = todos).
- Sem termos, os filtros listam itens (ex.: `search -c /Pesquisa/Ritmo` mostra o conteúdo da coleção).
- `--json`: `{"total", "results": [{key, title, creators, year, type, publication, doi, citekey, tags,
  collections, score, matched: {termo: [campos]}, abstract_snippet}]}`.

**`collection add/create`**
- DESTINO: chave, nome, caminho `A/B` (casa o final do caminho) ou `/A/B` (a partir da raiz).
- `--create` cria o destino que não existir; `--parent P` diz **onde**. Sem `--parent`, um destino
  novo é criado a partir da raiz (a prévia diz onde — confira).
- A prévia marca cada item: `+` adicionar · `=` já está · `!` problema (não existe nesta biblioteca,
  lixeira, anexo/nota). `--strict` não grava nada se houver `!`.
- `--no-plugin` (ou `--offline`) vai direto para o snippet JS. Se o plugin estiver ausente,
  antigo ou sem token, o comando cai sozinho no snippet e diz o motivo (`zotobs bridge-token` pareia o plugin).

## Regras para o agente
- **Sempre `--dry-run` antes de gravar** e mostre o resumo; só grave com a aprovação do usuário.
- Só chaves que vieram de `search`/`show`/`collections`: **nunca invente** chaves nem coleções.
- A coleção é uma "pasta" de **referências**, não de arquivos: um item pode estar em várias coleções; adicionar não move nem remove de outras.
- Se o Zotero estava aberto e o resultado não aparece, é só a lista do Zotero: ela atualiza na hora quando
  a escrita foi pelo plugin; pelo snippet, depois do Run. Para a nuvem, o sync do próprio Zotero.
- Configuração do Zotero vem de `prefs.js`; sobrescreva com `--zotero-dir` ou `ZOTERO_DATA_DIR`.
- **Limites:** não importa referências novas (de Crossref, OpenAlex, etc.), não remove itens de coleções,
  não renomeia nem apaga coleções, não edita tags. Itens ausentes da biblioteca ficam fora (`!`).
