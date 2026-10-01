# Instalação passo a passo

Este guia assume que você **nunca** usou `uv` nem o terminal para instalar
programas. Se já sabe o que é isso, vá direto aos comandos.

> **Estado dos testes.** Tudo foi desenvolvido e testado em **macOS** com
> **Zotero 10.0.4**. Em **Linux** e **Windows** o projeto foi escrito para
> funcionar, mas **não foi testado**: siga este guia, e se algo falhar veja
> [Problemas](TROUBLESHOOTING.md) e
> [como relatar](#ajude-a-testar-linux-e-windows). Os trechos específicos de
> Windows e Linux estão marcados com ⚠️.

## 0. O que você vai instalar (e por quê)

São três peças. Você pode usar só a primeira, ou todas.

| Peça | O que faz | Precisa de `uv`? |
|---|---|---|
| **Plugin `zotobs-bridge`** (arquivo `.xpi`) | Adiciona ao Zotero os botões de exportar anotações para Markdown (no menu do botão direito e no leitor de PDF) e recebe anotações vindas do terminal | Não sozinho; **sim** para exportar desenhos e para mesclar (passo 6) |
| **Comando `zotobs`** (terminal) | Lê as anotações do Zotero e as converte em Markdown/Obsidian; envia anotações e edições de volta ao Zotero | **Sim** |
| **Skill para agentes de IA** (opcional) | Ensina Claude Code, opencode, Gemini/Antigravity a usar o comando | Sim (usa o comando) |

**O que é o `uv`?** Um programa gratuito que executa scripts Python já
preparando tudo de que eles precisam (aqui: a biblioteca `pymupdf`, que lê
PDFs). Sem ele você teria que instalar Python e bibliotecas à mão. Ele não
mexe no Python do seu sistema.

## 1. Onde digitar comandos

- **macOS:** abra o app **Terminal** (Spotlight: `⌘ + espaço`, digite “Terminal”).
- **Linux:** abra o seu terminal (em geral `Ctrl + Alt + T`).
- **Windows** ⚠️: abra o **PowerShell** (menu Iniciar → digite “PowerShell”).

Cada bloco de código abaixo é para **copiar e colar** e apertar Enter.
Linhas que começam com `#` são comentários: não precisam ser digitadas.

## 2. Instalar o `uv`

Primeiro veja se já tem:

```bash
uv --version
```

Se aparecer um número de versão (ex.: `uv 0.9.0`), pule para o passo 3.
Se aparecer “command not found” / “não é reconhecido”, instale:

**macOS e Linux** (Terminal):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
(No macOS também serve `brew install uv`, se você usa o Homebrew.)

**Windows** ⚠️ (PowerShell):
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Depois **feche o terminal e abra de novo** (isso recarrega o PATH) e confira:

```bash
uv --version
```

Se ainda não for reconhecido, o `uv` foi instalado em `~/.local/bin`
(macOS/Linux) ou `%USERPROFILE%\.local\bin` (Windows) e essa pasta precisa
estar no PATH. O instalador do `uv` costuma avisar e configurar isso sozinho;
veja a [documentação do uv](https://docs.astral.sh/uv/getting-started/installation/).

> Sem `uv`? Alternativa: tenha Python 3.9+ e rode `pip install pymupdf`; troque
> `zotobs …` por `python3 skills/zotero-anotacoes/scripts/zotero_anot.py …`.
> O plugin também achará o comando se você indicar o caminho nas configurações.

## 3. Baixar o projeto

**Com git** (se você tem):
```bash
git clone https://github.com/zepadovani/zotobs-io.git ~/repositorios/zotobs-io
cd ~/repositorios/zotobs-io
```

**Sem git:** na página do projeto no GitHub, botão verde **Code → Download
ZIP**; descompacte em uma pasta fixa (ex.: `Documentos/zotobs-io`) e entre
nela pelo terminal (`cd caminho/da/pasta`). Não mova a pasta depois: o comando
`zotobs` aponta para ela.

> O nome `~/repositorios/zotobs-io` é só uma sugestão. O plugin procura o
> comando nessa pasta como último recurso; você pode indicar outro caminho
> nas configurações do plugin (passo 6).

## 4. Instalar o comando `zotobs`

**macOS e Linux:**
```bash
./install.sh --all        # comando `zotobs` + skill para os agentes (veja opções abaixo)
```
Se quiser só o comando, sem as skills dos agentes, rode `mkdir -p ~/.local/bin && ln -sf "$PWD/bin/zotobs" ~/.local/bin/zotobs`.

**Windows** ⚠️:
```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
# com -Agentes também liga a skill às pastas dos agentes de IA
```

O comando fica em `~/.local/bin` (macOS/Linux) ou `%USERPROFILE%\.local\bin`
(Windows). **Essa pasta precisa estar no PATH.** Teste, **em um terminal novo**:

```bash
zotobs --help
```

Se disser que não encontrou o comando, use o caminho completo
(`./bin/zotobs --help` dentro da pasta do projeto; `.\bin\zotobs.cmd --help` no
Windows) ou adicione a pasta ao PATH:

- **macOS (zsh)** — acrescente ao arquivo `~/.zshrc` a linha
  `export PATH="$HOME/.local/bin:$PATH"` e abra um terminal novo.
- **Linux (bash)** — igual, no arquivo `~/.bashrc`.
- **Windows** ⚠️ — Iniciar → “Editar as variáveis de ambiente do sistema” →
  Variáveis de Ambiente → `Path` do usuário → Novo → `%USERPROFILE%\.local\bin`.

A primeira execução de `zotobs` demora um pouco (o `uv` baixa o `pymupdf`);
as seguintes são rápidas.

### Testar se enxerga o seu Zotero

Escolha um PDF que esteja na sua biblioteca do Zotero:

```bash
zotobs info "/caminho/completo/do/artigo.pdf"
```

Deve mostrar o item, a chave do anexo e quantas anotações existem. Se disser
“NÃO encontrado como attachment”, veja [Problemas](TROUBLESHOOTING.md).

## 5. Instalar o plugin no Zotero

Você precisa do arquivo **`zotobs-bridge-X.Y.Z.xpi`**:

- Baixe-o na página **Releases** do projeto no GitHub (clique com o botão
  direito no link → *Salvar link como…*, para o navegador não tentar instalá-lo
  nele mesmo); ou
- gere-o a partir do código: `python3 extension/build.py` (cria
  `extension/build/zotobs-bridge-X.Y.Z.xpi`; no Windows use `py extension\build.py`).

Depois, **no Zotero** (versão 7 ou mais nova):

1. Menu **Ferramentas → Plugins** (no macOS: *Tools → Plugins*).
2. Clique na **engrenagem** (canto superior direito) → **Install Plugin From File…**
3. Escolha o arquivo `.xpi` → **Install**. Se o Zotero pedir, reinicie-o.

Para conferir: na lista de plugins aparece **zotobs-bridge**. Clique com o
botão direito em um item da biblioteca: no fim do menu há
**“zotobs-io: Exportar anotações …”**.

**Atualizar:** atualize também o comando (`git pull` na pasta do projeto: o plugin e o CLI evoluem juntos) e repita o procedimento com o `.xpi` mais novo (ele substitui o
antigo). Quando o projeto estiver publicado com releases, o Zotero também
verifica atualizações sozinho (*Plugins → engrenagem → Check for Updates*).

## 6. Configurar o plugin

**Configurações do Zotero** (macOS: `Zotero → Settings`; Windows/Linux:
`Edit → Settings`) → aba **zotobs-io**:

1. **Pasta padrão de exportação** — clique em *Escolher…* e selecione onde as
   notas devem ser criadas (por exemplo, uma pasta dentro do seu cofre do
   Obsidian). Para cada PDF será criada uma pasta com o nome do PDF:
   `<pasta>/<nome do PDF>/<nome do PDF>.md` e `…_img/` (imagens).
2. **Usar o CLI zotobs** (marcado por padrão) — é o que exporta os *desenhos
   com o texto que eles cobrem* e permite *mesclar* com uma nota já editada.
   Se o plugin não achar o comando sozinho, digite o caminho dele no campo
   (resultado de `which zotobs` no macOS/Linux, ou `where zotobs` no Windows).

## 7. Primeiro uso

1. No Zotero, abra um PDF, faça algumas anotações (destaque, nota…).
2. Exporte de um destes jeitos:
   - **Leitor de PDF:** botão **zotobs** na barra de ferramentas (pasta padrão)
     ou **zotobs…** (escolher a pasta); ou botão direito no texto do PDF.
   - **Biblioteca:** botão direito no item (ou no PDF dentro dele) →
     *zotobs-io: Exportar anotações (pasta padrão)* / *…para…*.
3. Uma janela mostra o resultado. Abra a pasta no Obsidian (ou em qualquer
   editor de Markdown).

Se a nota já existe, o plugin pergunta: **Mesclar** (mantém o que você
escreveu entre as anotações — recomendado), **Sobrescrever** ou **Cancelar**.
Veja [OBSIDIAN.md](OBSIDIAN.md).

### Parear o plugin com o terminal (opcional)

Só é necessário para **enviar** anotações do terminal/Obsidian ao Zotero sem
internet e sem chave de API (`zotobs add`, `zotobs sync-md`):

```bash
zotobs bridge-token
```

Deve responder **“extensão ativa”** (com o Zotero aberto). Isso cria um
arquivo com uma senha local em `~/.config/zotero-anot/bridge_token`, que só o
plugin e o comando conhecem.

## 8. Chave de API do Zotero (opcional)

Só para `zotobs add` quando o plugin não estiver disponível (ex.: Zotero
fechado). Passo a passo em [API-KEY.md](API-KEY.md). **Extrair** anotações
(`extract`) e usar o plugin **não** precisam de chave.

## 9. Agentes de IA (opcional)

O `install.sh --all` (ou `install.ps1 -Agentes`) liga a skill às pastas lidas por:

| Opção | Pasta | Quem lê |
|---|---|---|
| `--claude` | `~/.claude/skills` | Claude Code (e o opencode também lê esta pasta) |
| `--agents` | `~/.agents/skills` | padrão compartilhado (Antigravity/Gemini e outros) |
| `--opencode` | `~/.config/opencode/skills` | opencode |

Depois é só pedir ao agente: “extraia as anotações deste PDF do Zotero”.
Sem instalar nada, você pode dizer ao agente “leia
`skills/zotero-anotacoes/SKILL.md` e faça …”. O agente precisa de acesso a
shell e de permissão para ler a pasta de dados do Zotero e os PDFs.

## 10. Se o Zotero guarda os dados em lugar incomum

Normalmente o comando descobre sozinho (lê o `prefs.js` do seu perfil do
Zotero). Se não achar:

```bash
zotobs --zotero-dir "/pasta/de/dados/do/Zotero" --base-dir "/pasta/base/dos/anexos" info arquivo.pdf
# ou defina as variáveis de ambiente ZOTERO_DATA_DIR e ZOTERO_BASE_DIR
```

A pasta de dados é a que contém `zotero.sqlite` (em geral `~/Zotero`;
no Windows ⚠️, `C:\Users\SEU_NOME\Zotero`). A pasta base dos anexos vinculados
está em *Configurações → Avançado → Arquivos e pastas → Base directory*.

## Atualizar, verificar, desinstalar

```bash
git pull                 # (se clonou) atualiza o código; o comando e a skill usam a pasta direto
make test                # testes automáticos (precisa de `make`; opcional)
```

Desinstalar (macOS/Linux; só remove atalhos, não seus arquivos):
```bash
rm ~/.local/bin/zotobs ~/.claude/skills/zotero-anotacoes ~/.agents/skills/zotero-anotacoes ~/.config/opencode/skills/zotero-anotacoes
rm -r ~/.config/zotero-anot ~/.cache/zotero-anot      # config, token e backups (opcional)
```
No Zotero: *Ferramentas → Plugins → ⋯ ao lado do zotobs-bridge → Remove*.

## Ajude a testar Linux e Windows

Se você usa um desses sistemas e tentou instalar, **conte o que aconteceu**
(abra uma *issue* no GitHub), mesmo que tenha dado certo. Inclua:

- sistema e versão, versão do Zotero, resultado de `uv --version`;
- em qual passo deste guia parou e a mensagem de erro completa;
- o arquivo `zotobs-export.log` (na pasta temporária do sistema) se o erro foi
  na exportação pelo plugin; e, se possível, o **Error Console** do Zotero
  (*Ferramentas → Developer → Error Console*, filtre por “zotobs”).

Pontos que mais podem precisar de ajuste fora do macOS: detecção da pasta de
dados do Zotero no Windows, o atalho `zotobs.cmd`, e a chamada do comando pelo
plugin (Linux usa `bash`; Windows usa um `.cmd` temporário).
