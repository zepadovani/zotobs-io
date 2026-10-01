# Plano: extensão do Zotero ("zotobs-bridge")

> **Andamento (2026-09-30):** M0 e M1 **verificados ao vivo no Zotero 10.0.4**:
> instalação do `.xpi` (exige `update_url` no manifesto), `zotobs bridge-token`
> mostra “extensão ativa”, `zotobs add` cria a anotação no leitor e o reenvio
> pula (“0 criadas, 1 já existiam”). Ainda sem teste ao vivo: token errado
> (403, só coberto com servidor falso) e Zotero fechado (fallback).
> **M2 (2026-09-30):** matriz de erros rodada contra o servidor real (403 sem/com token
> errado e com `Origin`; 400 corpo inválido; 404 anexo inexistente; 413 >500 itens; falha
> isolada por item; duplicada pulada; update fora do anexo recusado; update sem mudança =
> inalterada) e fallback do CLI com Zotero fechado/token errado (extensão → API → snippet,
> mensagens acionáveis; testado também com o Zotero realmente fechado: extensão falha →
> Web API cria, reenvio não duplica). O CLI envia em lotes de 200.
> **M3 verificado ao vivo:** `sync-md` alterou comentários de uma nota e de um texto livre
> (inclusive comentário com parágrafo em branco); o reenvio deu “nada a sincronizar”; a
> nota original restaurou os valores. Cor e leitura via `GET /annotations` ficaram fora
> (a leitura é feita pelo banco).
> Decisões: pareamento por arquivo `~/.config/zotero-anot/bridge_token` (lido
> a cada requisição; sem preferência do Zotero); a extensão é tentada **antes**
> da Web API (é local e imediata).

## Objetivo

Tornar o modo **sem rede** tão automático quanto a Web API: o `zotobs add`
entrega as anotações a um plugin dentro do Zotero, que as cria com
`Zotero.Annotations.saveFromJSON` — sem copiar/colar snippet, sem chave, sem
sync imediato. Como bônus, o mesmo canal permite **ler** e **editar**
anotações existentes com a validação do próprio Zotero.

Não é objetivo: interface gráfica no Zotero, sincronização própria, escrever
no `zotero.sqlite`.

## Estado atual (base já validada)

- O snippet JS que cria anotações via `Zotero.Annotations.saveFromJSON` **já
  foi executado com sucesso** no Zotero 10.0.4 (Run JavaScript). O plugin
  reaproveita exatamente essa chamada.
- O Zotero já expõe um servidor HTTP local em `127.0.0.1:23119`
  (`/connector/ping` responde). Plugins podem registrar endpoints nele
  (`Zotero.Server.Endpoints`).

## Arquitetura

```
zotobs add --dest zotero
   ├─ 1. Web API                       (se houver chave e rede)
   ├─ 2. Plugin local  ◄── novo        (POST http://127.0.0.1:23119/zotobs/import)
   └─ 3. Snippet JS                    (colar em Run JavaScript)
```

Plugin *bootstrapped* (Zotero 7+): `manifest.json` + `bootstrap.js`,
empacotado como `.xpi` (zip). Sem código de UI no MVP.

```
extension/
  manifest.json      id, versão, strict_min_version/strict_max_version
  bootstrap.js       startup/shutdown: registra e remove endpoints
  build.sh           zip -> build/zotobs-bridge.xpi
  README.md
```

### Endpoints (todos sob `/zotobs/`)

| Endpoint | Método | Função |
|---|---|---|
| `/zotobs/ping` | GET | `{"ok":true,"version":"…","zotero":"10.0.4"}` — o CLI detecta o plugin |
| `/zotobs/import` | POST | cria anotações (mesmo JSON do snippet); resposta `{criadas, puladas, falhas}` |
| `/zotobs/annotations?attachment=KEY` | GET | (fase 3) lista anotações do anexo |
| `/zotobs/update` | POST | (fase 3) altera comentário/cor/tags de anotação existente |

Corpo de `/import`:

```json
{"library": 1, "attachment": "87BBKH34",
 "items": [{"key":"…","annotationType":"highlight","annotationText":"…","annotationComment":"…",
            "annotationColor":"#ffd400","annotationPageLabel":"57",
            "annotationSortIndex":"00086|000080|00056","annotationPosition":"{…}",
            "tags":[{"tag":"agente"}]}]}
```
Idêntico ao formato que `zotero_native.to_native` já gera — o CLI não muda
de estrutura, só ganha um transporte novo.

Esboço do endpoint (a validar no Zotero 10):

