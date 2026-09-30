# Como gerar a chave da API do Zotero

A chave só é necessária para **escrever** anotações no Zotero pela rede
(`zotobs add`, modo padrão). Para **extrair** (`extract`) não precisa de nada.
Sem chave ou sem rede, o `add` cai sozinho no modo `--offline` (snippet JS).

## Pré-requisitos

1. **Conta em zotero.org** (gratuita): <https://www.zotero.org/user/register>.
2. **Sincronização ligada no Zotero desktop**: Zotero → Configurações →
   Sincronização → entre com a conta → "Sincronizar dados". As anotações são
   criadas na sua biblioteca online e o Zotero as baixa no próximo sync.
   - Não é preciso sincronizar os *arquivos* (PDF). Basta o item/anexo estar
     sincronizado (metadados). Quem usa arquivos vinculados, WebDAV ou
     Nextcloud continua igual.

## Passo a passo

1. Acesse <https://www.zotero.org/settings/keys> (faça login).
2. Clique em **Create new private key**.
3. Preencha:
   - **Key description:** ex. `zotobs-io`.
   - **Personal library:** marque
     - ✅ *Allow library access*
     - ✅ *Allow notes access*
     - ✅ *Allow write access*  ← indispensável
     - (*Allow files access* **não** é necessário)
   - **Default group permissions / grupos:** deixe *None*, a menos que queira
     anotar em bibliotecas de grupo (aí dê *Read/Write* ao grupo desejado).
4. Clique em **Save Key**. A chave (24 caracteres) aparece **uma única vez**:
   copie-a agora.

## Onde guardar

Crie `~/.config/zotero-anot/config.json` (o `./install.sh` já cria um modelo):

```json
{
  "api_key": "COLE_A_CHAVE_AQUI"
}
```

```bash
chmod 600 ~/.config/zotero-anot/config.json   # só você lê
```

Alternativa: variável de ambiente `ZOTERO_API_KEY` (e, opcionalmente,
`ZOTERO_USER_ID`; se ausente, é descoberto pela chave). Mude o caminho do
arquivo com `ZOTERO_ANOT_CONFIG`.

> **Nunca** coloque a chave em um repositório, nota do Obsidian ou conversa.
> O `.gitignore` deste projeto já bloqueia `config.json`.

## Testar

```bash
KEY=$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.config/zotero-anot/config.json')))['api_key'])")
curl -s -H "Zotero-API-Key: $KEY" "https://api.zotero.org/keys/$KEY"
```

A resposta deve trazer `"userID": ...` e `"write": true` em `access.user`.
Depois: `zotobs add arquivo.pdf marcas.md --dry-run` e, sem `--dry-run`, o
envio real (`[zotero/API] N criadas`). Aperte o botão de sync do Zotero para
ver as anotações no leitor.

## Revogar ou trocar

Na mesma página (<https://www.zotero.org/settings/keys>), clique em
**Delete** ao lado da chave. Crie outra e atualize o `config.json`.

## Não quero (ou não posso) usar chave

Use o modo offline: `zotobs add arquivo.pdf marcas.md --offline`. Veja
[USAGE.md](USAGE.md#modo-offline-sem-rede-nem-chave). A futura extensão
([PLUGIN-PLAN.md](PLUGIN-PLAN.md)) tornará esse caminho automático.
