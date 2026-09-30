# Instalador para Windows (NAO TESTADO). Rode no PowerShell, dentro da pasta do projeto:
#   powershell -ExecutionPolicy Bypass -File .\install.ps1 [-Agentes]
# Cria o comando `zotobs` em %USERPROFILE%\.local\bin e, com -Agentes, liga a skill
# a ~\.claude\skills e ~\.agents\skills (junction: não precisa de administrador).
param([switch]$Agentes)
$ErrorActionPreference = "Stop"
$root  = Split-Path -Parent $MyInvocation.MyCommand.Path
$skill = Join-Path $root "skills\zotero-anotacoes"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Write-Warning "uv não encontrado. Instale com:  powershell -ExecutionPolicy ByPass -c `"irm https://astral.sh/uv/install.ps1 | iex`""
}
$bin = Join-Path $env:USERPROFILE ".local\bin"
New-Item -ItemType Directory -Force $bin | Out-Null
# o atalho aponta para o script deste clone (caminho absoluto)
Set-Content -Encoding ASCII (Join-Path $bin "zotobs.cmd") "@echo off`r`nuv run --script `"$skill\scripts\zotero_anot.py`" %*"
Write-Host "atalho: $bin\zotobs.cmd (confira se a pasta está no PATH)"
if ($Agentes) {
  foreach ($d in @(".claude\skills", ".agents\skills")) {
    $dir = Join-Path $env:USERPROFILE $d; $dest = Join-Path $dir "zotero-anotacoes"
    New-Item -ItemType Directory -Force $dir | Out-Null
    if (Test-Path $dest) { Write-Host "pulado (já existe): $dest" }
    else { New-Item -ItemType Junction -Path $dest -Target $skill | Out-Null; Write-Host "instalado: $dest" }
  }
}
$cfg = Join-Path $env:USERPROFILE ".config\zotero-anot\config.json"
if (-not (Test-Path $cfg)) {
  New-Item -ItemType Directory -Force (Split-Path $cfg) | Out-Null
  Set-Content -Encoding UTF8 $cfg "{`n  `"api_key`": `"COLE_A_CHAVE_AQUI`"`n}"
  Write-Host "modelo criado: $cfg (veja docs/API-KEY.md)"
}
