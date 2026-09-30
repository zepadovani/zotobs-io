# Problemas conhecidos

## `info` diz "NÃO encontrado como attachment"
O caminho do PDF não bate com o registrado no Zotero. Anexos vinculados são
guardados relativos à pasta base (`extensions.zotero.baseAttachmentPath`).
Passe `--base-dir /pasta/base` (a mesma de Zotero → Configurações → Avançado →
Arquivos e pastas → *Base directory*) e/ou `--zotero-dir`.

## Não vejo as anotações no Zotero depois do `add`
- **Web API:** aperte o botão de sync (setas circulares). Ver também se a
  saída mostrou `[zotero/API] N criadas`.
- **Snippet JS:** aparecem na hora; feche/reabra a aba do PDF se estava aberta.
- **`--destino pdf`:** feche e reabra a aba do leitor; anotações embutidas
  aparecem como externas (somente leitura) até serem importadas
  (Arquivo → Importar anotações…).

## `texto não encontrado na página`
O trecho precisa ser literal e contínuo. Causas: hifenização/ligaduras
(use um trecho menor ou sem a palavra hifenizada), texto em imagem (PDF
escaneado), página errada (índice do PDF ≠ número impresso; use `page_label`
ou `zotobs pages`).

## `N ocorrências na página; informe 'occurrence'`
O trecho aparece mais de uma vez. Passe `"occurrence": 2` ou
`"context": "texto vizinho"`; ou escolha um trecho mais longo.

## API: `HTTP 403 ... Invalid key` / `write access`
Chave errada ou sem *Allow write access*. Refaça em
<https://www.zotero.org/settings/keys> ([API-KEY.md](API-KEY.md)).

## API: `either If-Unmodified-Since-Version or 'version' property must be provided`
Corrigido no projeto (envia `version: 0` em criações com chave própria). Se
reaparecer, atualize o repositório.

## Snippet JS: `UnloadedDataException: 'primaryData' not loaded for item`
Corrigido: o snippet agora usa `Zotero.Annotations.saveFromJSON` (a mesma
rotina do leitor). Cole o snippet **novo** (gerado por `add --offline`);
apague o código antigo da janela antes.

## Snippet JS: `attachment XXXX não encontrado na biblioteca N`
O anexo não está na biblioteca indicada (biblioteca de grupo?). Verifique com
`zotobs info arquivo.pdf` e se o PDF pertence à biblioteca pessoal.

## Duplicatas entre PDF e Zotero
Ocorre quando o mesmo comentário existe embutido e no banco. `extract`
já deduplica na leitura. Para limpar o PDF: `zotobs strip arquivo.pdf`
(remove só as criadas por este projeto) — confira antes que existem no Zotero.

## `database is locked`
O script nunca abre o banco original; usa uma cópia. Se aparecer, apague
`$TMPDIR/zotero_anot_cache/` e rode de novo.

## A área de transferência foi sobrescrita
`add --offline` copia o snippet. Desligue com `ZOTERO_ANOT_NO_CLIP=1`.

## Restaurar um PDF alterado
Toda alteração in-place gera backup em `~/.cache/zotero-anot/backups/`
(`<nome>.<data-hora>.pdf`). Copie de volta sobre o original.

## `uv: command not found` / “não é reconhecido”
O `uv` não está instalado ou sua pasta não está no PATH. Veja o passo 2 de
[INSTALL.md](INSTALL.md). Depois de instalar, **feche e abra o terminal**.
O plugin não herda o PATH do seu terminal; ele acrescenta `~/.local/bin`,
`/opt/homebrew/bin` e `/usr/local/bin` por conta própria. Se o seu `uv` está em
outro lugar, indique o comando completo em *Configurações → zotobs-io*, ou
instale o `uv` em `~/.local/bin`.

## `zotobs: command not found`
O atalho não está no PATH. Rode `./install.sh --all` (macOS/Linux) ou
`install.ps1` (Windows) e confira o passo 4 de [INSTALL.md](INSTALL.md). Dentro
da pasta do projeto, `./bin/zotobs` sempre funciona.

## Plugin: “Add-on Installation Failed”
Causas vistas: manifesto sem `update_url` (já corrigido no projeto) ou versão do
Zotero fora do intervalo `strict_min/max_version`. Use o `.xpi` gerado por
`python3 extension/build.py` e veja o *Error Console* (Ferramentas → Developer).

## Plugin: não vejo os comandos no menu / os botões no leitor
Reinicie o Zotero depois de instalar. Para os botões do leitor, **feche e
reabra a aba do PDF**. Se ainda faltar, abra o *Error Console* e procure
“zotobs”.

## Plugin: a exportação diz “sem desenhos/texto coberto: CLI não encontrado/falhou”
O plugin não achou o comando `zotobs` (ou ele falhou). A janela mostra o fim do
erro; o log completo está em `zotobs-export.log` na pasta temporária do sistema
(macOS: `$TMPDIR`). Causas comuns: `uv` ausente (acima) ou caminho do CLI
errado nas configurações. A exportação ainda é feita, só sem os desenhos e sem
a mescla.

## `zotobs bridge-token`: “extensão inacessível”
O Zotero está fechado ou o plugin não está instalado/ativo. Abra o Zotero e
confira *Ferramentas → Plugins*.

## `zotobs bridge-token`: “extensão recusou o token”
O arquivo `~/.config/zotero-anot/bridge_token` não é o que o plugin lê (por
exemplo, você está em outro usuário do sistema). Rode `zotobs bridge-token` de
novo no mesmo usuário em que o Zotero roda.

## Reexportei e sumiu algo que escrevi na nota
Se o texto estava **dentro** de um bloco de anotação (linhas `> …` coladas ao
bloco), ele é tratado como comentário e o Zotero prevalece. Escreva **fora**
dos blocos (com uma linha em branco antes). Toda reexportação guarda a nota
anterior em `~/.cache/zotero-anot/backups/`.

## Windows / Linux ⚠️ (não testados)
Se algo falhar, veja o final de [INSTALL.md](INSTALL.md#ajude-a-testar-linux-e-windows)
para saber o que relatar.
