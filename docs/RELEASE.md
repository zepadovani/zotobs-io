# Publicar uma versão do plugin

Para mantenedores. O Zotero atualiza plugins sozinho lendo o `update_url` do
`manifest.json` (aqui: `extension/updates.json` no branch `main`), que aponta
para o `.xpi` de uma *release* do GitHub e traz o **hash SHA-256** dele.

> **Requisito:** o repositório precisa ser **público** para que outras pessoas
> baixem o `.xpi` e o Zotero leia `updates.json`. Com repositório privado nada
> disso funciona para terceiros (instalação manual do `.xpi` continua valendo).

## Passo a passo

1. **Escolha a versão** (ex.: `0.2.0`) e edite em `extension/manifest.json` (`"version"`).
   O `bootstrap.js` lê a versão do manifesto ao iniciar.
2. **Rode os testes** (`make test`) e teste o plugin no Zotero (veja a lista
   abaixo).
3. **Gere o `.xpi` e o `updates.json`:**
   ```bash
   python3 extension/build.py --updates
   ```
   Cria `extension/build/zotobs-bridge-0.2.0.xpi` (+ `.sha256`) e reescreve
   `extension/updates.json` com o link e o hash. O `.xpi` é reprodutível (datas
   fixas no zip): o mesmo código gera o mesmo hash.
4. **Atualize o `CHANGELOG.md`**, faça *commit* (incluindo `updates.json`) e
   *push* no `main`.
5. **Crie a release com o arquivo gerado — exatamente esse:**
   ```bash
   git tag v0.2.0 && git push origin v0.2.0
   gh release create v0.2.0 extension/build/zotobs-bridge-0.2.0.xpi \
      extension/build/zotobs-bridge-0.2.0.xpi.sha256 --title "zotobs-bridge 0.2.0" --notes-file NOTAS.md
   ```
   O nome do arquivo e a tag precisam bater com o `update_link` de `updates.json`
   (`…/releases/download/v0.2.0/zotobs-bridge-0.2.0.xpi`). Se regerar o `.xpi`
   depois de publicar, o hash muda e a atualização passa a falhar: nesse caso
   publique uma versão nova.
6. **Confira:** `curl -sL <update_url>` deve mostrar a versão nova; e
   `curl -sL <update_link> | shasum -a 256` deve igualar o `update_hash`.

## Lista de testes manuais antes de publicar

- Instalar o `.xpi` por cima da versão anterior (Plugins → engrenagem → Install Plugin From File).
- `zotobs bridge-token` → “extensão ativa: vX.Y.Z”.
- Botão direito num item → exportar (pasta padrão e “para…”); conferir o `.md`.
- Leitor de PDF: botões **zotobs** e **zotobs…**, e botão direito no texto.
- Exportar de novo sobre a mesma nota → diálogo → *Mesclar* mantém um trecho escrito entre duas anotações.
- `zotobs add` (cria; reenvio pula) e `zotobs sync-md` (edita um comentário).
- Zotero fechado: `zotobs add` cai para a Web API/snippet com mensagem clara.

## Compatibilidade de versões do Zotero

`manifest.json` declara `strict_min_version` `6.999` (Zotero 7+) e
`strict_max_version` `10.*`. Quando sair uma versão nova do Zotero, teste e
suba o `strict_max_version`; a API interna usada (`Zotero.Annotations`,
`Zotero.Server`, `Zotero.Reader`) pode mudar entre versões principais.
