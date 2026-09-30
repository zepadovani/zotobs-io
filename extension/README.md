# extension/ — zotobs-bridge (v0.1.0, M0–M3)

Extensão do Zotero 7+ que recebe anotações do CLI em
`http://127.0.0.1:23119/zotobs/*` e as cria via `Zotero.Annotations.saveFromJSON`
— sem chave de API, sem rede, sem colar snippet. Plano e fases:
[../docs/PLUGIN-PLAN.md](../docs/PLUGIN-PLAN.md).

## Instalar

```bash
make xpi                                   # gera extension/build/zotobs-bridge.xpi
zotobs bridge-token                        # cria ~/.config/zotero-anot/bridge_token (modo 600)
```
Zotero → Ferramentas → Plugins → engrenagem → *Install Plugin From File…* →
escolher o `.xpi`. Depois: `zotobs bridge-token` de novo deve mostrar
“extensão ativa”.

## Uso

`zotobs add …` tenta a extensão primeiro (se houver token e ela responder),
depois Web API, depois snippet. `--sem-extensao` pula o primeiro passo.

## Editar anotações existentes (M3)

```bash
zotobs extract arquivo.pdf -o notas.md     # edite os **Comentário:** e as #tags no Obsidian
zotobs sync-md arquivo.pdf notas.md --dry-run   # mostra o que mudou
zotobs sync-md arquivo.pdf notas.md             # grava no Zotero (via /zotobs/update)
```
Só comentário e tags; só anotações do anexo indicado. Requer a extensão ≥ 0.1.0
(reinstale o `.xpi`).

## Segurança

O endpoint exige `X-Zotobs-Token` igual ao arquivo `bridge_token` (lido a cada
requisição; sem arquivo = tudo negado), recusa requisições com `Origin`,
aceita no máx. 500 itens e só cria anotações.

## Status dos testes

- CLI ↔ contrato HTTP: automático (`tests/test_bridge.py`, servidor falso).
- `bootstrap.js` dentro do Zotero 10: verificado ao vivo no Zotero 10.0.4 (M0/M1
  ok; pendentes: token errado e Zotero fechado).