```js
Zotero.Server.Endpoints["/zotobs/import"] = function () {};
Zotero.Server.Endpoints["/zotobs/import"].prototype = {
  supportedMethods: ["POST"],
  supportedDataTypes: ["application/json"],
  permitBookmarklet: false,
  init: async function (req) {
    if (!authorized(req)) return [403, "application/json", '{"error":"token"}'];
    const att = Zotero.Items.getByLibraryAndKey(req.data.library, req.data.attachment);
    // … para cada item: se já existe (chave) pula; senão saveFromJSON(att, {...})
    return [200, "application/json", JSON.stringify(result)];
  },
};
```

### Segurança (requisito de projeto, não opcional)

Um endpoint local que altera a biblioteca é alvo de qualquer processo local e
de páginas web (via navegador). Mitigações:

1. **Token compartilhado** em cabeçalho (`X-Zotobs-Token`), gerado na
   instalação e guardado em `~/.config/zotero-anot/config.json` (`"bridge_token"`)
   e numa preferência do Zotero. Sem token válido → 403.
2. **Recusar requisições com `Origin`** (as de navegador): o CLI não envia
   `Origin`. Um cabeçalho customizado também força *preflight* no navegador,
   que o endpoint não atende.
3. Escutar apenas em `127.0.0.1` (já é o comportamento do servidor do Zotero).
4. Escopo mínimo: só cria/edita **anotações**; não executa código arbitrário
   (ao contrário de plugins de "execução remota de JS"), não toca em outros
   tipos de item.
5. Limite de tamanho do corpo e de itens por requisição (ex.: 500).

## Fases

| Fase | Entrega | Critério de pronto |
|---|---|---|
| **M0** — protótipo | `.xpi` mínimo com `/zotobs/ping` | instala em Ferramentas → Plugins; `curl` recebe `ok` |
| **M1** — import | `/zotobs/import` + token; CLI usa o plugin quando `ping` responde | `zotobs add … ` cria anotação sem colar nada; reenvio pula duplicatas |
| **M2** — robustez | erros por item, limite de tamanho, logs no Zotero (`Zotero.debug`), versão/compatibilidade no `ping` | testes manuais em Zotero fechado/aberto, PDF inexistente, chave duplicada |
| **M3** — leitura/edição | `/annotations`, `/update` (comentário, cor, tags); `zotobs sync-md` | editar comentário no `.md` e refletir no Zotero |
| **M4** — distribuição | `build.sh`, release no GitHub, `update.json` para atualização | instalação a partir de release; `strict_max_version` revisada |

## Testes

- **Automáticos (CLI):** cliente HTTP com servidor falso (mesmo contrato) para
  a lógica de escolha de transporte e de fallback.
- **Manuais no Zotero:** matriz {Zotero aberto/fechado} × {token certo/errado}
  × {anexo existe/não existe} × {chave nova/existente}; verificar no leitor.
- **Regressão:** comparar as anotações criadas pelo plugin com as criadas
  pela Web API e pelo snippet (mesmas chaves, mesma posição).

## Riscos e questões em aberto

- **API interna.** `Zotero.Annotations`/`Zotero.Server` podem mudar entre
  versões majores. Mitigar: `ping` reporta versão; CLI cai no snippet se o
  plugin falhar; `strict_max_version` explícita; testes a cada atualização.
- **Formato do manifesto e `Zotero.Server.Endpoints`** — detalhes (campos do
  `manifest.json`, assinatura do `init`, cabeçalhos em `req.headers`) devem
  ser conferidos na documentação e no código do Zotero 10 antes do M0; o
  esboço acima segue o padrão de plugins recentes, não foi executado.
- **Dois lugares para o token** (arquivo do usuário e preferência do Zotero):
  definir o fluxo de pareamento (o CLI gera o token; o plugin o lê de um
  arquivo em `~/.config/zotero-anot/` para evitar cópia manual?).
- **Windows/Linux:** o projeto foi testado em macOS; caminhos e o atalho de
  área de transferência mudam.
- **Publicação:** decidir se o plugin fica só neste repositório privado ou
  ganha repositório/release próprio.

## Alternativas descartadas

| Alternativa | Por que não |
|---|---|
| Escrever direto no `zotero.sqlite` | risco de corrupção/dessincronização; exige Zotero fechado |
| API local do Zotero (`/api/`) | somente leitura |
| Plugin genérico de "executar JS remoto" | expõe execução arbitrária de código a qualquer processo local |
| Automatizar a janela Run JavaScript por script de UI (AppleScript) | frágil, dependente de foco/tela |
